import http.server
import socketserver
import urllib.parse
import datetime
import hashlib
import hmac
import secrets
import json
import os
import re
import sys
import socket
import threading
import http.cookies

import amf

PORT = 9090

HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# Language (zh-CN original / zh-TW / en)
# language.json holds the choice; launcher.py and the web pages change it via
# /api/language. Translated copies of game text files live in
# lang/<code>/<same path as the original>; if a file has no translation the
# original (Simplified Chinese) is served. Strings the server itself sends to
# the game (building and level names...) are translated through
# lang/<code>/server_text.json {"original": "translation"}.
# ---------------------------------------------------------------------------
LANGUAGES = {"zh-CN": "简体中文", "zh-TW": "繁體中文", "en": "English"}
DEFAULT_LANGUAGE = "zh-CN"
LANGUAGE_FILE = os.path.join(HERE, "language.json")
_lang_cache = {"mtime": None, "code": DEFAULT_LANGUAGE}
_server_text_cache = {}


def get_language():
    try:
        m = os.path.getmtime(LANGUAGE_FILE)
    except OSError:
        return DEFAULT_LANGUAGE
    if m != _lang_cache["mtime"]:
        try:
            with open(LANGUAGE_FILE, encoding="utf-8") as f:
                code = json.load(f).get("language", DEFAULT_LANGUAGE)
        except Exception:
            code = DEFAULT_LANGUAGE
        _lang_cache.update(mtime=m, code=code if code in LANGUAGES else DEFAULT_LANGUAGE)
    return _lang_cache["code"]


def set_language(code):
    if code not in LANGUAGES:
        return False
    with open(LANGUAGE_FILE, "w", encoding="utf-8") as f:
        json.dump({"language": code}, f, ensure_ascii=False, indent=2)
    return True


def server_text(code):
    if code not in _server_text_cache:
        table = {}
        try:
            with open(os.path.join(HERE, "lang", code, "server_text.json"), encoding="utf-8") as f:
                table = json.load(f)
        except Exception:
            pass
        _server_text_cache[code] = table
    return _server_text_cache[code]


def translate_payload(obj, table=None):
    """Replace server-sent Chinese strings with the chosen language's text."""
    if table is None:
        code = get_language()
        if code == DEFAULT_LANGUAGE:
            return obj
        table = server_text(code)
        if not table:
            return obj
    if isinstance(obj, str):
        return table.get(obj, obj)
    if isinstance(obj, dict):
        return {k: translate_payload(v, table) for k, v in obj.items()}
    if isinstance(obj, list):
        return [translate_payload(v, table) for v in obj]
    return obj
os.chdir(HERE)

# --------------------------------------------------------------------------
# Accounts + per-account save files
# --------------------------------------------------------------------------
# server.py used to be entirely stateless (every response was a fixed canned
# payload for the single hardcoded userId=245953145 the client always
# sends), so nothing ever persisted between launches. This section adds:
#   - accounts.json         : {username: {salt, password_hash, created}}
#   - saves/<username>.json : that account's game state (see _DEFAULT_SAVE)
#   - active_account.json   : which account the *client* is currently
#                             playing as - there's no per-request way to
#                             know this, since the SWF always sends the same
#                             hardcoded userId regardless of who's logged
#                             into the website (that's baked into Flow.as
#                             and would need its own AS3 patch to change).
#                             So "logged in" here means "this is who
#                             Start_Game.bat's *next* launch plays as",
#                             chosen on the website before you start the
#                             game - not a live multi-user session.
#
# Persisted now: account identity, tutorial state, profile values, and the
# building add/move/sell actions sent through services.I2012. The queue is
# decoded in amf.py and exact tile positions are returned via I2001.
# Battle completion is still not persisted: no playable TD battle module is
# wired up in this offline build, so there is no result to save yet.
_ACCOUNTS_PATH = os.path.join(HERE, "accounts.json")
_SAVES_DIR = os.path.join(HERE, "saves")
_ACTIVE_ACCOUNT_PATH = os.path.join(HERE, "active_account.json")
_AVATARS_DIR = os.path.join(HERE, "avatars")
# friends.json is owned by launcher.py (Add Friend button, accept/decline
# flow - see that file's own comment above its data layer) - server.py only
# ever reads it, to answer services.I1003 with the current account's
# accepted friends. Same shape launcher.py writes: {username: {"friends":
# [...], "incoming": [...], "outgoing": [...]}}.
_FRIENDS_PATH = os.path.join(HERE, "friends.json")

# Active TD battle sessions.  I4002 records which mission a battle UUID belongs to;
# I4003 can therefore persist the completed mission even though the original
# completion call sends the UUID rather than the mission id.
_BATTLE_SESSIONS = {}
_BATTLE_SESSIONS_LOCK = threading.Lock()

_DEFAULT_SAVE = {
    "tutorialStep": 1,        # DataManager.TUTORIAL_STEP_BUY_HOUSE
    "skippedTutorial": None,  # None = not finished yet, True = Cancel, False = Accept
    "money": 4500,
    "gems": 500,
    "level": 1,
    "experience": 0,
    "houses": [],         # placeholder - not wired up yet, see comment above
    # Completed TD mission ids.  The mission UI reads these through
    # pvzData.unlocks["5"], so keep the authoritative list in the per-account save.
    "levelsFinished": [],
    # Persistent progression: missions already won and plant cards earned from
    # those wins.  The first two plants are the tutorial starting cards.
    "unlockedLevels": [1],
    "unlockedPlants": [12, 2],
    "ownedBuildings": [], # resourceIds bought via services.I5001 - see that handler
    "placedBuildings": [], # {resourceId, position, buyId, level} - decoded from
                           # services.I2012's queue, see that handler
    "nextBuildingId": 1000000,
    "ownedFunctionCards": [], # resourceIds of the 5 funchouse cards bought via
                              # services.I5001 - see that handler
    "decorations": [],       # persistent town decoration groups: {id, tid, level, layout}
    "nextDecorationId": 2000000,
    # The starting build zone is a 12x12 tile rectangle made from the
    # four original 6x6 plots around the first house: areas 8, 9, 12 and 13.
    # Everything else remains locked until purchased through TownBaseMap.
    "unlockedAreas": [8, 9, 12, 13],
}

# DataManager.TUTORIAL_STEP_COMPLETE (3) alone only satisfies
# isCompleteTutorial (tutorialStep >= 3), which is what gates the TD-tutorial
# confirm dialog and most things. But TownUIPanel.setBtTutorialState() and
# its neighbors check FOUR further bits independently, bitwise, to decide
# whether the citizen/shop/card/rampage buttons are visible at all
# (TUTORIAL_STEP_GOAL_BT=16, _CITIZEN_BT=32, _SHOP_BT=64, _CARD_BT=128,
# _RAMPAGE_BT=256 - confirmed by reading TownUIPanel.as directly, not just
# DataManager's constant list) - none of those bits are set by 3 alone, so
# without this, those buttons stay hidden even once the tutorial is
# otherwise "done". 3|16|32|64|128|256 = 499.
_TUTORIAL_COMPLETE_FULL = 3 | 16 | 32 | 64 | 128 | 256


def _load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def _write_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except OSError as e:
        print(f"[!] could not write {path}: {e}")


def load_accounts():
    return _load_json(_ACCOUNTS_PATH, {})


def _uid_for_username(username):
    """A stable, distinct numeric uid per account, required now that friends
    need to be distinguishable from each other - FriendManager.
    allFriendDataMap (client-side) is keyed by uid, so every account
    sharing one fixed value would collapse every friend into a single map
    entry. Deterministic (same username always yields the same uid across
    logins), not random. The not-logged-in local-save case keeps the
    original fixed value, since there's no username to derive from and no
    friends are reachable there anyway (see active_identity())."""
    return int(hashlib.md5(username.encode("utf-8")).hexdigest(), 16) % 900000000 + 100000000


def friends_of_active_account():
    """Read-only: the active account's accepted friends, each resolved to a
    FriendVO-compatible dict (uid, name, level, thumbnail) using the same
    per-friend save/avatar files server.py already reads for the local
    player. Returns [] whenever there's no active account (local-save
    sessions have no accounts.json entry to befriend, or be befriended by)
    or friends.json doesn't exist yet."""
    username = get_active_account()
    if not username:
        return []
    accounts = load_accounts()
    entry = _load_json(_FRIENDS_PATH, {}).get(username)
    if not isinstance(entry, dict):
        return []
    result = []
    for friend_username in entry.get("friends", []):
        if friend_username not in accounts:
            continue  # deleted since becoming friends - skip silently
        friend_save = load_save(friend_username)
        thumbnail = ""
        avatar_path = os.path.join(_AVATARS_DIR, f"{friend_username}.png")
        if os.path.isfile(avatar_path):
            version = int(os.stat(avatar_path).st_mtime)
            thumbnail = f"{_public_base_url()}avatars/{urllib.parse.quote(friend_username)}.png?v={version}"
        result.append({
            "uid": _uid_for_username(friend_username),
            "name": friend_username,
            "level": friend_save.get("level", 1),
            "thumbnail": thumbnail,
        })
    return result


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000).hex()
    return salt, digest


def verify_password(password, salt, expected_digest):
    _, digest = hash_password(password, salt)
    return hmac.compare_digest(digest, expected_digest)


_USERNAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,32}$")


def create_account(username, password):
    username = username.strip()
    if not username or not password:
        return False, "Username and password are both required."
    if not _USERNAME_RE.match(username):
        # saves/{username}.json is built directly from this string - without
        # this check, a username like "../../../../whatever" would let
        # registration write a save file outside _SAVES_DIR entirely.
        return False, "Username can only contain letters, numbers, - and _ (max 32 characters)."
    if len(password) < 4:
        return False, "Password must be at least 4 characters."
    accounts = load_accounts()
    if username in accounts:
        return False, "That username is already taken."
    salt, digest = hash_password(password)
    accounts[username] = {
        "salt": salt,
        "password_hash": digest,
        "created": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    _write_json(_ACCOUNTS_PATH, accounts)
    os.makedirs(_SAVES_DIR, exist_ok=True)
    save_path = os.path.join(_SAVES_DIR, f"{username}.json")
    if not os.path.exists(save_path):
        _write_json(save_path, dict(_DEFAULT_SAVE))
    return True, None


def check_login(username, password):
    accounts = load_accounts()
    account = accounts.get(username)
    if account is None:
        return False, "No account with that username."
    if not verify_password(password, account["salt"], account["password_hash"]):
        return False, "Wrong password."
    return True, None


# --------------------------------------------------------------------------
# Multi-device play: per-browser sessions + per-request identity
# --------------------------------------------------------------------------
# Every browser (PC, phone, tablet) that logs in on /accounts gets its own
# random session token, stored in a cookie and in sessions.json. /play hands
# that token to the SWF through the page's util.getSessionKey() - the same
# JavaScript hook the original Renren page used - and I1001 sends it to us
# as its second argument. We answer I1001 with popcapId = that token, and
# AmfCaller then prepends it (PVZNetConnection.POPCAP_ID) as the 3rd argument
# of EVERY later call. So each AMF body tells us which account it belongs
# to, without any SWF patch.
#
# Anything that doesn't carry a known web token (the Flash projector started
# by Start_Game.bat has no page, so it sends the built-in default key and
# gets popcapId "offline") falls back to active_account.json exactly as
# before - the launcher keeps working unchanged.
_SESSIONS_PATH = os.path.join(HERE, "sessions.json")
_WEB_TOKEN_PREFIX = "web_"
_state_lock = threading.RLock()   # serialises save/account/session file access
_request_ctx = threading.local()


def _load_sessions():
    data = _load_json(_SESSIONS_PATH, {})
    return data if isinstance(data, dict) else {}


def create_session(username):
    token = _WEB_TOKEN_PREFIX + secrets.token_hex(16)
    with _state_lock:
        sessions = _load_sessions()
        sessions[token] = {
            "username": username,
            "created": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        _write_json(_SESSIONS_PATH, sessions)
    return token


def delete_session(token):
    with _state_lock:
        sessions = _load_sessions()
        if sessions.pop(token, None) is not None:
            _write_json(_SESSIONS_PATH, sessions)


def session_username(token):
    """Username for a web session token, or None if unknown/expired or the
    account no longer exists."""
    if not isinstance(token, str) or not token.startswith(_WEB_TOKEN_PREFIX):
        return None
    entry = _load_sessions().get(token)
    if not entry:
        return None
    username = entry.get("username")
    return username if username in load_accounts() else None


def get_active_account():
    """Which account the current request is playing as.

    Inside an AMF body that carried a web session token (see the section
    comment above) this is that browser's account. Everywhere else it is
    the launcher's active_account.json, as it always was."""
    if getattr(_request_ctx, "scoped", False):
        return _request_ctx.username
    data = _load_json(_ACTIVE_ACCOUNT_PATH, {"username": None})
    return data.get("username")


def _public_base_url():
    """http://<host the client used>/ - so URLs we hand back (avatars) work
    from a phone too, not only on the PC itself (127.0.0.1)."""
    host = getattr(_request_ctx, "host", None) or f"127.0.0.1:{PORT}"
    return f"http://{host}/"


def lan_addresses():
    """Best-effort list of this PC's LAN IPv4 addresses."""
    found = []
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))   # no packet is actually sent
            found.append(s.getsockname()[0])
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip not in found:
                found.append(ip)
    except OSError:
        pass
    return [ip for ip in found if not ip.startswith("127.")]


def set_active_account(username):
    _write_json(_ACTIVE_ACCOUNT_PATH, {"username": username})


def active_identity():
    """Return the local identity fields consumed by FriendManager and the
    town header. The patched main.swf reads these fields during I1001, before
    TownUIPanel asks FriendManager for the town owner's name and thumbnail.

    uid MUST stay the fixed constant for every account, confirmed by
    reading Flow.as directly: the client hardcodes
    this.userId = 245953145 unconditionally, client-side, before the very
    first server call ever goes out (this was always going to be true
    offline - it's the ExternalInterface.call("util.getUserId") fallback
    path, which always fails with no browser bridge to call). commonModel.id
    gets set to that value immediately after. Every subsequent AmfCaller.
    onResult() then does `if(commonModel.id != 0 && obj.user != null) { if
    (user.uid != commonModel.id) return; ... }` - silently discarding the
    ENTIRE response, including I1001's login payload itself, whenever the
    server's stated uid doesn't match what the client already hardcoded
    itself to. A per-account derived uid here breaks login outright for
    every named account (confirmed live) - this field specifically has to
    match the client's own fixed value, not be genuinely unique.
    """
    username = get_active_account()
    if username not in load_accounts():
        username = None
    display_name = username or "Local Player"
    thumbnail = ""
    if username is not None:
        avatar_path = os.path.join(_AVATARS_DIR, f"{username}.png")
        if os.path.isfile(avatar_path):
            version = os.stat(avatar_path).st_mtime_ns
            thumbnail = (
                f"{_public_base_url()}avatars/"
                f"{urllib.parse.quote(username)}.png?v={version}"
            )
    return {
        "uid": 245953145,
        "name": display_name,
        "thumbnail": thumbnail,
    }


def load_save(username):
    if username is None:
        return _ensure_starter_area_open(dict(_DEFAULT_SAVE))
    path = os.path.join(_SAVES_DIR, f"{username}.json")
    merged = dict(_DEFAULT_SAVE)
    merged.update(_load_json(path, {}))
    return _ensure_starter_area_open(merged)


def write_save(username, **updates):
    if username is None:
        return dict(_DEFAULT_SAVE)
    os.makedirs(_SAVES_DIR, exist_ok=True)
    path = os.path.join(_SAVES_DIR, f"{username}.json")
    state = load_save(username)
    state.update(updates)
    _write_json(path, state)
    return state


# Separate from the accounts system entirely (not just saves/None.json or
# similar - a real registered username could otherwise collide with
# whatever sentinel we picked). This is what makes tutorial completion
# persist for the *default* way of playing - just running Start_Game.bat,
# no website visit needed - which is how every save/skip/accept this
# project has ever been tested with has actually been played. Logging into
# an account via the website is still supported and takes priority when
# active, but is no longer required for persistence to work at all.
_LOCAL_SAVE_PATH = os.path.join(HERE, "local_save.json")


def _ensure_starter_area_open(save):
    """Keep the 12x12 starter build zone free and buildable.

    The map is divided into 16 original 6x6 plots.  The first house is at
    tile position 316/320/321 on the upper-right side of the 12x12 rectangle
    formed by areas 8, 9, 12 and 13.  Those four plots therefore make up the free starting area.
    Area 0 was used by an earlier build as a separate free plot; migrate it
    away so an old save does not leave an extra, unintended free grid.
    Older/incomplete saves can carry an empty or malformed unlockedAreas
    value, so normalize them here.
    """
    raw = save.get("unlockedAreas", [8, 9, 12, 13])
    if not isinstance(raw, (list, tuple, set)):
        raw = [8, 9, 12, 13]
    normalized = set()
    for value in raw:
        try:
            area = int(value)
        except (TypeError, ValueError):
            continue
        if 0 <= area <= 15:
            normalized.add(area)
    # Area 0 was a legacy free plot, not part of the 12x12 starter zone.
    normalized.discard(0)
    normalized.difference_update((4, 5))
    normalized.update((8, 9, 12, 13))
    save["unlockedAreas"] = sorted(normalized)
    return save


def load_local_save():
    merged = dict(_DEFAULT_SAVE)
    merged.update(_load_json(_LOCAL_SAVE_PATH, {}))
    return _ensure_starter_area_open(merged)


def write_local_save(**updates):
    state = load_local_save()
    state.update(updates)
    _write_json(_LOCAL_SAVE_PATH, state)
    return state


def current_save():
    """The save file build_amf_response() should read from for whatever the
    game client is doing right now: the active website account's save if
    one is logged in, otherwise local_save.json (see its comment above)."""
    username = get_active_account()
    return load_save(username) if username is not None else load_local_save()


def write_current_save(**updates):
    """Write-side companion to current_save() - writes to whichever save
    current_save() would have read from."""
    username = get_active_account()
    return write_save(username, **updates) if username is not None else write_local_save(**updates)





# Every print() below (AMF request/response lines, 404 warnings, the build
# check) also gets written to server_log.txt, truncated fresh on each
# startup - so "what did the server log say" is a file you can attach
# instead of a console window you have to screenshot. See
# Export_Debug_Log.bat, which bundles this together with flashlog.txt into
# one file.
class _Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, data):
        for s in self.streams:
            s.write(data)

    def flush(self):
        for s in self.streams:
            s.flush()


_server_log_path = os.path.join(HERE, "server_log.txt")
_server_log_file = open(_server_log_path, "w", encoding="utf-8", buffering=1)
_server_log_file.write(
    f"=== PvZ server log - started {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n"
)
sys.stdout = _Tee(sys.stdout, _server_log_file)
sys.stderr = _Tee(sys.stderr, _server_log_file)

# Known-good hashes of the SWFs (and now conf_1_.xml) as last patched. If
# what's actually sitting in this folder doesn't match, you are NOT running
# the version you think you are - this has bitten us more than once, so the
# server checks and says so loudly on every startup instead of leaving it
# ambiguous.
#
# conf_1_.xml is in here now too - it silently carried the activityPanel
# fix and this check never noticed, because it only ever looked at the 3
# SWFs. That's almost certainly why the 966/967 crash and "Activity doesn't
# load" both got reported again after already being fixed: the 3 SWFs
# hadn't changed across those rounds (both were server.py/conf_1_.xml-only
# fixes), so this kept saying [OK] while conf_1_.xml was actually a stale
# copy from before those fixes.
#
# BUILD_LABEL is a plain, eyeballable marker for the same problem on the
# server.py side, which still can't hash-check itself: if what you paste
# into a message doesn't match the label mentioned in that reply, the file
# is stale, full stop - no need to compute anything.
BUILD_LABEL = "2026-10-06-rampage-panel-real-rampage"

EXPECTED_BUILD = {
    "main.swf": (578849, "273f4df24e717e5ebc1b2974cb025e4c"),
    "PVZEntry_1_.swf": (498126, "508e7aa404e2598fb1f27fef8b40da9d"),
    "townEntry_1_.swf": (480919, "9639ac0d85eb1dbc86ae06008d74bda1"),
    "itemShop.swf":     (427447, "8d5e97f5667580d05a7e3fee224d0b18"),
    "pvzTD_1_.swf": (1705693, "4b5712664922a7bd5747842f61543652"),
}


def check_build():
    print("=========================================================")
    print(f" Build check - server.py BUILD_LABEL: {BUILD_LABEL}")
    print("=========================================================")
    all_ok = True
    for fname, (exp_size, exp_md5) in EXPECTED_BUILD.items():
        if not os.path.exists(fname):
            print(f"  [MISSING]  {fname} - not found in this folder at all!")
            all_ok = False
            continue
        actual_size = os.path.getsize(fname)
        actual_md5 = hashlib.md5(open(fname, "rb").read()).hexdigest()
        if actual_size == exp_size and actual_md5 == exp_md5:
            print(f"  [OK]       {fname} matches the latest patched build")
        else:
            print(f"  [MISMATCH] {fname} is NOT the file I last sent you!")
            print(f"             This is an old/different copy - replace it.")
            all_ok = False
    if not all_ok:
        print()
        print("  >>> At least one file above is stale. Delete this whole")
        print("  >>> folder and do a completely fresh extract of the zip -")
        print("  >>> don't copy individual files over an existing folder.")
    print("=========================================================\n")

# Garden/seed items. PlantBuilding extends Building, so planting one goes
# through the exact same Data.instance.itemConfArr mechanism buying the
# house did - same "size" string-not-array gotcha applies. On top of that,
# PlantBuilding.initSkin() ALSO needs bigImg (a generic soil/water tile
# background) and mcSourceName (the specific plant's own swf, e.g.
# "Plant_Sunflower.swf"). The soil/water backgrounds ARE present - checked
# directly with ffdec's link report - in townUI_1_.swf, one of the files
# already loaded for every town. The per-plant swfs are supplied in the project root and are loaded by
# their mcSourceName; Cherry Bomb is now supplied as a compiled town-plant
# SWF built from the provided CherryBomb FLA animation source.
_SEED_DEFS = {
    # resourceId: (mcSourceName, bigImg) - both read directly from GamePropItem_1_.xml
    101: ("Plant_Sunflower.swf", "Plant_Soil_Bg_Mc"),
    102: ("Plant_Peashooter.swf", "Plant_Soil_Bg_Mc"),
    103: ("Plant_SunShroom.swf", "Plant_Soil_Bg_Mc"),
    104: ("Plant_Wallnut.swf", "Plant_Soil_Bg_Mc"),
    106: ("Plant_CherryBomb.swf", "Plant_Soil_Bg_Mc"),
    107: ("Plant_LilyPad.swf", "Plant_Water_Bg_Mc"),  # the one water plant
    111: ("Plant_PotatoMine.swf", "Plant_Soil_Bg_Mc"),
    115: ("Plant_Squash.swf", "Plant_Soil_Bg_Mc"),
    116: ("Plant_Jalapeno.swf", "Plant_Soil_Bg_Mc"),
    105: ("Plant_SnowPeashooter.swf", "Plant_Soil_Bg_Mc"),
    118: ("Plant_Repeater.swf", "Plant_Soil_Bg_Mc"),
}

# Seeds that have real town art (Plant_*.swf in the game folder, made by the
# user's friend - see PLANT_ART.txt). These become buyable once the tutorial
# is finished; during the tutorial only TUTORIAL_SEED_RESOURCE_ID is.
_SEEDS_WITH_ART = (101, 102, 103, 104, 105, 106, 107, 111, 115, 116, 118)
# 103 Sun-shroom, 104 Wall-nut, 107 Lily Pad, 111 Potato Mine, 115 Squash and
# 116 Jalapeno got garden art (Plant_*.swf, class TownPlant_*) generated from
# the PvZ 1 FLAs in the original Social crop-field layout, so every seed the
# server defines can be planted, saved (I2012 action 9) and restored (I2001).

# The battle/almanac plant card id and the town seed-packet resource id are
# different ids.  Keep their relationship explicit so the same plant can be
# resolved consistently in the Almanac, the Adventure card selector, and the
# town seed system.  The seed ids come from GamePropItem_1_.xml; the plant ids
# come from conf/PlantData.xml.
_PLANT_TO_SEED_RESOURCE = {
    12: 102,  # Peashooter
    2: 101,   # Sunflower
    17: 106,  # Cherry Bomb
    9: 104,   # Wall-nut
    18: 111,  # Potato Mine
    16: 105,  # Snow Pea
    20: 114,  # Chomper
    13: 109,  # Puff-shroom
    14: 112,  # Fume-shroom
    24: 118,  # Repeater
    1: 103,   # Sun-shroom
    15: 119,  # Scaredy-shroom
    5: 120,   # Grave Buster
    4: 107,   # Lily Pad
    22: 115,  # Squash
    21: 113,  # Spikeweed
    25: 116,  # Jalapeno
    8: 138,   # Torchwood
    19: 108,  # Sea-shroom
    7: 121,   # Coffee Bean
    10: 123,  # Pumpkin
    41: 131,  # Melon-pult
    6: 124,   # Magnet-shroom
    33: 127,  # Blover
    27: 125,  # Cactus
    11: 122,  # Tall-nut
}

# How long a planted seed takes to grow, and how that time is split between
# the three stages the art has (conf_1_.xml <plantAnimator>: seedling,
# growing, grown). "stage:fraction" pairs, read by GardenUtils.getGrowthStatus.
_SEED_GROW_SECONDS = 300
_DEFAULT_PLANT_CAPACITY = 10   # how many seed plots a town can hold
_SEED_GROWTH_CHAIN = "1:0.3,2:0.4,3:0.3"



# Tutorial seed gating. The user identified their item_12 reference card
# (GamePropItem_1_.xml resourceId 12, name "豌豆射手" - "Peashooter, your
# first line of defense" - an almanac-style entry, category 2, no
# mcSourceName) as the one plant allowed during the town tutorial. That's
# NOT a seed-shop resourceId on its own - the actual purchasable/plantable
# seed for the same plant is resourceId 102 ("豌豆射手的种子" / "Peashooter's
# Seed", category 0 = CATEGORY_GARDEN, mcSourceName Plant_Peashooter.swf),
# which is already one of the 9 entries in _SEED_DEFS below. So the gate is
# expressed as: only 102 stays active; the other 8 seeds are hidden from
# the shop entirely (ItemShopUI.initData() only lists items where
# Boolean(item.active) is true - confirmed at ItemShopUI.as:502 - so a
# false entry here just never appears as a listing, it's not a locked/
# greyed-out state). i1001_payload()'s "items" field only ever grants the
# one FuncHouse card added below (ITEM_TYPE_CARD, unrelated to seeds) -
# no ITEM_TYPE_SEED entries are ever granted directly, so the shop is
# still the only way to ever acquire a seed packet, meaning hiding the
# other 8 here is sufficient to guarantee only Peashooter can ever be
# placed anywhere, tutorial house included -
# confirmed by reading TownEntry.loadBuildingConf(): it builds
# Data.instance.itemConfArr from itemTypeConfigMap purely off each entry's
# "size" field, with no active check of its own, so the shop-visibility
# gate here is the only (and correct) place to enforce this.
TUTORIAL_SEED_RESOURCE_ID = 102  # Peashooter - matches the user's item_12 card


def _seed_item_settings():
    """itemSettings["1"] (ITEM_TYPE_SEED) entries for the 9 garden seeds.
    Feeds both propItemsConfigMap (shop display - though the shop icons for
    these were already confirmed wired via imgList before any of this
    session's fixes) and itemConfArr (needed to actually plant one).

    Only TUTORIAL_SEED_RESOURCE_ID is active for now - the other 8 are
    hidden from the shop (see note above). Flip more of these back to
    True once the user wants additional seeds available post-tutorial."""
    save = current_save()
    tutorial_done = int(save.get("tutorialStep", 0) or 0) >= 3
    out = {}
    for seed_id, (mc_source, big_img) in _SEED_DEFS.items():
        out[str(seed_id)] = {
            "id": seed_id,
            "resourceId": seed_id,
            "type": 1,          # ITEM_TYPE_SEED
            "active": (seed_id == TUTORIAL_SEED_RESOURCE_ID
                       or (tutorial_done and seed_id in _SEEDS_WITH_ART)),
            "money": 25,        # coin price - placeholder, not from any source data
            "sellType": 0,      # DataManager.MONEY_TYPE_COIN
            "discount": "1",
            "onShelfTime": "0",
            "offShelfTime": "0",
            "status": 1,
            "recommend": 0,
            "level": 1,
            "size": "1,1",       # a single growing-plot tile, not 2x2 like the house -
                                # MUST still be a comma string, not an array (see 701's note)
            "bigImg": big_img,
            "mcSourceName": mc_source,
            # PlantBuilding.onGetPlantSwf() reads this directly
            # (itemConfArr[id].movieClipName, NOT XML-merged, same rule as
            # every other itemConfArr-only field) to find the plant's real
            # MovieClip symbol once mcSourceName's swf finishes loading -
            # Reflection.createMovieClip(undefined, ...) when this was
            # missing returned null with no guard anywhere in the chain
            # down to BitmapUtil.drawMovieClip(), which is where the #1009
            # actually surfaced. Confirmed via GamePropItem_1_.xml: for
            # every one of these resourceIds, movieClipName is always
            # exactly mcSourceName with ".swf" stripped - not a coincidence
            # worth hand-listing separately, so it's derived here instead.
            "movieClipName": _town_plant_class(mc_source),
        }
    return out


def _swf_exported_classes(path):
    """Class names a SWF exports (SymbolClass tag), or [] if unreadable."""
    import zlib, struct as _st
    try:
        with open(path, "rb") as f:
            d = f.read()
        body = zlib.decompress(d[8:]) if d[:3] == b"CWS" else d[8:]
        nb = body[0] >> 3
        p = (5 + 4 * nb + 7) // 8 + 4
        names = []
        while p + 2 <= len(body):
            h = _st.unpack_from("<H", body, p)[0]; code = h >> 6; ln = h & 63; p += 2
            if ln == 63:
                ln = _st.unpack_from("<I", body, p)[0]; p += 4
            if code == 76:
                b = body[p:p + ln]; n = _st.unpack_from("<H", b)[0]; q = 2
                for _ in range(n):
                    q += 2; e = b.index(b"\0", q); names.append(b[q:e].decode("utf-8", "replace")); q = e + 1
            if code == 0:
                break
            p += ln
        return names
    except Exception:
        return []


_TOWN_PLANT_CLASS_CACHE = {}


def _town_plant_class(mc_source):
    """movieClipName for a garden-plot plant: the class its SWF really exports.

    PlantBuilding loads mcSourceName (e.g. Plant_CherryBomb.swf) and then
    looks up movieClipName in it; a mismatch gives Error #1009 in
    BitmapUtil.drawMovieClip. Garden SWFs may export Plant_X (original) or
    TownPlant_X (renamed so they never clash with the battle art), so read
    the SWF instead of guessing."""
    base = mc_source[:-4] if mc_source.endswith(".swf") else mc_source
    if base in _TOWN_PLANT_CLASS_CACHE:
        return _TOWN_PLANT_CLASS_CACHE[base]
    choice = _TOWN_PLANT_CLASS_RENAMES.get(base, base)
    for folder in ("", os.path.join("swf", "20130627", "town", "plants"), os.path.join("local", "swf", "v1")):
        path = os.path.join(HERE, folder, base + ".swf")
        if os.path.exists(path):
            names = _swf_exported_classes(path)
            rest = base[len("Plant_"):] if base.startswith("Plant_") else base
            for cand in ("TownPlant_" + rest, base):
                if cand in names:
                    choice = cand
                    break
            break
    _TOWN_PLANT_CLASS_CACHE[base] = choice
    return choice


# The garden-plot SWFs used to export classes with the SAME names the battle
# art (pvzTD_1_.swf) uses for its plants (Plant_Peashooter, Plant_Sunflower,
# Plant_Repeater). Flash keeps the first definition of a class name, so after a
# battle had loaded, the town plots showed the battle sprites. The plot SWFs'
# classes are now renamed TownPlant_* (GamePropItem_1_.xml movieClipName too);
# the SWF file names are unchanged.
_TOWN_PLANT_CLASS_RENAMES = {
    "Plant_CherryBomb": "TownPlant_CherryBomb",
    "Plant_Peashooter": "TownPlant_Peashooter",
    "Plant_Sunflower": "TownPlant_Sunflower",
    "Plant_Repeater": "TownPlant_Repeater",
    "Plant_CherryBomb": "TownPlant_CherryBomb",
}



# FuncHouseCardSelectPanel "equip a card" system - completely separate from
# the garden seed shop above. Opened from the practice house's "强化"
# (Strengthen) tab in the citizen list, NOT from clicking the house on the
# map (that path goes through TownFlow.onClickFunctionBld() straight to
# TownTutorialFlow.showTdTutorialConfirmDialog() instead - see the big
# note on i1023_payload() below for how this system fits into the
# tutorial, or rather doesn't).
#
# FuncHouseCardSelectPanel.updateData() only pushes a card into the
# visible list if its id passes TWO separate checks: it must be listed
# under buffHouseCardsSettings[<buildingId>] (i1023_payload(), per
# building) AND it must be in DataManager.ownCardsData (built from this
# i1001 payload's "items"["0"] list - ITEM_TYPE_CARD). CardPolicy then
# resolves what the card actually DISPLAYS via
# PropItemsManager.getPropItemConfig(id).groupId - confirmed by reading
# CardPolicy.getCardPlantId() and FuncHouseCard.init(), both of which do
# imgList["item_" + groupId] - so groupId, not id/resourceId, is what
# points a card at its art.
#
# groupId=12 (the user's original item_12 reference card, GamePropItem_1_.xml
# resourceId 12, "豌豆射手") was the first thing tried here and is WRONG -
# confirmed by decompressing config.gz and reading build_config.py's
# img_entries(): imgList is built by globbing this project's OWN
# item_*.png files, and item_12_1_.png simply isn't one of them (only
# item_101/102/103/104/106/107/111/115/116, the 653-672/1006-1014/
# 1151-1157/1201 range, and 1201 exist - confirmed by listing the project
# root directly). ImageManager.loadImage() on a missing imgList entry
# fails silently (this project's established degrade-gracefully pattern),
# so the card slot existed but rendered with no visible bitmap - not a
# crash, just invisible. groupId=102 instead targets item_102
# ("豌豆射手的种子" - Peashooter's Seed), which IS a real file
# (item_102_1_.png) already confirmed working in the garden shop, and is
# the same plant besides.
#
# _FUNC_HOUSE_CARD_ID (9001) is a synthetic placeholder id: max real
# resourceId anywhere in GamePropItem_1_.xml is 1408, and nothing in the
# 9000s is used by the original game data, so this can't collide with
# anything real. No source data exists for what id the original game
# actually used for a plain FuncHouse buff card - the existing "碎片盒"
# (fragment box, e.g. item_1007) and minigame-jar items (e.g. item_655)
# in GamePropItem_1_.xml are both confirmed-different systems (card
# compose-from-fragments, and Rampage/Vasebreaker jar bonuses), not this.
_FUNC_HOUSE_CARD_ID = 9001


def _func_house_card_settings():
    """itemSettings["0"] (ITEM_TYPE_CARD - confirmed at DataManager.as:110,
    NOT to be confused with ItemShopUI.CATEGORY_GARDEN which is also 0 in
    a completely different dict). One entry: the user's requested
    Peashooter card for the practice house's card-select panel."""
    return {
        str(_FUNC_HOUSE_CARD_ID): {
            "id": _FUNC_HOUSE_CARD_ID,
            "resourceId": _FUNC_HOUSE_CARD_ID,
            "type": 0,        # ITEM_TYPE_CARD
            "groupId": 102,   # -> imgList["item_102"], a REAL file (see note above)
            # FuncHouse.resetToolTips() reads
            # propItemsConfigMap.get(curSelectCardId).name directly once a
            # card is equipped - since 9001 is synthetic (no
            # GamePropItem_1_.xml entry, so no XML-merge name), that showed
            # up as the literal string "undefined" in the tooltip without
            # this hand-supplied field.
            "name": "豌豆射手的种子",
        }
    }


# Plants are unlocked by (1) beating levels (_PLANT_REWARDS_BY_NAME),
# (2) buying the card from the almanac for 199 gems (below).
_PLANT_GEM_PRICE = 199
_MONEY_TYPE_GEM = 1      # DataManager.MONEY_TYPE_GEM (COIN is 0) - unverified, see PLANT_UNLOCK_RULES.txt


def _buy_plant_with_gems(pid):
    """Unlock plant card ``pid`` for _PLANT_GEM_PRICE gems.
    Returns True on success (also when already owned, without charging)."""
    if pid not in _PLANT_ALMANAC_IDS:
        return False
    save = _normalize_progress(current_save())
    owned = set(save["unlockedPlants"])
    if pid in owned:
        return True
    gems = int(save.get("gems", 0) or 0)
    if gems < _PLANT_GEM_PRICE:
        print(f"[save] plant {pid} denied: need {_PLANT_GEM_PRICE} gems, have {gems}")
        return False
    owned.add(pid)
    write_current_save(gems=gems - _PLANT_GEM_PRICE, unlockedPlants=sorted(owned))
    print(f"[save] plant {pid} bought for {_PLANT_GEM_PRICE} gems")
    return True


# Plant almanac cards - resourceIds confirmed as real GamePropItem_1_.xml
# entries (category 2, img="item_N", bigImg="CardBigImage_N", both files
# now present) - see conf/PlantData.xml for the matching <plant> elements.
# Unlike the FuncHouse card above, ComposeCardsContainer.setCardsWithPage()
# reads levelRequired/money/sellType/type DIRECTLY off
# propItemsConfigMap.get(id) (not via CardPolicy.getCardPlantId()/groupId -
# that indirection is specific to FuncHouseCard/ActivityPanel, not this
# panel), and gets img/bigImg/name/category/desc from the XML merge
# automatically since these resourceIds already exist in
# GamePropItem_1_.xml - so no groupId needed here, just these four raw
# fields. levelRequired=0 and money=0 keep every card unconditionally
# viewable rather than gating any of them behind a level/price - see
# ownCardsData below for the other half of "shows as unlocked".
_PLANT_ALMANAC_IDS_FALLBACK = [12, 2, 17, 9, 18, 20, 24, 13, 15, 16, 1, 14, 5, 4, 22, 21, 23, 8, 19, 25, 7, 11, 10, 6, 33, 41, 27, 71, 38, 73, 74, 75, 3, 42, 43, 45, 57, 76]


def _load_plant_almanac_ids():
    """Every <plant ... isDisplay="1"> id in conf/PlantData.xml, in positionId order.

    The Almanac (ComposeCardsContainer.setCardsWithPage) shows every
    isDisplay="1" plant and looks each one up in propItemsConfigMap by its
    PlantData id. Any displayed plant missing from this list has no item
    config, so the client reads a property of null (Error #1009) the moment
    the Almanac opens or the page buttons are pressed. That happened with
    Blover (id 33), displayed at positionId 25 but left out of the old
    hand-written list. Reading the list from PlantData.xml keeps the two in
    step. Falls back to the hand-written list if the XML can't be read."""
    try:
        import re as _re
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "conf", "PlantData.xml"),
                  encoding="utf-8-sig") as f:
            xml = f.read()
        found = []
        for tag in _re.findall(r"<plant\s[^>]*>", xml):
            if not _re.search(r'isDisplay="1"', tag):
                continue
            pid = _re.search(r'\sid="(\d+)"', tag)
            pos = _re.search(r'positionId="(\d+)"', tag)
            if pid:
                found.append((int(pos.group(1)) if pos else 9999, int(pid.group(1))))
        ids = [pid for _, pid in sorted(found)]
        if ids:
            missing = sorted(set(_PLANT_ALMANAC_IDS_FALLBACK) - set(ids))
            print(f"[ALMANAC] {len(ids)} displayed plants read from conf/PlantData.xml"
                  + (f" (not displayed: {missing})" if missing else ""))
            return ids
    except Exception as e:
        print(f"[ALMANAC] could not read conf/PlantData.xml ({e}); using built-in list")
    return list(_PLANT_ALMANAC_IDS_FALLBACK)


_PLANT_ALMANAC_IDS = _load_plant_almanac_ids()

# Every zombieId we have real card art for (zombieCard_N files) and a real
# <Zombie> entry for in conf/ZombieData.xml. 10 of these (2,4,5,7,8,9,10,11,
# 13,101) also have a zombieBigImage_N detail-view file; the rest fall back
# to a missing (blank, non-crashing) detail image, same graceful-degradation
# pattern as plants without a CardBigImage.
_ZOMBIE_ALMANAC_IDS = [2, 3, 4, 5, 7, 8, 9, 10, 11, 13, 14, 15, 16, 18, 19, 20,
                       26, 34, 36, 101]


def _plant_almanac_card_settings():
    return {
        str(rid): {
            "id": rid,
            "resourceId": rid,
            "groupId": rid,        # PlantData id used by CardPolicy.getCardPlantId()
            "plantId": rid,
            "seedId": _PLANT_TO_SEED_RESOURCE.get(rid, 0),
            "seedResourceId": _PLANT_TO_SEED_RESOURCE.get(rid, 0),
            "seedPacketId": _PLANT_TO_SEED_RESOURCE.get(rid, 0),
            "type": 0,           # ITEM_TYPE_CARD
            "levelRequired": 0,
            "money": _PLANT_GEM_PRICE,   # buy a locked plant straight from the almanac
            "sellType": _MONEY_TYPE_GEM,
            # CardDetailPanel.enterContainer() reads this directly
            # (cardItemObj.earlyUnlockCost, no String() wrapper unlike every
            # sibling assignment in that function) - missing entirely
            # before, which is what threw Error #2007 the moment any card
            # was opened. 0 = nothing to pay to "early unlock" (there's no
            # unlock gate here to begin with - see ownCardsData).
            "earlyUnlockCost": 0,
            # ItemShopUI.initData() checks String(item.onShelfTime) != "0"
            # && String(item.offShelfTime) != "0" to decide whether to treat
            # an item as having a scheduled shelf window - with these missing
            # entirely, String(undefined) != "0" is true, so it incorrectly
            # entered that branch and fed "undefined" to a date parser
            # (GardenUtils.parseStringToDate), confirmed live. Buildings
            # already had "0" here; cards never did. "0" means "no schedule",
            # matching every other item in this project.
            "onShelfTime": "0",
            "offShelfTime": "0",
            # ItemShopListItem.setData() calls this.data.discount.split(".")
            # directly (no guard at all) whenever discount isn't exactly "1"
            # or "0" - a MISSING discount field is neither, so it entered
            # that branch and called .split() on undefined, confirmed live
            # (#1010). "1" means "no discount", same as buildings.
            "discount": "1",
            # setData() also reads status (gotoAndStop(int(status)), several
            # STATUS_* comparisons) and ownCountLimit (isFullOwnItemLimit) -
            # missing ownCountLimit specifically reproduces the exact
            # "always shows sold out" bug already found and fixed for
            # building 701 earlier in this project (0 >= undefined-as-0 is
            # true). Matching buildings' values exactly rather than waiting
            # to discover each gap one crash at a time.
            "status": 1,          # ItemShopUI.STATUS_NORMAL
            "ownCountLimit": 99,
        }
        for rid in _PLANT_ALMANAC_IDS
    }


# The 5 "funchouse" function-buff items (real GamePropItem_1_.xml data,
# category=6/CATEGORY_FUNCTION - the shop's "强化" tab, which is exactly
# where these already sort themselves via the XML merge, same as every
# other real-data item in this project). These are cards, same ITEM_TYPE_CARD
# mechanism as the plant almanac cards and the practice house's card - the
# difference is these ARE meant to be bought directly from the shop (not
# just owned/displayed), so unlike the almanac cards they need active=true
# and a real price, and their purchase needs to be recognized by the I5001
# handler below. Each of these has 2 further upgrade tiers in the real data
# (e.g. 952/953 for 951) with the same category=-1/no-further-data pattern
# already established for buildings - not wired up here, matching the
# "base tier only, no upgrade path yet" scope of this pass.
_FUNCTION_CARD_PRICES = {951: 800, 954: 900, 957: 1000, 960: 1100, 963: 1200}


def _function_card_settings(is_tutorial_done):
    return {
        str(rid): {
            "id": rid,
            "resourceId": rid,
            "type": 0,        # ITEM_TYPE_CARD
            "active": is_tutorial_done,
            "levelRequired": 0,
            "money": price,
            "sellType": 0,
            "earlyUnlockCost": 0,  # see _plant_almanac_card_settings's note on why
            "onShelfTime": "0",    # see _plant_almanac_card_settings's note on why
            "offShelfTime": "0",
            "discount": "1",       # see _plant_almanac_card_settings's note on why
            "status": 1,           # ItemShopUI.STATUS_NORMAL
            "ownCountLimit": 99,
        }
        for rid, price in _FUNCTION_CARD_PRICES.items()
    }


# Upgrade materials referenced by conf/PlantData.xml's <upgradeConfig> table
# (materialRequest="9002:1", protectionRequest="9003:1") -
# CardDetailPanel.onFillMaterial()/getPropItemConfig(id).money is what the
# "补齐" (fill) button charges gems against, .name is what's displayed next
# to the "0/N" counter. Synthetic ids (see _FUNC_HOUSE_CARD_ID's note on
# why - no real data exists for this whole upgrade-materials system, it's
# not in GamePropItem_1_.xml at all). Not granted to the player (no "items"
# entry) - starting at 0 owned is correct, matches the "0/1" reference
# screenshot exactly, and getPropNum() handles an ungranted id safely
# (returns 0, doesn't require a pre-existing ownership record).
_UPGRADE_MATERIAL_IDS = {
    9002: ("培养液", 50),          # Cultivation Fluid
    9003: ("防降级保护药", 100),   # Anti-Downgrade Protection Potion
}


def _upgrade_material_settings():
    return {
        str(mid): {
            "id": mid,
            "resourceId": mid,
            "type": 2,   # ITEM_TYPE_MATERIAL
            "name": name,
            "money": money,
            "sellType": 0,
        }
        for mid, (name, money) in _UPGRADE_MATERIAL_IDS.items()
    }


# Additional houses and shop buildings, per the user's request to add "the
# other houses and shop buildings ... like funchouse and jprestaurant".
# All resourceId/sourceName/bigImg values below are real, straight from
# GamePropItem_1_.xml (unlike 701, which has no XML entry at all and had to
# be hand-built) - these DO have matching <Item resourceId="..."> entries,
# so PropItemsManager.resetConfigMap()'s XML merge will pick up their real
# name/img/category/desc automatically (confirmed: itemList.(@resourceId==
# ...) finds a match, so HashMap.XML2Object merges the XML node onto this
# entry) - no need to hand-supply those fields the way 701 needed. Category
# is 7 (house) or 5 (shop) in the XML, both of which already match
# ItemShopUI.CATEGORY_HOUSE/CATEGORY_SHOP exactly (confirmed by reading
# ItemShopUI.as directly), so they'll sort into the right shop tabs with no
# extra work either.
#
# What's still hand-supplied here, same as 701 and for the same reasons
# (none of this is in the XML at all, only itemSettings-side data reaches
# itemConfArr/the actual buy-and-place flow - see 701's own comment above
# for the full "why" on each of these): subType 7 (BLD_TYPE_FUNC_HOUSE,
# the same class 701 already uses successfully), size (no real footprint
# data exists, so every building here uses the same "2,2" 701 already
# proved works, rather than guessing different sizes that could look
# visually wrong), ownCountLimit, and money (prices are simple placeholder
# numbers, not real balance data - they climb gently so the shop doesn't
# look flat, nothing more).
#
# Deliberately excluded: the "-1"-category entries for each of these (e.g.
# 707-710 are house2's own upgrade tiers) - those aren't separately
# purchasable in the real game either (ItemShopUI only lists
# category>=0), and there's no upgrade mechanic built here to unlock them
# through. Also excluded: funchouse1-5 (resourceIds 951-965) - despite the
# filename, GamePropItem_1_.xml's own data shows these are category=6
# (CATEGORY_FUNCTION) buff/booster items ("离子喷射增压器" - "ion jet
# booster", etc.), not architectural buildings - adding them as
# ITEM_TYPE_BUILDING would be the wrong item type for what they actually
# are.
#
# house4/house6/house5 (716/721/726) are labelled in their own XML desc
# text as challenge/survival/arena mode level-launchers respectively - none
# of those modes exist in this build. That's fine: these are subType 7
# (FuncHouse - no longer sharing that classification with 701, which is
# HOMES again, see its own comment above), and TownFlow.onClickFuncHouse()
# already treats every FuncHouse identically regardless of what it's
# "supposed" to do (opens the card-select panel once the tutorial's done)
# - so they behave exactly like any other building here, just
# decorative/placeable, rather than actually launching a mode that isn't
# implemented. These three are also what keeps CitizenListPanel's "强化"
# tab populated now that 701 no longer is.
# Each entry: base_id -> list of (resourceId, sourceName, bigImg, name) tiers,
# level 1 first. Real data straight from GamePropItem_1_.xml, cross-checked
# tier-by-tier against which SWF files actually exist in this project - 721
# and 726 reference house6_2.swf/house6_3.swf and house5_2/3/4.swf for their
# higher tiers, which were never provided, so those two chains stop at a
# single tier (not upgradeable) rather than pointing at a 404. Every other
# building keeps the same sourceName across all 5 tiers (only bigImg, the
# symbol picked out of that one swf, changes), which is why those chains are
# complete.
_UPGRADE_TIERS = {
    706: [(706, "house2.swf", "house2_1", "前院小木屋"), (707, "house2.swf", "house2_2", "前院木屋"),
          (708, "house2.swf", "house2_3", "前院小别墅"), (709, "house2.swf", "house2_3", "前院红瓦房"),
          (710, "house2.swf", "house2_3", "前院豪宅")],
    711: [(711, "house3.swf", "house3_1", "水池小木屋"), (712, "house3.swf", "house3_2", "水池木屋"),
          (713, "house3.swf", "house3_3", "水池小别墅"), (714, "house3.swf", "house3_3", "水池红瓦房"),
          (715, "house3.swf", "house3_3", "水池豪宅")],
    716: [(716, "house4.swf", "house4_1", "挑战道场"), (717, "house4.swf", "house4_2", "挑战道场"),
          (718, "house4.swf", "house4_3", "挑战道场"), (719, "house4.swf", "house4_3", "挑战道场"),
          (720, "house4.swf", "house4_3", "挑战道场")],
    721: [(721, "house6.swf", "house6_1", "生存墓室")],   # tier 2+ assets missing, single-level only
    726: [(726, "house5.swf", "house5_1", "僵尸竞技场")], # tier 2+ assets missing, single-level only
    821: [(821, "restaurant1.swf", "restaurant1_1", "热狗快餐车"), (822, "restaurant1.swf", "restaurant1_2", "热狗快餐车"),
          (823, "restaurant1.swf", "restaurant1_3", "热狗快餐车"), (824, "restaurant1.swf", "restaurant1_3", "热狗快餐车"),
          (825, "restaurant1.swf", "restaurant1_3", "热狗快餐车")],
    826: [(826, "icecream1.swf", "icecream1_1", "冰淇淋车"), (827, "icecream1.swf", "icecream1_2", "冰淇淋车"),
          (828, "icecream1.swf", "icecream1_3", "冰淇淋车"), (829, "icecream1.swf", "icecream1_3", "冰淇淋车"),
          (830, "icecream1.swf", "icecream1_3", "冰淇淋车")],
    831: [(831, "gasStation1.swf", "gasStation1_1", "汽车加油站"), (832, "gasStation1.swf", "gasStation1_2", "汽车加油站"),
          (833, "gasStation1.swf", "gasStation1_3", "汽车加油站"), (834, "gasStation1.swf", "gasStation1_3", "汽车加油站"),
          (835, "gasStation1.swf", "gasStation1_3", "汽车加油站")],
    836: [(836, "HRS1.swf", "HRS1_1", "24小时超市"), (837, "HRS1.swf", "HRS1_2", "24小时超市"),
          (838, "HRS1.swf", "HRS1_3", "24小时超市"), (839, "HRS1.swf", "HRS1_3", "24小时超市"),
          (840, "HRS1.swf", "HRS1_3", "24小时超市")],
    841: [(841, "motel1.swf", "motel1_1", "汽车旅馆"), (842, "motel1.swf", "motel1_2", "汽车旅馆"),
          (843, "motel1.swf", "motel1_3", "汽车旅馆"), (844, "motel1.swf", "motel1_3", "汽车旅馆"),
          (845, "motel1.swf", "motel1_3", "汽车旅馆")],
    846: [(846, "coffee1.swf", "coffee1_1", "咖啡小馆"), (847, "coffee1.swf", "coffee1_2", "咖啡小馆"),
          (848, "coffee1.swf", "coffee1_3", "咖啡小馆"), (849, "coffee1.swf", "coffee1_3", "咖啡小馆"),
          (850, "coffee1.swf", "coffee1_3", "咖啡小馆")],
    851: [(851, "CHRestaurant1.swf", "CHRestaurant1_1", "中国茶馆"), (852, "CHRestaurant1.swf", "CHRestaurant1_2", "中国茶馆"),
          (853, "CHRestaurant1.swf", "CHRestaurant1_3", "中国茶馆"), (854, "CHRestaurant1.swf", "CHRestaurant1_3", "中国茶馆"),
          (855, "CHRestaurant1.swf", "CHRestaurant1_3", "中国茶馆")],
    856: [(856, "pizza1.swf", "pizza1_1", "美味披萨店"), (857, "pizza1.swf", "pizza1_2", "美味披萨店"),
          (858, "pizza1.swf", "pizza1_3", "美味披萨店"), (859, "pizza1.swf", "pizza1_3", "美味披萨店"),
          (860, "pizza1.swf", "pizza1_3", "美味披萨店")],
    861: [(861, "hotel1.swf", "hotel1_1", "坚果连锁旅店"), (862, "hotel1.swf", "hotel1_2", "坚果连锁旅店"),
          (863, "hotel1.swf", "hotel1_3", "坚果连锁旅店"), (864, "hotel1.swf", "hotel1_3", "坚果连锁旅店"),
          (865, "hotel1.swf", "hotel1_3", "坚果连锁旅店")],
    866: [(866, "BarberShop1.swf", "BarberShop1_1", "疯狂美容美发"), (867, "BarberShop1.swf", "BarberShop1_2", "疯狂美容美发"),
          (868, "BarberShop1.swf", "BarberShop1_3", "疯狂美容美发"), (869, "BarberShop1.swf", "BarberShop1_3", "疯狂美容美发"),
          (870, "BarberShop1.swf", "BarberShop1_3", "疯狂美容美发")],
    871: [(871, "flower1.swf", "flower1_1", "阳光花店"), (872, "flower1.swf", "flower1_2", "阳光花店"),
          (873, "flower1.swf", "flower1_3", "阳光花店"), (874, "flower1.swf", "flower1_3", "阳光花店"),
          (875, "flower1.swf", "flower1_3", "阳光花店")],
    876: [(876, "JPRestaurant1.swf", "JPRestaurant1_1", "日式居酒屋"), (877, "JPRestaurant1.swf", "JPRestaurant1_2", "日式居酒屋"),
          (878, "JPRestaurant1.swf", "JPRestaurant1_3", "日式居酒屋"), (879, "JPRestaurant1.swf", "JPRestaurant1_3", "日式居酒屋"),
          (880, "JPRestaurant1.swf", "JPRestaurant1_3", "日式居酒屋")],
    881: [(881, "gym1.swf", "gym1_1", "健身房"), (882, "gym1.swf", "gym1_2", "健身房"),
          (883, "gym1.swf", "gym1_3", "健身房"), (884, "gym1.swf", "gym1_3", "健身房"),
          (885, "gym1.swf", "gym1_3", "健身房")],
    886: [(886, "supermarket1.swf", "supermarket1_1", "超级卖场"), (887, "supermarket1.swf", "supermarket1_2", "超级卖场"),
          (888, "supermarket1.swf", "supermarket1_3", "超级卖场"), (889, "supermarket1.swf", "supermarket1_3", "超级卖场"),
          (890, "supermarket1.swf", "supermarket1_3", "超级卖场")],
    # New, real FuncHouse buildings (subType 7) - added so the "强化" tab
    # keeps genuine content now that 701 is HOMES again (see its own
    # comment) and nothing else in this project is subType 7. Synthetic
    # resourceIds (9110+), same reasoning as 701 and the other hand-built
    # ids in this project: the real GamePropItem_1_.xml data for
    # 951/954/957/960/963 already models these as CATEGORY_FUNCTION cards,
    # not buildings (see _FUNCTION_CARD_PRICES's own comment) - reusing
    # those ids for a second, different item type would collide, so these
    # are separate ids entirely, not the same items reclassified. Only 2
    # tiers each - confirmed via ffdec's -export symbolclass against the
    # actual funchouse1-5 SWFs, which genuinely only contain funchouseN_1
    # and funchouseN_2 symbols (plus card-related symbols unrelated to
    # this), unlike the 5-tier pattern most other buildings use.
    9110: [(9110, "funchouse1.swf", "funchouse1_1", "强化屋1"), (9111, "funchouse1.swf", "funchouse1_2", "强化屋1")],
    9120: [(9120, "funchouse2.swf", "funchouse2_1", "强化屋2"), (9121, "funchouse2.swf", "funchouse2_2", "强化屋2")],
    9130: [(9130, "funchouse3.swf", "funchouse3_1", "强化屋3"), (9131, "funchouse3.swf", "funchouse3_2", "强化屋3")],
    9140: [(9140, "funchouse4.swf", "funchouse4_1", "强化屋4"), (9141, "funchouse4.swf", "funchouse4_2", "强化屋4")],
    9150: [(9150, "funchouse5.swf", "funchouse5_1", "强化屋5"), (9151, "funchouse5.swf", "funchouse5_2", "强化屋5")],
}

# subType per base id (unchanged from before - just no longer bundled with
# the tier art, which now lives in _UPGRADE_TIERS above)
_BUILDING_SUBTYPE = {706: 1, 711: 1, 716: 1, 721: 1, 726: 1,
                     821: 2, 826: 2, 831: 2, 836: 2, 841: 2, 846: 2, 851: 2,
                     856: 2, 861: 2, 866: 2, 871: 2, 876: 2, 881: 2, 886: 2,
                     9110: 7, 9120: 7, 9130: 7, 9140: 7, 9150: 7}

# Base (tier 1) price per building - unchanged values from the original
# _BUILDING_DEFS, not real balance data.
_BUILDING_BASE_MONEY = {706: 350, 711: 400, 716: 450, 721: 500, 726: 550,
                        821: 600, 826: 650, 831: 700, 836: 750, 841: 800,
                        846: 850, 851: 900, 856: 950, 861: 1000, 866: 1050,
                        871: 1100, 876: 1150, 881: 1200, 886: 1250,
                        9110: 600, 9120: 650, 9130: 700, 9140: 750, 9150: 800}

# Price lookup for services.I5001's purchase handler below - covers every
# building including 701 (whose own price lives in the building-701 dict
# entry inside i1001_payload(), not here, so it's listed separately here;
# all sold for coins, none of these are gem-priced). Only base (tier 1)
# prices - the other tiers are never bought through the shop, only reached
# by upgrading.
_ALL_BUILDING_PRICES = {701: 500}
_ALL_BUILDING_PRICES.update(_BUILDING_BASE_MONEY)


# Decoration items that have real art files in this offline project. The
# source XML already supplies the name/category/sourceName/bigImg/movieClipName
# metadata; these itemSettings entries add the fields the offline client needs
# in itemConfArr (type, size, price, and the normal shop flags). Decorations
# use ITEM_TYPE_DECORATIONS=3 and are bought by entering drag mode from the
# shop, then persisted through I2012's decoration queue actions.
#
# Only decorations whose source SWF is actually present are exposed here.
# This avoids putting shop entries on the shelf that would 404 at placement.
_DECORATION_DEFS = {
    # resourceId: (price, size)
    351: (50, "1,1"),   # stone road - RoadTileV1
    353: (75, "1,1"),   # asphalt road - RoadTileV4
    355: (75, "1,1"),   # brick road - RoadTileV2
    402: (100, "1,1"), # ordinary street lamp
    403: (125, "1,1"), # wrought-iron street lamp
    404: (150, "1,1"), # antique copper lamp
    452: (50, "1,1"),  # flower bed
    453: (50, "1,1"),  # grass clump
    454: (40, "1,1"),  # fence 1
    455: (100, "1,1"), # telephone booth
    456: (75, "1,1"),  # mailbox
    457: (75, "1,1"),  # park bench
    458: (60, "1,1"),  # cedar
    459: (60, "1,1"),  # golden maple
    460: (60, "1,1"),  # mulberry tree
    461: (60, "1,1"),  # flower bed 2
    462: (75, "1,1"),  # flower bed 3
    463: (75, "1,1"),  # flower bed 4
    465: (60, "1,1"),  # black pine
    470: (75, "1,1"),  # old oak
    471: (100, "1,1"), # sunflower totem
}


def _decoration_item_settings():
    out = {}
    for resource_id, (price, size) in _DECORATION_DEFS.items():
        out[str(resource_id)] = {
            "id": resource_id,
            "resourceId": resource_id,
            "type": 3,  # DataManager.ITEM_TYPE_DECORATIONS
            "active": True,
            "money": price,
            "sellType": 0,
            "status": 1,
            "discount": "1",
            "onShelfTime": "0",
            "offShelfTime": "0",
            "recommend": 0,
            "level": 1,
            "size": size,
            "ownCountLimit": 99,
            "greenPoints": 0,
        }
    return out


_ALL_DECORATION_PRICES = {rid: price for rid, (price, _size) in _DECORATION_DEFS.items()}


def _extra_building_settings(is_tutorial_done):
    """Every tier of every non-701 building. active is gated behind tutorial
    completion, same reasoning and same mechanism as TUTORIAL_SEED_RESOURCE_ID
    above: the shop's own active-filter (ItemShopUI.as -
    Boolean(item.active) && category>=0) is a pure visibility switch, so
    this hides these entirely rather than greying them out. Before this,
    all 19 were always active, which is exactly what let the tutorial's
    house-placement step render every house at once (confirmed live:
    getBldResUrl/getBitmap trace lines for ids 706, 711, 716, 721, 726 AND
    701 all fired from the same shop-tab render, not just 701) - 701 itself
    is untouched here (always active, handled entirely by its own dict
    entry above, same as always).

    UpgradeBldPanel.reset()/CitizenListPanel.onUpgradeBldResult() are what
    actually drive "leveling up": they search itemConfArr for an entry with
    a matching groupId (shared across every tier of one building), level ==
    currentLevel+1, AND active==true, then swap the placed instance to that
    resourceId's art - which is why every tier here carries the same
    groupId AND active=is_tutorial_done (not just tier 1 - an earlier
    version set tiers 2+ to active=False on the theory that only tier 1 is
    ever independently *bought* so the others didn't need shop visibility,
    which missed that this same active flag gates the upgrade search too,
    not just the shop - the result was every building reporting itself as
    already max level, confirmed live. Tiers 2+ still don't show up as
    separately-buyable shop items with active=true, because their real XML
    category (-1) independently keeps them off the shelf regardless -
    ItemShopUI's own display filter checks category>=0 as well as active).

    earlyUnlockCost is set on every tier (0, not real data) because
    UpgradeBldPanel.reset() assigns it to a TextField's .text unconditionally
    (line 165) even when the "early unlock" button stays hidden - confirmed
    by reading the function directly, this is the same never-String()-
    wrapped pattern that caused the almanac's Error #2007 earlier, so it's
    fixed here before it ever gets the chance to crash.

    levelRequired is deliberately left unset on every tier -
    UpgradeBldPanel.checkNeedUnlock() treats a missing levelRequired as "no
    unlock gate needed" and returns false immediately, which is what lets
    every upgrade skip the DataManager.pvzData["unlocks"]/services.I1014
    early-unlock system entirely - no real data exists for that system, and
    this avoids needing any."""
    out = {}
    for base_id, tiers in _UPGRADE_TIERS.items():
        sub_type = _BUILDING_SUBTYPE[base_id]
        base_money = _BUILDING_BASE_MONEY[base_id]
        for level, (resource_id, source_name, big_img, name) in enumerate(tiers, start=1):
            # Simple placeholder progression - not real balance data. Money/
            # income/exp/coolDown all scale gently with level so upgrading
            # is visibly worthwhile without needing real numbers.
            tier_money = int(base_money * (1 + 0.5 * (level - 1)))
            out[str(resource_id)] = {
                "id": resource_id,
                "resourceId": resource_id,
                "type": 4,          # ITEM_TYPE_BUILDING
                "active": is_tutorial_done,  # true on every tier, not just tier 1 - see
                                              # docstring: UpgradeBldPanel's next-tier
                                              # search requires active==true to find it,
                                              # and tier 2+'s real XML category (-1)
                                              # independently keeps them off the shop
                                              # shelf either way, so this is safe
                "money": tier_money,
                "sellType": 0,       # DataManager.MONEY_TYPE_COIN
                "status": 1,         # ItemShopUI.STATUS_NORMAL
                "discount": "1",
                "onShelfTime": "0",
                "offShelfTime": "0",
                "recommend": 0,
                "level": level,
                "groupId": base_id,  # shared across every tier - see docstring
                "earlyUnlockCost": 0,
                "subType": sub_type,  # GameConfig.BLD_TYPE_HOMES (1) or BLD_TYPE_BIZ (2) -
                                       # matches GamePropItem_1_.xml's own category for this id
                "size": "2,2",        # placeholder footprint, matches 701 (must be a string)
                "bigImg": big_img,
                "sourceName": source_name,
                "ownCountLimit": 99,
                # name/label/income/exp are read by FunctionalHouse's tooltip
                # code (Data.instance.itemConfArr[id].name/.label/.income) for
                # BLD_TYPE_BIZ buildings, and by TownFlow.onGetPrizeResult()
                # for the actual income/exp drop amounts - real per-tier
                # values, not just cosmetic, so they need to actually scale.
                # coolDown previously INCREASED with level (slower collection
                # the more you upgraded, backwards from what upgrading should
                # feel like) - now decreases instead, so a higher-level
                # building both pays out more AND is ready to collect from
                # again sooner. Floored at 600s (10 min) so it never becomes
                # trivially fast. Still placeholder economy, not real
                # balance data.
                "coolDown": max(600, int(3600 * (1 - 0.15 * (level - 1)))),
                "name": name,
                "label": name,
                "income": int(10 * (1 + 0.5 * (level - 1))) if sub_type == 2 else 0,
                "exp": int(5 * (1 + 0.5 * (level - 1))) if sub_type == 2 else 0,
            }
            if level > 1:
                # Real buildings get this from GamePropItem_1_.xml's own
                # data via the merge PropItemsManager.resetConfigMap() does
                # (see docstring above) - explicit here too so it no longer
                # silently depends on that merge alone, since the new
                # synthetic funchouse buildings (9110+) have no XML entry
                # at all and would otherwise show every tier as a
                # separately-buyable shop item instead of only reachable
                # by upgrading. Harmless for real buildings: matches what
                # the merge already sets there.
                out[str(resource_id)]["category"] = -1
    return out



def _plant_settings():
    """plantSettings -> DataManager.seedsConfigMap, a SEPARATE structure from
    itemSettings/itemConfArr entirely - ItemShopListItem.onClickItem() reads
    seedsConfigMap.get(id).cardId with no null check the moment you click
    ANY garden item, before even checking category, so every seed needs an
    entry here just to be clickable at all. cardId=0 deliberately bypasses
    an entire separate "own this card to unlock this seed" system that
    would otherwise gate every purchase - real game data for that doesn't
    exist here. growTime/yield are display-only placeholders (shown in the
    shop's "harvest in Xs for Y coins" description), not real balance data."""
    out = {}
    for seed_id in _SEED_DEFS:
        out[str(seed_id)] = {
            "cardId": 0,
            "greenConsumption": 1,
            "growTime": _SEED_GROW_SECONDS,
            "growthChain": _SEED_GROWTH_CHAIN,
            "yield": 10,
        }
    return out


def _seed_slot_unlock_rules():
    """UNLOCK_TYPE_CARD_SLOT (3) rules for the seed bar (the ITEM type of a slot is 10, the UNLOCK type is 3).

    SCardListTopPanel.refreshSlot() reads
    pvzData["unlockRules"]["3"][slotIndex]["levelRequired"] for slot 0..9.
    Without this table the seed-selection screen of every normal adventure
    level failed (#1010 "accessing field 0"). The 6 starting slots need no
    level; slots 7-10 open at player levels 10/20/30/40 (offline choice, the
    original values are not known).
    """
    levels = [0, 0, 0, 0, 0, 0, 10, 20, 30, 40]
    return {str(i): {"unlockNum": i, "levelRequired": lv, "money": 0, "gems": 0, "friendNum": 0}
            for i, lv in enumerate(levels)}


def _land_plot_unlock_rules():
    """Offline town-area unlock data consumed by TownBaseMap.

    The AS3 client already has the complete locked-plot UI and purchase flow.
    It asks for the rule at the current number of open areas, then sends
    services.I5001 with the area index as a STRING.  We deliberately make the
    normal coin-purchase path reachable immediately (level 1, zero friends)
    and leave the gem-based early-unlock path disabled.  Costs are an
    offline reconstruction rather than claimed original PopCap balance data.
    """
    # The first four plots (8,9,12,13) are the free 12x12 starter area, so
    # the first paid purchase happens when 4 plots are already open.  The
    # client indexes this table by opendAreaTileList.length, not by the map
    # area's spatial id.  Keep the first paid plot at 1000 coins so a normal
    # starter save can actually buy land without requiring a large balance.
    costs_by_open_count = {
        4: 1000, 5: 1500, 6: 2500, 7: 4000, 8: 6000, 9: 8500,
        10: 11500, 11: 15000, 12: 19000, 13: 23500, 14: 28500,
        15: 34000,
    }
    return {
        "2": {
            str(open_count): {
                "unlockNum": open_count,
                "money": cost,
                "levelRequired": 0,
                # TownBaseMap adds +1 to this value when checking the
                # normal unlock path, so -1 means no friend requirement.
                "friendNumRequired": -1,
                "earlyUnlockCost": -1,
            }
            for open_count, cost in costs_by_open_count.items()
        }
    }


# ---------------------------------------------------------------------------
# Persistent TD progression
# ---------------------------------------------------------------------------
# Plant ids are the same ids used by conf/PlantData.xml and the Almanac.
# The first two are the tutorial starting cards. Completing mission N grants
# the next plant in this table and opens mission N+1. Keeping this mapping in
# one place makes the progression easy to extend without touching the SWFs.
_PLANT_UNLOCK_BY_LEVEL = {
    1: 17,   # Cherry Bomb
    2: 9,    # Wall-nut
    3: 18,   # Potato Mine
    4: 16,   # Snow Pea
    5: 20,   # Chomper
    6: 24,   # Repeater
    7: 13,   # Puff-shroom
    8: 1,    # Sun-shroom
    9: 14,   # Fume-shroom
    10: 5,   # Grave Buster
}


# ---------------------------------------------------------------------------
# Adventure level catalogue (level number == mission id, as in the progression
# code below). Levels 1-3 are the tutorial levels in their real modes (types 3,
# 4, 5); after that come the enabled levels of conf/missions.json (wiki data:
# 前院1-1..1-6 = levels 4-9, 水池1-1..1-6 = levels 10-15). Night levels are in
# missions.json but disabled until pvzScreen2/pvzScreen4 exist.
# ---------------------------------------------------------------------------
_TUTORIAL_LEVELS = [
    dict(name="新兵训练1", type=3, scene=1, waves=5, initSun=150, zombies=[2], flagWave="5", gold=0, exp=0, img=1,
         description="开始第一关", dave=""),
    dict(name="新兵训练2", type=4, scene=1, waves=5, initSun=50, zombies=[2], flagWave="5", gold=0, exp=0, img=1,
         description="学会种向日葵", dave=""),
    dict(name="新兵训练3", type=5, scene=1, waves=5, initSun=50, zombies=[2], flagWave="5", gold=1000, exp=19, img=1,
         description="学会使用铲子", dave=""),
]
# plant card rewards for winning a level (wiki "获得…" notes for the easy difficulty)
_PLANT_REWARDS_BY_NAME = {
    "前院1-1": [9],          # Wall-nut
    "前院1-2": [18],         # Potato Mine
    "前院1-3": [16],         # Snow Pea
    "前院1-4": [20],         # Chomper
    "前院1-5": [24],         # Repeater
    "前院1-6": [13, 4],      # Puff-shroom; Lily Pad as well so the pool levels are playable
    "前院1-7": [22],         # Squash
    "前院1-8": [25],         # Jalapeno
    "前院1-9": [11],         # Tall-nut
    "前院1-10": [8],         # Torchwood
    "水池1-1": [23], "水池1-2": [21], "水池1-3": [15], "水池1-4": [1], "水池1-5": [7], "水池1-6": [19],
}
_ADVENTURE_CACHE = {}


def _adventure_levels():
    if "levels" in _ADVENTURE_CACHE:
        return _ADVENTURE_CACHE["levels"]
    levels = []
    for t in _TUTORIAL_LEVELS:
        levels.append(dict(t, category=1, plantRewards=[], progressId=len(levels) + 1))
    try:
        with open(os.path.join(HERE, "conf", "missions.json"), encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"[progress] could not read conf/missions.json ({e}); only the tutorial levels are available")
        data = {"levels": []}
    for m in data.get("levels", []):
        if not m.get("enabled"):
            continue
        easy = m["difficulties"][0]
        idx = len([x for x in levels if x.get("scene") == m["scene"] and x.get("type") == 1]) + 1
        waves = 6 + 2 * min(7, idx - 1) if m["scene"] == 1 else 8 + 2 * min(3, idx - 1)   # front yard grows to 20 waves (1-8..1-10)
        flags = ",".join(str(w) for w in ([10] if waves >= 15 else []) + [waves])   # PvZ: a flag every 10 waves + the final wave
        # The real Adventure data uses resourceId 11,12,... for the level and
        # resourceId*10+difficulty for the playable mission id (110/111/112,
        # 120/121/122, ...).  Keep the old sequential index as ``progressId``
        # for backward-compatible saves, but retain the real identifiers here
        # so difficulty selection cannot accidentally resolve to a tutorial.
        resource_id = int(m.get("resourceId", 0) or 0)
        difficulty_data = []
        for diff, d in enumerate(m.get("difficulties", [])[:3]):
            difficulty_data.append({
                "difficulty": diff,
                "missionId": resource_id * 10 + diff if resource_id else idx,
                "resourceId": resource_id,
                "cdMinutes": int(d.get("cdMinutes", 0) or 0),
                "gold": int(d.get("gold", 0) or 0),
                "exp": int(d.get("exp", 0) or 0),
                "note": d.get("note", ""),
            })
        # 4th difficulty for the confirm panel's 地狱 (hell) tab: the hard values
        # +30% coins/exp and a longer house cooldown (no wiki data for it).
        if len(difficulty_data) == 3:
            hard = difficulty_data[2]
            difficulty_data.append(dict(hard, difficulty=3,
                                        missionId=resource_id * 10 + 3 if resource_id else idx,
                                        cdMinutes=hard["cdMinutes"] + 15,
                                        gold=int(round(hard["gold"] * 1.3)), exp=int(round(hard["exp"] * 1.3)),
                                        note=""))
        levels.append(dict(name=m["name"], type=1, scene=m["scene"], waves=waves, initSun=50,
                           zombies=m["zombies"] or [2], flagWave=flags, gold=easy["gold"], exp=easy["exp"],
                           img=m["img"], description=m.get("dave", ""), dave=m.get("dave", ""), category=1,
                           plantRewards=_PLANT_REWARDS_BY_NAME.get(m["name"], []),
                           # progressId = position in this catalogue (tutorials 1-3, 前院1-1 = 4,
                           # ... 水池1-6 = 15): _level_info(), unlockedLevels and levelsFinished
                           # all use it. It used to be the per-scene index (前院1-1 = 1), so
                           # winning 前院1-1 was saved as "tutorial 1 finished" and the
                           # chain never unlocked 前院1-2.
                           resourceId=resource_id, progressId=len(levels) + 1, difficulties=difficulty_data,
                           maxDifficulty=max(0, len(difficulty_data) - 1)))
    _ADVENTURE_CACHE["levels"] = levels
    print(f"[progress] adventure catalogue: {len(levels)} levels")
    return levels


def _house_mission_resource_ids():
    ids = []
    for mid in range(1, _max_level() + 1):
        info = _level_info(mid) or {}
        normal = int(info.get("type", 1) or 1) == 1
        rid = int(info.get("resourceId", mid) or mid) if normal else mid
        ids.append(rid)
    return ids


def _max_level():
    return len(_adventure_levels())


def _level_info(mid):
    levels = _adventure_levels()
    return levels[mid - 1] if 1 <= mid <= len(levels) else None


def _level_by_resource_id(resource_id):
    try:
        rid = int(resource_id)
    except (TypeError, ValueError):
        return None
    for info in _adventure_levels():
        if int(info.get("resourceId", 0) or 0) == rid and int(info.get("type", 1) or 1) == 1:
            return info
    return None


def _resolve_mission_request(raw_mission_id, requested_difficulty=None):
    """Resolve both legacy sequential ids and the real Adventure mission ids.

    Tutorials remain 1/2/3.  Normal Adventure uses resourceId*10+difficulty:
    e.g. 前院1-1 = 110/111/112.  A bare resourceId such as 11 is treated as
    its easy mission (110), and the optional second argument can select 0..2.
    """
    try:
        raw = int(raw_mission_id)
    except (TypeError, ValueError):
        raw = 1
    try:
        req_diff = int(requested_difficulty) if requested_difficulty is not None else None
    except (TypeError, ValueError):
        req_diff = None

    # Real mission id: resourceId * 10 + difficulty.
    if raw >= 100:
        rid, diff = divmod(raw, 10)
        info = _level_by_resource_id(rid)
        if info is not None:
            diff = max(0, min(int(info.get("maxDifficulty", 0)), diff))
            if req_diff is not None and 0 <= req_diff <= int(info.get("maxDifficulty", 0)):
                diff = req_diff
            return info, diff, rid * 10 + diff

    # Real resourceId, normally supplied by the level panel before the
    # difficulty is appended.
    info = _level_by_resource_id(raw)
    if info is not None:
        diff = req_diff if req_diff is not None else 0
        diff = max(0, min(int(info.get("maxDifficulty", 0)), diff))
        return info, diff, int(info["resourceId"]) * 10 + diff

    # Backward compatibility for the old offline build's sequential ids.
    info = _level_info(raw)
    if info is not None:
        if int(info.get("type", 1) or 1) == 1:
            diff = req_diff if req_diff is not None else 0
            diff = max(0, min(int(info.get("maxDifficulty", 0)), diff))
            rid = int(info.get("resourceId", 0) or 0)
            return info, diff, (rid * 10 + diff) if rid else raw
        return info, 0, raw
    return _level_info(1), 0, 1


def _completed_mission_map(save):
    """unlocks["5"]: every completed mission id, as the client understands them.

    The client compares these with the ids it got from I1007 (tutorials 1-3,
    adventure levels resourceId*10+difficulty, e.g. 110/111/112). Older saves
    only have levelsFinished (catalogue positions), so a finished adventure
    level also counts as its easy mission id.
    """
    out = {}
    for mid in _normalize_progress(save)["levelsFinished"]:
        out[str(mid)] = "1"
        info = _level_info(mid)
        if info and int(info.get("type", 1) or 1) == 1 and int(info.get("resourceId", 0) or 0):
            out[str(int(info["resourceId"]) * 10)] = "1"
    for ext in save.get("missionsFinished", []):
        out[str(ext)] = "1"
    return out


def _normalize_progress(save):
    """Return a save with clean, backward-compatible progression fields."""
    finished = set()
    for value in save.get("levelsFinished", []):
        try:
            mid = int(value)
        except (TypeError, ValueError):
            continue
        if mid > 0:
            finished.add(mid)

    # Older builds recorded tutorial completion only in tutorialStep /
    # skippedTutorial and did not have levelsFinished.  Migrate that state
    # into the new progression fields so an already-finished tutorial really
    # grants mission 1 + its plant reward instead of making the player repeat
    # the level.
    legacy_tutorial_complete = False
    try:
        legacy_tutorial_complete = int(save.get("tutorialStep", 0) or 0) >= _TUTORIAL_COMPLETE_FULL
    except (TypeError, ValueError):
        legacy_tutorial_complete = False
    if legacy_tutorial_complete or save.get("skippedTutorial") is True:
        # A completed/skipped tutorial means Tutorials 1, 2 and 3 have all
        # been completed.  Keep the prerequisite chain intact: Mission 3
        # depends on Mission 2, and Mission 4 depends on Mission 3.  Older
        # saves that only recorded the final tutorial bit must therefore be
        # migrated to the complete sequential tutorial history.
        finished.update((1, 2, 3))
        # Cherry Bomb is the plant unlocked by the tutorial before the first
        # normal Adventure mission.  Keep it in owned cards after migration
        # so the normal-level card selector has a real owned plant to show.
        existing = set()
        for value in save.get("unlockedPlants", []):
            try:
                existing.add(int(value))
            except (TypeError, ValueError):
                pass
        existing.add(17)
        save["unlockedPlants"] = sorted(existing)

    # Mission 1 is the first playable mission. A completed mission also
    # unlocks the following mission, so keep both concepts explicit in the
    # save rather than relying on a transient client state.
    unlocked_levels = {1}
    for mid in finished:
        unlocked_levels.add(mid)
        if mid < _max_level():
            unlocked_levels.add(mid + 1)

    plants = {12, 2}
    for value in save.get("unlockedPlants", []):
        try:
            pid = int(value)
        except (TypeError, ValueError):
            continue
        if pid in _PLANT_ALMANAC_IDS:
            plants.add(pid)

    # Migrate older saves that already contain completed levels but no new
    # unlockedPlants field. Reconstruct rewards deterministically.
    for mid in finished:
        info = _level_info(mid)
        for pid in (info["plantRewards"] if info else []):
            plants.add(pid)

    save["levelsFinished"] = sorted(finished)
    save["unlockedLevels"] = sorted(unlocked_levels)
    save["unlockedPlants"] = sorted(plants)
    return save


def _persist_progress_for_completed_mission(mission_id):
    """Persist a completed mission, its next level, and its plant reward."""
    try:
        mission_id = int(mission_id)
    except (TypeError, ValueError):
        return current_save()
    if mission_id <= 0:
        return current_save()

    save = _normalize_progress(current_save())
    finished = set(save["levelsFinished"])
    finished.add(mission_id)
    unlocked_levels = set(save["unlockedLevels"])
    unlocked_levels.add(mission_id)
    if mission_id < _max_level():
        unlocked_levels.add(mission_id + 1)

    plants = set(save["unlockedPlants"])
    info = _level_info(mission_id)
    reward = list(info["plantRewards"]) if info else []
    for r in reward:
        plants.add(r)

    state = write_current_save(
        levelsFinished=sorted(finished),
        unlockedLevels=sorted(unlocked_levels),
        unlockedPlants=sorted(plants),
    )
    print(f"[progress] mission={mission_id} finished={sorted(finished)} "
          f"next={sorted(unlocked_levels)} plants={sorted(plants)} reward={reward}")
    return state


_RAMPAGE_TOURNAMENT = {
    "id": 1, "type": 102, "scene": 1, "totalWaves": 10, "initSun": 1500, "initTomb": 0,
    # zombies that have art in this folder (+ 100 = the rabbit-imp bonus zombie)
    "allowedZombies": [2, 5, 11, 14, 18, 19, 100],
    "specialFirstAllowWave": "19:1", "specialValue": "19:1", "specialWeight": "19:15000",
    "expPrize": 0, "tokenPrize": 0, "difficultCoefficient": 30, "rushCoolDown": 8,
    "groupVaseQty": 50, "gameDuration": 120, "vaseZombieWeight": 1, "vaseCardWeight": 2,
    "vasePlantWeight": 2, "dropVaseCD": 8, "dropVase": 1, "initVase": 1,
    "initPlant": "1:2,2:24,4:8,5:11,6:21", "missionName": "暴走模式",
    "contractFee": 0, "energyConsuming": 0, "flagWave": "10",
    # LeaderBoard fields: countdown end, weekly team goal and prizes
    "endTime": "2099-12-31 23:59:59", "teamTarget": 300000,
    "weeklyToken": 5000, "weeklyGems": 0, "weeklyExp": 500,
}


def _effective_tutorial_step(step):
    """Once the rampage tutorial (1024) is done, the town would start the arena
    (PvP occupation) and card-strengthen tutorials, which need online data and
    lock every other town button. Report them as done."""
    step = int(step or 0)
    if step & 1024:
        step |= 131072 | 262144 | 524288 | 1048576
    return step


def i1001_payload():
    """Response for services.I1001 - the very first call the client makes.
    Shape follows Flow.as's onInitPvzsComplete()/parseUserData()."""
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    save = current_save()
    identity = active_identity()
    return {
        "result": True,
        "gems": save["gems"],
        "gemsToToken": 17000,
        "feedEnabled": False,
        "sysTime": now,
        # Echoed back by the client as the 3rd argument of every later call
        # - see "Multi-device play" near get_active_account().
        "popcapId": getattr(_request_ctx, "token", None) or "offline",
        "rampageLevelRequired": 1,
        # Real rampage mode (after its tutorial): RamPageEntryPannel reads
        # pvzData.tournaments[pvzData.currentTournamentId] as the mission config
        # (same fields as PVZConfig.MISSION_TUTORIAL_RAMPAGE, type 102).
        "tournaments": {"1": _RAMPAGE_TOURNAMENT},
        "unlockedLevels": [str(x) for x in sorted(_normalize_progress(save)["unlockedLevels"])],
        "unlockedPlants": [str(x) for x in sorted(_normalize_progress(save)["unlockedPlants"])],
        "unlocks": {
            # DataManager.UNLCOK_TYPE_TD_MISSION == 5.  MissionListPanel
            # reconstructs completeMissionArr from this map.
            # Type 5 is the TD mission progression map. Keep completed
            # missions here; the MissionListPanel uses preMissions from I1007
            # to decide which following mission is selectable.
            "5": _completed_mission_map(save),
        },
        # Grants ownership of the FuncHouse card (see _func_house_card_settings()),
        # only the plant cards recorded in save["unlockedPlants"], AND whichever
        # funchouse function-cards have actually been bought
        # (save["ownedFunctionCards"], written by the I5001 handler) -
        # Flow.setMyItemsListS2C() reads this straight into
        # DataManager.myItemsMap, and for ITEM_TYPE_CARD (the "0" key) every
        # entry's tid is unconditionally pushed onto ownCardsData (no
        # count/expireTime check, unlike the special/time card branches).
        # FuncHouseCardSelectPanel.updateData() needs this for the practice
        # house's card; ComposeCardsContainer needs it too (isOwned =
        # ownCardsData.indexOf(String(cardId)) != -1) or every plant card
        # shows locked despite everything else being wired up. tid is sent
        # as a string so String(ownCardsData[i]) comparisons match cleanly
        # regardless of how each consumer sends its own ids.
        "items": {
            "0": (
                [{"tid": str(_FUNC_HOUSE_CARD_ID)}]
                + [{"tid": str(rid)} for rid in _normalize_progress(save)["unlockedPlants"]]
                + [{"tid": str(rid)} for rid in save.get("ownedFunctionCards", [])]
            ),
            # ITEM_TYPE_CARD_SLOT (10): the seed bar has one slot per entry
            # (SCardListTopPanel: maxCardNum = items["10"].length, 5..10).
            # Without this list the seed-selection screen of every normal
            # adventure level failed (#1010 reading .length of undefined).
            # PvZ starts with 6 slots; save["seedSlots"] can raise it.
            # ITEM_TYPE_BOOST_SLOT (11): one entry per open boost slot (3 = all open)
            "11": [{"tid": str(9100 + i), "slotId": i, "index": i} for i in range(3)],
            "10": [
                {"tid": str(9000 + i), "slotId": i, "index": i, "active": True}
                for i in range(max(5, min(10, int(save.get("seedSlots", 6) or 6))))
            ],
        },
        # itemSettings drives the ENTIRE item shop, not just display - it's the
        # only thing PropItemsManager.resetConfigMap() ever loops over
        # (Flow.setItemsConfigS2C -> PropItemsManager.resetConfigMap). GamePropItem_1_.xml
        # only supplies cosmetic fields (name/img/category/desc) for whatever resourceId
        # already has an entry here; it is never iterated on its own. Leaving this {}
        # (as it was) means propItemsConfigMap AND itemTypeConfigMap both stay
        # completely empty - every shop category shows 0/0 (not just House), and
        # Data.instance.itemConfArr (TownEntry.loadBuildingConf, built from
        # itemTypeConfigMap) is empty too, which is what a lot of the town/building
        # code indexes into.
        #
        # Top-level keys here are STRING item-type ids (DataManager.ITEM_TYPE_*,
        # e.g. "4" = ITEM_TYPE_BUILDING), each holding a dict of catalog entries
        # keyed by an arbitrary string (only entry["id"] is actually read).
        #
        # Only resourceId 701 (the starter house, GamePropItem_1_.xml category="7")
        # is wired in so far. This is the exact item the new-player tutorial
        # (TownTutorialFlow / DataManager.TUTORIAL_STEP_BUY_HOUSE) is waiting on:
        # with it missing, item 701 could never appear in the shop, so the tutorial's
        # required first purchase could never complete, so tutorialStep could never
        # advance past TUTORIAL_STEP_BUY_HOUSE (1) - which is also why ItemShopUI
        # kept forcing every tab click back to the House category
        # (ItemShopUI.onClickTypeBy: "if tutorialStep == TUTORIAL_STEP_BUY_HOUSE: param1 =
        # CATEGORY_HOUSE"). That tab-lock is intentional tutorial behavior, not a bug,
        # and lifts on its own once this purchase completes and the house is placed
        # (TownTutorialFlow.showTutorialBuyHouse4 advances tutorialStep to
        # TUTORIAL_STEP_TD_TUTORIAL). Buying a House-category item doesn't call
        # services.I5001 at all (ItemShopListItem.onClickItem dispatches
        # DEventManager.TAKING_BUILDING directly for HOUSE/DECORATE/FUNCTION/SHOP
        # categories) - the AMF call that follows placement (services.I1016, and the
        # queued build-complete call) already null-guards a generic {} response, so
        # nothing new needed there.
        #
        # Other categories (Garden seeds 101-116, Points/Strengthen items 1006-1201,
        # etc.) still won't show anything until they get their own entries here too -
        # that's a bigger follow-up (each one's ITEM_TYPE_* isn't in the XML at all,
        # it only exists here, so it has to be assigned deliberately per item) and
        # deliberately left out of this fix to keep it scoped to what's blocking you
        # right now.
        "itemSettings": {
            # ITEM_TYPE_CARD_SLOT (10): catalogue entries for the seed-slot items
            # sent in items["10"] (tids 9000-9009). Every owned item is looked up
            # in this catalogue (e.g. ItemShopListItem.isFullOwnItemLimit reads
            # propItemsConfigMap.get(tid).groupId with no null check), so the
            # slot items need real entries or the item shop crashes (#1009).
            # Inactive and group 0: never sold, never counted as a building.
            "10": {**{
                str(9000 + i): {
                    "id": 9000 + i,
                    "resourceId": 9000 + i,
                    "type": 10,
                    "groupId": 0,
                    "active": False,
                    "money": 0,
                    "sellType": 0,
                    "status": 0,
                    "discount": "1",
                    "onShelfTime": "0",
                    "offShelfTime": "0",
                    "levelRequired": 0,
                    "ownCountLimit": 0,
                }
                for i in range(10)
            }, **{
            # Seed-slot UNLOCK prices: SCardListTopPanel.overSlotLock() reads
            # propItemsConfigMap.get(337 + maxCardNum).money with no null check
            # (hovering a locked slot crashed with #1009). 6 slots -> item 343.
                str(337 + n): {
                "id": 337 + n, "resourceId": 337 + n, "type": 10, "groupId": 0, "active": False,
                "money": {6: 750, 7: 1500, 8: 3000, 9: 5000}.get(n, 5000), "sellType": 0,
                "status": 0, "discount": "1", "onShelfTime": "0", "offShelfTime": "0",
                "levelRequired": 0, "ownCountLimit": 0,
                } for n in range(0, 11)
            }},
            "11": {  # ITEM_TYPE_BOOST_SLOT items sent in items["11"] (never sold)
                str(9100 + i): {
                    "id": 9100 + i, "resourceId": 9100 + i, "type": 11, "groupId": 0, "active": False,
                    "money": 0, "sellType": 0, "status": 0, "discount": "1", "onShelfTime": "0",
                    "offShelfTime": "0", "levelRequired": 0, "ownCountLimit": 0,
                } for i in range(3)
            },
            "4": {  # ITEM_TYPE_BUILDING
                "701": {
                    "id": 701,
                    "resourceId": 701,
                    "type": 4,          # ITEM_TYPE_BUILDING
                    "active": True,
                    "money": 500,       # price in coins - adjust freely, not from any source data
                    "sellType": 0,      # DataManager.MONEY_TYPE_COIN
                    "status": 1,        # ItemShopUI.STATUS_NORMAL
                    "discount": "1",    # "1" == no discount (exact-string check in ItemShopListItem)
                    "onShelfTime": "0", # "0" == no shelf-time window (bypasses holiday/discount-cycle logic)
                    "offShelfTime": "0",
                    "recommend": 0,
                    "level": 1,
                    # Everything below this line is ONLY needed because buying the item
                    # doesn't route through propItemsConfigMap (which DOES get XML-merged,
                    # and is all the *shop display* needs) - it goes through
                    # DataManager.itemTypeConfigMap -> Data.instance.itemConfArr instead
                    # (PropItemsManager.resetConfigMap's OUTER loop stores the raw,
                    # un-merged itemSettings object under itemTypeConfigMap, never
                    # touching GamePropItem_1_.xml at all), and that's what
                    # Manager.createNewItem()/getDefinitionClass() and the Building/AbsItem
                    # base classes read from once you actually click to buy. Confirmed via
                    # a live AS error (Error #1009 in Manager.getDefinitionClass, called
                    # from createNewItem <- addAndDrapNewItem <- TownFlow.onTakingBuilding)
                    # that itemConfArr[701] was ending up with nothing usable without these:
                    "subType": 1,           # GameConfig.BLD_TYPE_HOMES - REVERTED back to
                                            # HOMES (from FUNC_HOUSE/7) at the user's explicit
                                            # request: 701 is used to load TD levels and get
                                            # upgraded like the other houses, not to power up
                                            # plants, so it belongs grouped with 706/711/716/
                                            # 721/726 in the building catalog rather than off
                                            # in the "强化" tab. Last time this reclassification
                                            # was tried, reverting it back to FUNC_HOUSE was
                                            # needed because 701 was the ONLY subType-7
                                            # building in the whole project, so that tab went
                                            # silently empty without it (see git history for
                                            # the long version of that story). That's no longer
                                            # true here: 716/721/726 are already their own,
                                            # separate subType-7 (FUNC_HOUSE) buildings in this
                                            # project (see _BUILDING_SUBTYPE below), so the
                                            # "强化" tab keeps real content either way - 701
                                            # moving to HOMES no longer empties it out.
                    "size": "2,2",          # MUST be a comma-separated STRING, not an
                                            # array - confirmed via [DEBUG-BUILD] trace:
                                            # TownEntry.loadBuildingConf()'s own check is
                                            # "if(!(size==null || size.indexOf(',')==-1))"
                                            # guarding the *entire* itemConfArr[id]=...
                                            # assignment, not just the split-to-array step
                                            # I originally assumed it was. Array.indexOf(',')
                                            # looks for an ELEMENT equal to ",", never finds
                                            # one in [2,2], so the whole entry was being
                                            # silently skipped - itemConfArr[701] genuinely
                                            # never existed. A real string with a comma in it
                                            # makes String.indexOf(",") succeed, the code
                                            # splits it back into ["2","2"], and w/h (typed
                                            # int) coerce the strings back to numbers fine.
                    "bigImg": "house1_1",   # AbsItem.updateSkin() needs this to spawn the
                                            # actual visual (same symbol confirmed rendering
                                            # correctly in the shop icon).
                    "sourceName": "house1.swf",  # BldSkinManager.getBldResUrl() needs this
                                                 # to know which swf to load for the skin.
                    "ownCountLimit": 99,    # Manager.putBuildingToMousePos() blocks the
                                            # actual drop with an "already own the max of
                                            # this" alert whenever
                                            # ownedCount(0, brand new) >= ownCountLimit -
                                            # left unset, int(undefined) is 0, so 0>=0
                                            # was true on EVERY attempt, always blocking
                                            # placement (shown as a bare "Error" popup,
                                            # since the real message comes from
                                            # Localization.xml, still missing). This reads
                                            # from propItemsConfigMap (the XML-merged shop
                                            # map, via PropItemsManager.getPropItemConfig),
                                            # not itemConfArr, but the XML has no such
                                            # attribute either, so it still needs setting
                                            # here. 99 is a generous placeholder, not a
                                            # real limit from any source data.
                },
                # 966 and 967 aren't shop items - they're the two fixed "sponsor"
                # buildings conf_1_.xml always places on the map
                # (<bg><bizBldItem itemId="966".../><zbzBldItem itemId="967".../>),
                # rendered directly by TownBaseMap rather than bought/placed like 701.
                # TownBaseMap.onGetBIzItemData()/onGetZbzBIzItemData() read
                # Data.instance.itemConfArr[bizItemId].functionId/.affect with no null
                # check - confirmed live (Error #1009) - and that lookup goes through
                # this same itemSettings data, same as 701. GamePropItem_1_.xml already
                # has real name/image data for both (category="-1", so they were never
                # going to show up in the shop regardless); functionId/affect aren't in
                # the XML at all, so they need setting here same as 701's building-only
                # fields. 0/0 is a "no effect" placeholder, not real balance data.
                #
                # "size" is REQUIRED here too, same reason/same fix as 701's: without a
                # comma-containing string, TownEntry.loadBuildingConf()'s
                # "if(!(size==null || size.indexOf(',')==-1))" guard silently drops the
                # whole entry, so itemConfArr[966]/[967] stayed undefined even with
                # functionId/affect set - confirmed as the actual still-live crash
                # (Error #1009 in TownBaseMap.onGetBIzItemData, at
                # itemConfArr[bizItemId].functionId) despite this dict otherwise looking
                # complete. 1x1 is a placeholder footprint - these aren't placed/dragged
                # by the player, so the actual number doesn't affect anything visible.
                "966": {
                    "id": 966,
                    "resourceId": 966,
                    "type": 4,
                    "functionId": 0,
                    "affect": 0,
                    "size": "1,1",
                },
                "967": {
                    "id": 967,
                    "resourceId": 967,
                    "type": 4,
                    "functionId": 0,
                    "affect": 0,
                    "size": "1,1",
                },
                **_extra_building_settings(save["tutorialStep"] >= 3),  # 3 = DataManager.TUTORIAL_STEP_COMPLETE
            },
            "1": _seed_item_settings(),  # ITEM_TYPE_SEED - the 9 garden seeds
            "0": {**_func_house_card_settings(), **_plant_almanac_card_settings(), **_function_card_settings(save["tutorialStep"] >= 3)},  # ITEM_TYPE_CARD
            "2": _upgrade_material_settings(),  # ITEM_TYPE_MATERIAL
            "3": _decoration_item_settings(),  # ITEM_TYPE_DECORATIONS
        },
        # DataManager.UNLOCK_TYPE_TOWNSIZE = 2.  The client already owns the
        # complete locked-area UI; this supplies the rules it needs for the
        # next locked plot.
        # 3 = UNLOCK_TYPE_CARD_SLOT (seed bar), 7 = UNLOCK_TYPE_BOOST (boost panel:
        # BoostPanel.updateLock() reads unlockRulesConfigMap.get("7")[slot] -
        # missing, rampage mode crashed with #1009).
        "unlockRules": dict(_land_plot_unlock_rules(), **{
            "3": _seed_slot_unlock_rules(),
            "7": {str(i): {"unlockNum": i, "levelRequired": 0, "earlyUnlockCost": 0, "money": 0, "gems": 0}
                  for i in range(3)},
        }),
        "zombieSettings": {},
        "plantSettings": _plant_settings(),
        "synthesisSettings": {},
        # levelUpBonus (Flow.setLevelUpBonusS2C -> DataManager.
        # levelUpBonusMap, keyed by level as a string) was empty - CONFIRMED
        # LIVE CRASH: EnergyManager.__onLevelUp() does
        # levelUpBonusMap.get(newLevel).energy with no null-check at all, so
        # every single level-up (any level) threw Error #1009 the instant it
        # fired, via CommonModel's level setter dispatching straight into
        # this listener. UpGradePanel.onTimerCompleted() has the exact same
        # unguarded-access pattern for .token/.gems, so it needed a real
        # entry too, not just EnergyManager's field. Populated for every
        # level in expLadder's range (1-60) with placeholder-but-present
        # values - no real PvZ Social level-up balance data exists here
        # (same "placeholder, not real balance" situation as this project's
        # other placeholder fields), but 0/empty is enough to make every
        # read site's null-check pass and every arithmetic read resolve to
        # a real number instead of throwing.
        "levelUpBonus": {
            str(n): {"energy": 5, "token": 0, "gems": 0, "items": {}}
            for n in range(1, 61)
        },
        "user": {
            "uid": identity["uid"],
            "name": identity["name"],
            "thumbnail": identity["thumbnail"],
            "token": save["money"],
            "experience": save["experience"],
            "level": save["level"],
            "ladderExpValue": 500,
            "energy": 20,
            "energyLimit": 20,
            "lastEnergyChargedTime": now,
            "point": 0,
            "stealCount": 0,
            "lastStoleanTime": "",
            "battleSlotNum": 6,
            "guideStep": _effective_tutorial_step(save["tutorialStep"]),
            "todayLoginBonus": False,
            "antiAddictionDuration": 0,
            "antiAddictionUnlock": True,
            # AmfCaller.as: commonModel.meetZombies = user.unlockedZombies
            # (a comma-separated string, split() on the consuming end in
            # ZombiesContainer.as) - gates isEnabled per zombie tile; without
            # this every zombie in the almanac shows greyed-out/undiscovered
            # regardless of what's in ZombieData.xml. Every zombieId we
            # actually have art and data for (see _ZOMBIE_ALMANAC_IDS).
            "unlockedZombies": ",".join(str(z) for z in _ZOMBIE_ALMANAC_IDS),
        },
        "antiAddictionRecords": {},
        # Reverted along with unlockRules/grounds above (back to how this
        # was before the area-unlock feature): groundUnlockGreenPoints back
        # to empty and defaultGreenPoints removed entirely. Historical
        # note, in case this needs revisiting later - with these empty/
        # missing, Data.instance.maxPlanValue stays stuck at 0 regardless of
        # how many areas are open, and yet seed planting was never actually
        # observed to be blocked by that throughout this whole project -
        # something else was covering it, never fully identified, so
        # reverting this is not expected to reintroduce any regression that
        # was actually visible before.
        "groundUnlockGreenPoints": [],
        # Planting capacity (Data.instance.maxPlanValue, the "x/y" counter
        # next to the seedling icon). Each seed uses greenConsumption 1, and
        # Manager.addAndDrapNewItem() refuses a new seed when used + 1 > max,
        # so with this missing (max 0) no seed could be placed at all.
        # Independent of the land-plot unlock work that was backed out.
        "defaultGreenPoints": _DEFAULT_PLANT_CAPACITY,
        "clickBonus": [],
        # This is the root cause behind the VERY FIRST gap this project ever
        # flagged (the "[DEBUG-DATA-MISSING] areaTileIndexConf[n] was
        # undefined... pvzData.grounds is likely empty/incomplete" lines
        # every debug export has shown since day one) - and, it turns out,
        # also why no building could ever be placed anywhere in town:
        # TownEntry.as parses this into Data.instance.areaTileIndexConf /
        # areaTileItemIdConf, which TownFlow.as's onGetUserTownInfo() (see
        # i2001_payload below) then uses to build opendAreaTileList, which
        # Manager.resetOpenArea() uses to flip itemMap tiles from -1
        # (locked) to 0 (buildable). With this empty, NOTHING ever unlocks,
        # so Manager.isBuidAble() returns false for every tile, forever -
        # a house can get all the way into drag mode and just never have
        # anywhere valid to drop.
        #
        # conf_1_.xml's <image areaTileArea="..."> defines 16 6x6-tile
        # blocks (a 4x4 grid covering the full 24x24 town). Each key here
        # is a "ground id"; TownEntry.as sorts the values (ascending by
        # first element) and uses the SORTED RANK as the actual area
        # index - so as long as these are already in ascending order by
        # key, key "N"'s rank is just N, matching areaTilePosConf[N] one
        # to one. Giving each of the 16 a distinct, non-overlapping
        # 36-length range (36 = 6x6) is enough; the exact numbers don't
        # appear to matter elsewhere, just their sort order.
        "grounds": {str(i): [i * 36, i * 36 + 35] for i in range(16)},
        "buildingSettings": {},
        "currentTournamentId": 1,  # = the tournament in "tournaments" (real rampage config)
        "lastTournamentId": 0,
        "depreciation": 1,
        # DataManager.maxUserLevel is derived from this map's HIGHEST KEY
        # (Flow.as: loops expLadder's keys, keeps the largest, assigns that
        # to maxUserLevel) - with this empty, that loop never runs,
        # maxUserLevel stayed at its int default of 0, and ExpBar.updateView()
        # shows "MAX" whenever currLvl >= maxLvl - 1 >= 0 is always true, so
        # the level bar showed MAX from the very first login regardless of
        # actual level. ExpBar also has its own read pattern worth noting:
        # for level N's progress bar it reads expLadder[N+1] (see
        # ExpBar.analyzeExpObj()), not expLadder[N] - so the exp cost to
        # reach level N+1 lives under key N+1, one level ahead of where
        # you'd naively expect. No source data exists for a real curve, so
        # this is a simple placeholder - 100 exp more per level, 60 levels
        # of headroom - not real balance data.
        "expLadder": {str(n): n * 100 for n in range(1, 61)},
        # Flow.setBattleHouseS2C(initDat.battleHouseLevelupBonus) - stored
        # as-is with no null-guard beyond "was the whole field missing".
        # UpgradeBldPanel.reset()'s BLD_TYPE_HOMES branch then does
        # battleHouseLevelupBonus[level] directly (both the current and next
        # tier's level) with no guard at all - missing this crashes the very
        # first time a house-type building's upgrade panel opens. Values are
        # a fraction (multiplied by 100 for display as a percent) - simple
        # placeholder progression, not real balance data. Index 0 included
        # since a fresh building's initial level state can read from it.
        "battleHouseLevelupBonus": {str(n): round(0.02 * n, 2) for n in range(0, 6)},
        "fightExchangeConfig": {},
        "harvestLowerLimit": 1,
        # LeaderBoard.enterContainer(): rampageWeeklyBonus[currentTournamentId]
        # ["teamTarget"] (3 team-score goals) - an empty dict crashed (#1009).
        "rampageWeeklyBonus": {"1": {"teamTarget": [100000, 300000, 500000]}},
        "residentStayingBonus": 0,
        "residentStayingToken": 0,
        "validRampageBonus": 1,
        "validRampageDuration": 60,
    }


def i2001_payload():
    """Response for services.I2001 - TownFlow.onGetUserTownInfo(). grounds is
    read 'as Array' then has .length accessed with no null check - the exact
    same crash pattern as pvzData.groundUnlockGreenPoints earlier. Everything
    else here already has proper null-guards in the real code, included
    anyway for completeness.

    grounds here must be the GROUND KEYS from i1001_payload's "grounds" dict
    (as strings) - TownFlow.as maps each one through
    Data.instance.areaTileItemIdConf to get the actual unlocked area index.

    The first house sits in area 8.  Areas 4, 5, 8 and 9 form one contiguous
    12x12 tile rectangle around it, so those four are returned free at login;
    all remaining areas stay behind the normal TownBaseMap purchase UI.
    """
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    save = current_save()
    return {
        "result": True,
        # I2001 returns the ground keys that are currently open.  I1001 still
        # defines all 16 source plots, while this per-save list controls which
        # plots are actually buildable.  The four starter plots (8,9,12,13)
        # form the requested 12x12 free starting rectangle.
        "grounds": [str(i) for i in sorted(set(save.get("unlockedAreas", [8, 9, 12, 13])))] ,
        # Reconstructed from real placement data, decoded out of
        # services.I2012's action queue (see that handler) rather than a
        # synthesized position - each entry is exactly what the player
        # themselves placed, at the position they themselves chose, so
        # there's no risk of two buildings landing on the same tile the way
        # a made-up position would have risked. Manager.createTownBuildList()
        # reads "position" as a single encoded tile number (via posToRl()),
        # which is exactly the shape Building.getPos() produced when it was
        # captured, so it round-trips as-is with no reformatting.
        "buildings": [
            {
                "id": b["buyId"],
                "tid": b["resourceId"],
                "level": b.get("level", 1),
                "position": str(b["position"]),
                "rotation": 0,
                "buyId": b.get("buyId", ""),
                "occupier": None,
                "leaveTime": None,
                "coolDown": "0000-00-00 00:00:00",
            }
            for b in save.get("placedBuildings", [])
        ],
        "decorations": [
            {
                "id": int(group.get("id", 0)),
                "tid": int(group["tid"]),
                "level": int(group.get("level", 1)),
                "layout": str(group.get("layout", "")),
            }
            for group in save.get("decorations", [])
            if int(group.get("tid", -1)) in _DECORATION_DEFS and group.get("layout")
        ],
        "plants": _town_plants(save),
        "sysTime": now,
        "ownerRampagePointLevel": 0,
        "addEnergy": 0,
    }


def i1034_payload():
    """Response for services.I1034 - TownFlow.onGetHouseEnegrySetting() (typo
    is the original game's, not ours), called right after a house is
    successfully placed. The handler does
    'Data.instance.housesEnegryList = param1.energyLimit[2]' with no null
    check - energyLimit needs to be a real 3+ element array or this throws
    Error #1010 the moment a house is placed (confirmed live). Only index 2
    is ever read, and what it becomes (housesEnegryList) is itself indexed
    later by building id (CitizenListItem/UpgradeBldPanel/CitizenListPanel
    all do housesEnegryList[building.id] to show a house's energy capacity).
    An empty dict is a safe default - int(undefined) from an unmatched
    lookup is 0 elsewhere - rather than fabricating specific capacity
    numbers with no source data behind them."""
    return {"result": True, "energyLimit": [{}, {}, {}]}


def i1023_payload():
    """Response for services.I1023 - FuncHousePage.requestData(), fired the
    first time you open a FuncHouse's "strengthen"/card-select panel.
    FuncHouseCardSelectPanel.updateData() does
    'Data.instance.buffHouseCardsSettings["buffHouseCardsSettings"]' with no
    null check - the whole response object needs a nested field of the same
    name (confirmed live: Error #1009 the moment that panel opened).

    "701" (the practice house's building id) now lists
    _FUNC_HOUSE_CARD_ID, so the one card from _func_house_card_settings()
    shows up as selectable - combined with the ownership grant in
    i1001_payload()'s "items" field, this is the other half of "make the
    Peashooter card selectable here" (see the big comment above
    _FUNC_HOUSE_CARD_ID for the full mechanism). Every other building
    still gets an empty list (curConfigCardsData already defaults to []
    for any key not present here) rather than fabricating cards for
    966/967 with no source data behind them.

    IMPORTANT - this panel is NOT what finishes the tutorial. Clicking the
    practice house directly on the map (not through this "strengthen"
    panel) is what calls TownTutorialFlow.showTdTutorialConfirmDialog() -
    confirmed by reading TownFlow.onClickFunctionBld(), which branches
    straight there for BLD_TYPE_HOMES while the tutorial is incomplete,
    without ever touching this card system. See that function and
    TownTutorialFlow.acceptTdTutorial()/skipTdTutorial() for how tutorial
    completion actually works."""
    return {"result": True, "buffHouseCardsSettings": {"701": [_FUNC_HOUSE_CARD_ID]}}


def i7017_payload():
    """Response for services.I7017 - ActivityPanel.onGetActivityConfig(), fired
    the first time the town's Activity button is clicked. The code reads
    param1.event as an array and, for each entry, looks up id/name/order/
    functionId/functionName/url/js/jsParams/params/childEvents/swfPath/img/
    smallImg/items/startDate/endDate - an entry only survives into the
    visible list if getActivityActive(startDate,endDate) says "now" falls
    between them.

    There's no real activity content in this reconstruction (no banner art,
    no per-activity swf), so this is a single placeholder entry with a wide
    open date range just so the panel has something to show instead of
    silently staying empty - the banner/icon image loads for it will 404
    (ActivityPanel.as's onLoadError swallows that instead of raising an
    unhandled-IOError dialog). functionId "-1" hides the confirm/accept
    button so clicking it doesn't try to follow a fake link.
    """
    return {
        "result": True,
        "event": [
            {
                "id": "1",
                "name": "Welcome",
                "order": "0",
                "functionId": "-1",
                "functionName": "",
                "url": "",
                "js": "",
                "jsParams": "",
                "params": "",
                "childEvents": "",
                "swfPath": "local/none.swf",
                "img": "local/none.png",
                "smallImg": "local/none.png",
                "items": "",
                "startDate": "2000-01-01 00:00:00",
                "endDate": "2099-12-31 23:59:59",
            }
        ],
        "code": 0,
    }


def generic_payload():
    """Fallback for every other services.I**** call we haven't modeled yet.
    Just claims success with an empty result so the client doesn't hang;
    don't expect this data to be *correct* for whatever it asked."""
    return {"result": True, "list": [], "code": 0}


def service_args(body):
    """Return the arguments after AmfCaller's id/signature/POPCAP prefix."""
    args = amf.decode_amf_args(body.value_bytes)
    if len(args) < 3:
        raise ValueError("service request is missing its three common arguments")
    return args[3:]


def _harvest_time_str(dt):
    """GardenUtils.parseNumberToDate's format: no zero padding."""
    return f"{dt.year}-{dt.month}-{dt.day} {dt.hour}:{dt.minute}:{dt.second}"


def i2017_payload(body):
    position = -1
    try:
        args = service_args(body)
        seed_id = int(args[0])
        position = int(args[1])
        save = current_save()
        updates, _ = apply_town_queue(
            save, [{"action": 9, "params": {"seedId": seed_id, "pos": position}}])
        if updates:
            write_current_save(**updates)
            save = current_save()
            print(f"[save] I2017 planted seed {seed_id} at {position}")
        plant = next((p for p in _town_plants(save) if p["position"] == position), None)
        if plant is not None:
            return {"result": True, "plant": plant, "code": 0}
        print(f"[save] I2017 could not plant seed {seed_id} at {position}")
    except (ValueError, TypeError, KeyError, IndexError) as exc:
        print(f"[save] I2017 decode failed: {exc}")
    # __onPlantComplete dereferences param1.plant unconditionally, so
    # never answer without one.
    return {"result": True, "plant": {"id": 0, "position": position}, "code": 0}


def _town_plants(save):
    """Planted seeds for I2001, in the shape Manager.createTownBuildList /
    PlantBuilding.setData read (no tid -> looked up by seedId)."""
    out = []
    for plant in save.get("plants", []):
        try:
            seed_id = int(plant["seedId"])
            position = int(plant["position"])
        except (KeyError, TypeError, ValueError):
            continue
        if seed_id not in _SEED_DEFS:
            continue
        # PlantBuilding is a town renderer.  Never hand it a seed whose
        # configured mcSourceName has no real Plant_*.swf art in this build;
        # otherwise ResSwfManager can complete with no MovieClip and the
        # existing BitmapUtil.drawMovieClip() path throws Error #1009.
        if seed_id not in _SEEDS_WITH_ART:
            continue
        out.append({
            "id": int(plant.get("id", 0) or 0),
            "seedId": seed_id,
            "position": position,
            "harvestTime": str(plant.get("harvestTime", "0")),
            "stealList": "",
            "stealCount": 0,
        })
    return out


def apply_town_queue(save, queue):
    """Apply building add/move/sell actions and return (updates, add replies).

    The response's buildings list matters: Manager.__onBuildComplete reads
    the assigned id back and stores it on the live building, so later moves
    and sales can refer to the same instance. Replaying the same add at the
    same position reuses its id instead of charging or duplicating it.
    """
    if not isinstance(queue, list):
        raise ValueError("I2012 placement queue is not an array")
    placed = [dict(item) for item in save.get("placedBuildings", [])]
    decorations = [dict(item) for item in save.get("decorations", [])]
    plants = [dict(item) for item in save.get("plants", [])]
    next_plant_id = max(
        int(save.get("nextPlantId", 3000000)),
        max((int(item.get("id", 0) or 0) for item in plants), default=0) + 1,
    )
    next_id = max(
        int(save.get("nextBuildingId", 1000000)),
        max((int(item.get("buyId", 0) or 0) for item in placed), default=0) + 1,
    )
    next_decoration_id = max(
        int(save.get("nextDecorationId", 2000000)),
        max((int(item.get("id", 0) or 0) for item in decorations), default=0) + 1,
    )
    money = int(save.get("money", 0))
    replies = []
    changed = False

    for entry in queue:
        if not isinstance(entry, dict) or not isinstance(entry.get("params"), dict):
            continue
        params = entry["params"]
        try:
            action = int(entry.get("action"))
        except (TypeError, ValueError):
            continue

        if action == 0:  # Config.QUEUE_TYPE_ADD_BLD
            try:
                resource_id = int(params["tid"])
                position = int(params["pos"])
            except (KeyError, TypeError, ValueError):
                continue
            if resource_id not in _ALL_BUILDING_PRICES or not 0 <= position < 10000:
                continue
            existing = next((b for b in placed if int(b["position"]) == position), None)
            if existing is not None:
                if int(existing["resourceId"]) == resource_id:
                    replies.append({"id": int(existing["buyId"]), "position": position})
                continue
            record = {
                "resourceId": resource_id,
                "position": position,
                "buyId": next_id,
                "level": 1,
            }
            placed.append(record)
            replies.append({"id": next_id, "position": position})
            next_id += 1
            money -= _ALL_BUILDING_PRICES[resource_id]
            changed = True
        elif action == 2:  # Config.QUEUE_TYPE_ADD_DECORATION
            try:
                resource_id = int(params["tid"])
                position = int(params["pos"])
                rotation = int(params.get("rotation", 0))
            except (KeyError, TypeError, ValueError):
                continue
            if resource_id not in _ALL_DECORATION_PRICES or not 0 <= position < 10000:
                continue
            price = _ALL_DECORATION_PRICES[resource_id]
            if money < price:
                print(f"[save] decoration {resource_id} denied: need {price}, have {money}")
                continue
            duplicate = False
            for group in decorations:
                if int(group.get("tid", -1)) != resource_id:
                    continue
                entries = [x for x in str(group.get("layout", "")).split(",") if x]
                if any(int(x.split(":", 1)[0]) == position for x in entries):
                    duplicate = True
                    replies.append({"id": int(group.get("id", 0)), "position": position})
                    break
            if duplicate:
                continue
            group = next((g for g in decorations if int(g.get("tid", -1)) == resource_id), None)
            if group is None:
                group = {"id": next_decoration_id, "tid": resource_id, "level": 1, "layout": ""}
                decorations.append(group)
                next_decoration_id += 1
            token = f"{position}:{rotation}"
            group["layout"] = token if not group.get("layout") else str(group["layout"]) + "," + token
            replies.append({"id": int(group["id"]), "position": position})
            money -= price
            changed = True
        elif action == 3:  # Config.QUEUE_TYPE_MOVE_DECORATION
            try:
                resource_id = int(params["tid"])
                old_pos = int(params["oldPos"])
                new_pos = int(params["newPos"])
                rotation = int(params.get("rotation", 0))
            except (KeyError, TypeError, ValueError):
                continue
            group = next((g for g in decorations if int(g.get("tid", -1)) == resource_id), None)
            if group is None:
                continue
            entries = [x for x in str(group.get("layout", "")).split(",") if x]
            changed_entry = False
            for i, token in enumerate(entries):
                try:
                    pos = int(token.split(":", 1)[0])
                except (ValueError, IndexError):
                    continue
                if pos == old_pos:
                    entries[i] = f"{new_pos}:{rotation}"
                    changed_entry = True
                    break
            if changed_entry:
                group["layout"] = ",".join(entries)
                changed = True
        elif action == 4:  # Config.QUEUE_TYPE_REMOVE_DECORATION
            try:
                resource_id = int(params["tid"])
                position = int(params["pos"])
            except (KeyError, TypeError, ValueError):
                continue
            group = next((g for g in decorations if int(g.get("tid", -1)) == resource_id), None)
            if group is None:
                continue
            entries = [x for x in str(group.get("layout", "")).split(",") if x]
            kept = []
            removed = False
            for token in entries:
                try:
                    pos = int(token.split(":", 1)[0])
                except (ValueError, IndexError):
                    kept.append(token)
                    continue
                if pos == position and not removed:
                    removed = True
                    continue
                kept.append(token)
            if removed:
                group["layout"] = ",".join(kept)
                changed = True
                if not group["layout"]:
                    decorations.remove(group)
        elif action == 9:  # Config.QUEUE_TYPE_ADD_PLANT {seedId, pos, pid}
            try:
                seed_id = int(params["seedId"])
                position = int(params["pos"])
            except (KeyError, TypeError, ValueError):
                continue
            if (seed_id not in _SEED_DEFS
                    or seed_id not in _SEEDS_WITH_ART
                    or not 0 <= position < 10000):
                continue
            if any(int(p.get("position", -1)) == position for p in plants):
                continue
            ready = (datetime.datetime.now(datetime.timezone.utc)
                     + datetime.timedelta(seconds=_SEED_GROW_SECONDS))
            plants.append({
                "id": next_plant_id,
                # id the client gave it this session - a move sent before
                # the next reload still refers to it by this one
                "clientPid": params.get("pid"),
                "seedId": seed_id,
                "position": position,
                "harvestTime": _harvest_time_str(ready),
            })
            next_plant_id += 1
            changed = True
        elif action == 10:  # Config.QUEUE_TYPE_MOVE_PLANT {pid, pos}
            try:
                plant_id = int(params["pid"])
                position = int(params["pos"])
            except (KeyError, TypeError, ValueError):
                continue
            match = next((p for p in plants if int(p.get("id", -1)) == plant_id), None)
            if match is None:
                match = next((p for p in plants
                              if str(p.get("clientPid")) == str(params.get("pid"))), None)
            if match is not None and 0 <= position < 10000:
                match["position"] = position
                changed = True
        elif action in (1, 11):  # move building, sell function house
            try:
                buy_id = int(params["bid"])
            except (KeyError, TypeError, ValueError):
                continue
            match = next((b for b in placed if int(b.get("buyId", -1)) == buy_id), None)
            if match is None:
                continue
            if action == 1:
                try:
                    position = int(params["pos"])
                except (KeyError, TypeError, ValueError):
                    continue
                if 0 <= position < 10000 and position != int(match["position"]):
                    match["position"] = position
                    changed = True
            else:
                placed.remove(match)
                money += int(_ALL_BUILDING_PRICES.get(int(match["resourceId"]), 0) * 0.1)
                changed = True

    updates = ({
        "placedBuildings": placed,
        "nextBuildingId": next_id,
        "decorations": decorations,
        "nextDecorationId": next_decoration_id,
        "plants": plants,
        "nextPlantId": next_plant_id,
        "money": money,
    } if changed else {})
    return updates, replies


def null_list_payload():
    """Same as generic_payload(), but with list:None instead of list:[].
    Still used as I1003's zero-friends case: Flow.onLoadPlayerFriendsComplete
    only takes its safe self-identity fallback branch when list is null, not
    when it is merely empty - see i1003_payload() below, which returns this
    whenever the active account has no accepted friends, and a real
    populated list otherwise."""
    return {"result": True, "list": None, "code": 0}


def i1003_payload():
    """Real friends list for services.I1003 (Flow.requestPlayerFriends).
    Each entry needs pushFriendData(entry, true) called client-side to
    actually register as a friend rather than merely being counted - see
    the AS3 patch to Flow.onLoadPlayerFriendsComplete's previously-empty
    loop body. Falls back to null_list_payload() (list: None, not list: [])
    when there are no friends yet, preserving the existing empty-vs-null
    workaround for that case."""
    friends = friends_of_active_account()
    if not friends:
        return null_list_payload()
    return {"result": True, "list": friends, "code": 0}


def i1004_payload():
    """Return the current player as a FriendVO-compatible record.

    This is also a compatibility fallback for unpatched clients. The patched
    main.swf receives the same identity earlier through I1001 so the town
    header can render it on the first frame.
    """
    identity = active_identity()
    identity["level"] = current_save()["level"]
    return {"result": True, "list": [identity], "code": 0}


def _scope_body(body):
    """Point get_active_account() at the account this AMF body belongs to."""
    token = None
    try:
        args = amf.decode_amf_args(body.value_bytes)
        if "I1001" in body.target:
            # sendAndCall("services.I1001", cb, "" + userId, sessionKey)
            token = args[1] if len(args) > 1 else None
        elif len(args) >= 3:
            # AmfCaller prefix: [uid, md5 signature, POPCAP_ID, ...]
            token = args[2]
    except Exception:
        token = None
    if isinstance(token, str) and token.startswith(_WEB_TOKEN_PREFIX):
        _request_ctx.scoped = True
        _request_ctx.username = session_username(token)
        _request_ctx.token = token
        if _request_ctx.username is None:
            print(f"    [session] unknown/expired web session {token[:12]}... - "
                  "using the default local save for this call. Reload /play.")
    else:
        _request_ctx.scoped = False
        _request_ctx.username = None
        _request_ctx.token = None


def build_amf_response(bodies):
    with _state_lock:
        return _build_amf_response_locked(bodies)


def _build_amf_response_locked(bodies):
    responses = []
    for body in bodies:
        payload = None
        _scope_body(body)
        who = get_active_account() or "local save"
        print(f"    [amf] target={body.target!r} response={body.response!r} "
              f"({len(body.value_bytes)} bytes of args) account={who!r}")
        if "I1001" in body.target:
            payload = i1001_payload()
        elif "I2001" in body.target:
            payload = i2001_payload()
        elif "I1034" in body.target:
            payload = i1034_payload()
        elif "I1007" in body.target:
            # Adventure/MissionListPanel requests the mission list that is
            # actually displayable/selectable.  The previous build returned
            # the entire 1..10 catalogue, but the client then filtered it with
            # its unlock state and ended up rendering only the original
            # tutorial card.  Return exactly the levels currently unlocked by
            # the saved progression, and include the display fields the panel
            # normally gets from the mission config.
            save = _normalize_progress(current_save())
            write_current_save(
                levelsFinished=save["levelsFinished"],
                unlockedLevels=save["unlockedLevels"],
                unlockedPlants=save["unlockedPlants"],
            )
            mission_rows = []
            # List EVERY level: the panel builds its list from these rows
            # (MissionListPanel patch) and shows locked ones with the game's
            # own padlock ("complete X first") from preMissions + unlocks["5"].
            for mid in range(1, _max_level() + 1):
                info = _level_info(mid)
                if info is None:
                    continue
                # Normalize every non-tutorial Adventure mission to the
                # ordinary Adventure mode before it reaches the client.
                # Do not let a legacy tutorial/type/mode flag leak into a
                # normal level and suppress CardSelectorHelper.
                normal = int(info.get("type", 1) or 1) == 1
                mission_type = 1 if normal else int(info["type"])
                resource_id = int(info.get("resourceId", mid) or mid)
                display_mission_id = resource_id * 10 if normal and resource_id else mid
                if normal:
                    prev_mid = mid - 1
                    prev_info = _level_info(prev_mid) if prev_mid > 0 else None
                    prev_external = ((int(prev_info.get("resourceId", 0) or 0) * 10)
                                     if prev_info and int(prev_info.get("type", 1) or 1) == 1
                                     else (prev_mid if prev_mid > 0 else 0))
                    pre_missions = ["null"] if mid <= 4 else [str(prev_external)]
                    difficulty_rows = list(info.get("difficulties", []))
                else:
                    pre_missions = ["null"] if mid == 1 else [str(mid - 1)]
                    difficulty_rows = []
                row = {
                    "id": str(display_mission_id),
                    "missionId": int(display_mission_id),
                    "resourceId": resource_id,
                    "progressId": mid,
                    "category": info["category"],
                    "name": info["name"],
                    "description": info["description"],
                    "img": info["img"],
                    "difficulty": 0,
                    "maxDifficulty": int(info.get("maxDifficulty", 0) or 0),
                    "difficulties": difficulty_rows,
                    "difficultyList": difficulty_rows,
                    "levelRequired": 0,
                    "preMissions": pre_missions,
                    "contractFee": 0,
                    "energyConsuming": 0,
                    "type": mission_type,
                    "modeId": 1 if normal else int(info["type"]),
                    "completed": mid in save["levelsFinished"],
                    "unlocked": True,
                }
                # Explicitly identify normal levels as NOT tutorial.  This is
                # kept false rather than omitted so clients that deserialize
                # the optional flag cannot retain a stale/default tutorial
                # state from an older mission object.
                row["isTutorial"] = False if normal else True
                mission_rows.append(row)
                # One row per difficulty: MissionListPanel groups rows by
                # resourceId into _missionArr[difficulty], and the confirm
                # panel's 容易/普通/困难/地狱 tabs read _missionArr[0..3].id.
                if normal and resource_id:
                    for drow in list(info.get("difficulties", []))[1:4]:
                        extra = dict(row)
                        extra["id"] = str(int(drow["missionId"]))
                        extra["missionId"] = int(drow["missionId"])
                        extra["difficulty"] = int(drow["difficulty"])
                        mission_rows.append(extra)
            print(f"[progress] I1007 displayable={sorted(save['unlockedLevels'])} "
                  f"finished={save['levelsFinished']} plants={save['unlockedPlants']}")
            payload = {
                "result": True,
                "list": mission_rows,
                "unlockedLevels": [str(x) for x in sorted(save["unlockedLevels"])],
                "completedLevels": [str(x) for x in sorted(save["levelsFinished"])],
                "code": 0,
            }
        elif "I1008" in body.target:
            # Mission settings are generated for every exposed level.
            # Values stay compatible with the existing playable tutorial and
            # gradually add waves/zombie types for the later selectable levels.
            try:
                args = service_args(body)
            except Exception:
                args = []
            mission_id = args[0] if args else 1
            requested_difficulty = args[1] if len(args) > 1 else None
            info, difficulty, resolved_mission_id = _resolve_mission_request(mission_id, requested_difficulty)
            waves = int(info["waves"])
            difficulty_rows = list(info.get("difficulties", []))
            selected_difficulty = difficulty_rows[difficulty] if difficulty_rows and difficulty < len(difficulty_rows) else {
                "difficulty": difficulty, "cdMinutes": 0, "gold": int(info.get("gold", 0) or 0),
                "exp": int(info.get("exp", 0) or 0), "note": "",
            }
            # Normal Adventure missions must always enter the client's real
            # CardSelectorHelper flow.  Tutorial missions keep their special
            # scripted flow and must never open this panel.
            is_normal_adventure = info["type"] == 1
            progress = _normalize_progress(current_save())
            owned_plants = [str(x) for x in sorted(progress["unlockedPlants"])]
            card_slots = max(5, min(10, int(progress.get("seedSlots", 6) or 6)))
            payload = {
                "result": True,
                "setting": {
                    # MissionVO.modeId is what the client Tutorial getters
                    # inspect.  Values 3/4/5 are the three tutorial modes;
                    # normal Adventure must be an ordinary mode (1).
                    # Keep both the original response names and the explicit
                    # MissionVO-style aliases because different offline
                    # client builds consume different fields.
                    # Normal Adventure is always mode/type 1.  Never pass
                    # tutorial modes 3/4/5 through for a non-tutorial level.
                    "type": 1 if is_normal_adventure else info["type"],
                    "modeId": 1 if is_normal_adventure else info["type"],
                    "scene": info["scene"],
                    "sceneId": info["scene"],
                    "totalWaves": waves,
                    "initSun": info["initSun"],
                    "initTomb": 0,
                    "allowedZombies": list(info["zombies"]),
                    "allowedZombiesArr": list(info["zombies"]),
                    "appearZombieIdArr": list(info["zombies"]),
                    "initPlant": [],
                    "forcedCards": [],
                    "forbiddenCards": [],
                    "flagWave": info["flagWave"],
                    "specialFirstAllowWave": "",
                    "specialValue": "",
                    "specialWeight": "",
                    # the client shows prize * totalWaves on the confirm panel
                    "expPrize": round(int(selected_difficulty.get("exp", info["exp"])) / float(waves), 4),
                    "tokenPrize": round(int(selected_difficulty.get("gold", info["gold"])) / float(waves), 4),
                    "difficultCoefficient": 30,
                    "missionName": info["name"],
                    "missionId": int(resolved_mission_id),
                    "resourceId": int(info.get("resourceId", 0) or 0),
                    "progressId": int(info.get("progressId", 0) or 0),
                    "difficulty": int(difficulty),
                    "maxDifficulty": int(info.get("maxDifficulty", 0) or 0),
                    "difficulties": difficulty_rows,
                    "difficultyList": difficulty_rows,
                    "cooldownMinutes": int(selected_difficulty.get("cdMinutes", 0) or 0),
                    "goldReward": int(selected_difficulty.get("gold", info["gold"])),
                    "expReward": int(selected_difficulty.get("exp", info["exp"])),
                    # MissionConfirmPanel shows the first itemPrize entry as the
                    # reward card (card item id == plant id, picture item_<id>).
                    "itemPrize": {str(pid): 1 for pid in info.get("plantRewards", [])[:1]},
                    "contractFee": 0,
                    "energyConsuming": 0,
                    # The original client uses mission type to distinguish
                    # the three tutorial modes from ordinary Adventure.
                    # These explicit fields document/echo the same decision
                    # for the offline server: type 1 gets card selection;
                    # tutorial types 3/4/5 do not.
                    "isTutorial": not is_normal_adventure,
                    "showCardSelector": is_normal_adventure,
                    "cardSelectionEnabled": is_normal_adventure,
                    "cardSelectorEnabled": is_normal_adventure,
                    "needCardSelector": is_normal_adventure,
                    "ownedPlants": owned_plants,
                    "ownedCards": owned_plants,
                    "plantIds": owned_plants,
                    "cardSlots": card_slots,
                    "maxCardNum": card_slots,
                    # Explicit plant-card -> seed-packet links.  The client
                    # still uses the normal plant card ids for CardPolicy, but
                    # these fields make the seed resource available to offline
                    # clients/builds that resolve the packet directly.
                    "cardList": [
                        {
                            "id": int(pid),
                            "itemId": int(pid),
                            "plantId": int(pid),
                            "seedId": int(_PLANT_TO_SEED_RESOURCE.get(int(pid), 0)),
                            "seedResourceId": int(_PLANT_TO_SEED_RESOURCE.get(int(pid), 0)),
                        }
                        for pid in owned_plants
                    ],
                    "seedPackets": [
                        {
                            "plantId": int(pid),
                            "seedId": int(_PLANT_TO_SEED_RESOURCE.get(int(pid), 0)),
                            "img": (f"item_{_PLANT_TO_SEED_RESOURCE.get(int(pid), 0)}"
                                    if _PLANT_TO_SEED_RESOURCE.get(int(pid), 0) else ""),
                        }
                        for pid in owned_plants
                        if _PLANT_TO_SEED_RESOURCE.get(int(pid), 0)
                    ],
                    "selectedCards": [],
                    "oldCardsVOs": [],
                },
                "code": 0,
            }
            print(f"[progress] I1008 request={mission_id} resolved={resolved_mission_id} "
                  f"level={info.get('resourceId', info.get('progressId', 0))} {info['name']} "
                  f"difficulty={difficulty} type={info['type']} scene={info['scene']} "
                  f"waves={waves} zombies={info['zombies']}")
        elif "I1033" in body.target:
            # TownFlow.loadHouseSetting(): house template id -> list of mission
            # resourceIds the house's adventure panel may show. The practice
            # house (701) hosts the whole catalogue; I1007 decides which of
            # them are unlocked and therefore visible.
            payload = {
                "result": True,
                # Practice house (701) and the people houses 706-715 (前院 / 水池
                # cabins and their upgrades) all host the whole adventure.
                # The ids must be the rows' resourceIds from I1007 (tutorials 1-3,
                # 前院 11-20, 水池 31-36), not catalogue positions - with positions
                # the pool levels (31+) never matched and were hidden.
                # A list starting with 0 marks the rampage house: TownFlow.
                # resetRampageBt() only shows the rampage gravestone (rpBt) if
                # some PeopleHouse's list has [0] <= 0. openAdventureForHouse()
                # skips ids <= 0, so the adventure list itself is unchanged.
                "list": dict({"701": [0] + _house_mission_resource_ids()},
                             **{str(tid): _house_mission_resource_ids() for tid in range(706, 716)}),
                "code": 0,
            }
        elif "I4002" in body.target:
            # AdventureGame.start() asks the server to start a TD mission and
            # BasicGame.enterTD() consumes response["uuid"].  Keep the mission
            # id attached to that UUID so the later I4003 completion call can
            # persist the correct level for this account.
            try:
                args = service_args(body)
            except Exception:
                args = []
            raw_mission_id = args[0] if args else 0
            requested_difficulty = args[1] if len(args) > 1 else None
            resolved_info, difficulty, resolved_mission_id = _resolve_mission_request(raw_mission_id, requested_difficulty)
            # Completion/progression is tracked by the internal sequential
            # level index, while the actual mission id keeps the real
            # resourceId*10+difficulty identity.
            mission_id = int(resolved_info.get("progressId", 0) or 0) if resolved_info else 0
            battle_uuid = "offline-" + secrets.token_hex(12)
            with _BATTLE_SESSIONS_LOCK:
                _BATTLE_SESSIONS[battle_uuid] = {
                    "account": get_active_account(),
                    "missionId": mission_id,
                    "missionExternalId": int(resolved_mission_id),
                    "difficulty": int(difficulty),
                }
            payload = {
                "result": True,
                "uuid": battle_uuid,
                "code": 0,
            }
            print(f"[td] started request={raw_mission_id} resolved={resolved_mission_id} "
                  f"progressId={mission_id} difficulty={difficulty} uuid={battle_uuid}")
        elif "I4003" in body.target:
            # AdventureGame calls I4003 at the end of a TD win. The first
            # argument is normally the battle UUID and the final argument is
            # the win flag. Some Flash/AMF builds encode that flag as a string,
            # so do not use Python's bool("false") semantics here.
            try:
                args = service_args(body)
            except Exception:
                args = []
            battle_uuid = str(args[0]) if args else ""
            raw_won = args[-1] if args else False
            if isinstance(raw_won, str):
                won = raw_won.strip().lower() not in ("", "0", "false", "no", "null")
            else:
                won = bool(raw_won)
            session = None
            with _BATTLE_SESSIONS_LOCK:
                session = _BATTLE_SESSIONS.get(battle_uuid)
            active_account = get_active_account() or "local save"
            reward_gold, reward_exp = 0, 0
            prizes = {}
            if won and session:
                session_account = session.get("account") or "local save"
                # The battle UUID is generated locally by I4002, so it is the
                # authoritative link to the mission. Keep the account check
                # when both sides are known, but don't throw away a real win
                # just because the projector omitted its optional account id.
                if session_account == active_account or session_account == "local save" or active_account == "local save":
                    try:
                        mission_id = int(session.get("missionId", 0) or 0)
                    except (TypeError, ValueError):
                        mission_id = 0
                    if mission_id > 0:
                        plants_before = set(_normalize_progress(current_save()).get("unlockedPlants", []))
                        saved = _persist_progress_for_completed_mission(mission_id)
                        # GameOverPanel shows every entry of "prizes" in its 特殊奖励 box,
                        # pops up the new-plant card for card ids <= 100 and adds plant
                        # cards to ownCardsData at once - so the almanac and the seed
                        # screen show the new plant without restarting the game.
                        new_plants = sorted(set(saved.get("unlockedPlants", [])) - plants_before)
                        prizes = {str(pid): 1 for pid in new_plants}
                        info = _level_info(mission_id)
                        # remember the real mission id won (e.g. 110 = 前院1-1 easy):
                        # the client marks levels completed / unlocks the next one
                        # and the next difficulty from these ids (unlocks["5"]).
                        ext_id = int(session.get("missionExternalId", 0) or 0)
                        diff = int(session.get("difficulty", 0) or 0)
                        if ext_id > 0:
                            cur = current_save()
                            done = set(int(x) for x in cur.get("missionsFinished", []) if str(x).lstrip("-").isdigit())
                            first_clear = ext_id not in done
                            done.add(ext_id)
                            write_current_save(missionsFinished=sorted(done))
                            # First clear of a level: show its reward plant(s) in the
                            # unlock screen even if already owned (older saves got some
                            # plants from a previous reward order, e.g. Potato Mine /
                            # Snow Pea, and then 1-2 / 1-3 showed nothing).
                            if first_clear and info:
                                for pid in info.get("plantRewards", []) or []:
                                    prizes[str(pid)] = 1
                        diffs = info.get("difficulties") or [] if info else []
                        if info and 0 <= diff < len(diffs):
                            reward_gold, reward_exp = int(diffs[diff].get("gold", 0)), int(diffs[diff].get("exp", 0))
                            cur = current_save()
                            write_current_save(money=int(cur.get("money", 0)) + reward_gold,
                                               experience=int(cur.get("experience", 0)) + reward_exp)
                        elif info and (info["gold"] or info["exp"]):
                            reward_gold, reward_exp = int(info["gold"]), int(info["exp"])
                            cur = current_save()
                            write_current_save(money=int(cur.get("money", 0)) + reward_gold,
                                               experience=int(cur.get("experience", 0)) + reward_exp)
                        print(f"[td] completed mission={mission_id} account={active_account} "
                              f"gold=+{reward_gold} exp=+{reward_exp} plants={saved.get('unlockedPlants', [])}")
            payload = {
                "result": True,
                "money": 0,
                "token": reward_gold,     # GameOverPanel shows token = coins won, exp = experience won
                "exp": reward_exp,
                "prizes": prizes,         # newly unlocked plant cards {plantId: 1}
                "code": 0,
            }
        elif "I1023" in body.target:
            payload = i1023_payload()
        elif "I1003" in body.target:
            payload = i1003_payload()
        elif "I1004" in body.target:
            payload = i1004_payload()
        elif "I5004" in body.target:
            # Flow.refreshMyItems() -> I5004 -> setMyItemsListS2C(): the client
            # CLEARS ownCardsData and rebuilds it from this reply. With the old
            # generic {result: true} reply every plant became locked (almanac,
            # seed selection) after a level until the game was reloaded - only
            # a just-won plant (added by the result screen) stayed unlocked.
            # Send exactly the inventory the login reply (I1001) carries.
            payload = {"result": True, "code": 0, "list": i1001_payload().get("items", {})}
            print("[items] I5004 inventory refresh: "
                  + ", ".join(f"type {k}: {len(v)}" for k, v in payload["list"].items()))
        elif "I1019" in body.target:
            # sendAndCall("services.I1019", null, DataManager.TUTORIAL_STEP_X):
            # the client marks a one-time tutorial prompt as seen (e.g.
            # TUTORIAL_STEP_ADVENTURE = 65536, the difficulty prompt on the
            # first level confirm panel). Save the bit so it shows once.
            try:
                args = service_args(body)
                bit = int(args[0]) if args else 0
            except (TypeError, ValueError, IndexError):
                bit = 0
            if bit > 0:
                cur = current_save()
                step = int(cur.get("tutorialStep", 0) or 0)
                if step & bit == 0:
                    write_current_save(tutorialStep=step | bit)
                    print(f"[save] I1019 tutorial bit {bit} saved (tutorialStep {step} -> {step | bit})")
            payload = {"result": True, "code": 0}
        elif "I4008" in body.target:
            # Rampage leaderboard (LeaderBoard.setLeaderBoardListS2C reads
            # reply.leaderboard[*] = {uid, score, teamScore}). Offline: just
            # the player, with the best rampage score saved by I4010.
            best = int(current_save().get("rampageBestScore", 0) or 0)
            uid = active_identity()["uid"]
            payload = {"result": True, "code": 0,
                       "leaderboard": {"0": {"uid": uid, "score": best, "teamScore": best}}}
        elif "I4010" in body.target:
            # End of a real rampage run: RamPageGame -> I4010(uuid, score, stats,
            # isGameWin) -> showRampageAwardUI(reply). Pay coins/exp from the score.
            try:
                args = service_args(body)
                score = int(float(args[1])) if len(args) > 1 else 0
            except (TypeError, ValueError, IndexError):
                score = 0
            token = min(5000, max(100, score // 10))
            exp = min(500, max(10, score // 100))
            cur = current_save()
            write_current_save(money=int(cur.get("money", 0)) + token,
                               experience=int(cur.get("experience", 0)) + exp,
                               rampageBestScore=max(int(cur.get("rampageBestScore", 0) or 0), score))
            print(f"[rampage] I4010 score={score} -> +{token} coins, +{exp} exp")
            payload = {"result": True, "code": 0, "token": token, "tokenBonus": 0, "exp": exp, "expBonus": 0}
        elif "I7017" in body.target:
            payload = i7017_payload()
        elif body.target.rstrip().endswith("I1016"):
            # Tutorial progression callback.  Some client builds call this
            # between tutorial stages, while the final call is the tutorial
            # completion callback.  Read a small numeric stage argument when
            # present; if the build supplies no stage, this is the final
            # completion callback.  Stage 2 grants Cherry Bomb early so its
            # seed packet is available inside Tutorial 3 itself.  Stage 3
            # completes Tutorial 3 and unlocks the first real Adventure level.
            try:
                args = service_args(body)
            except Exception:
                args = []
            stage = None
            for value in reversed(args):
                try:
                    iv = int(value)
                except (TypeError, ValueError):
                    continue
                if iv in (1, 2, 3):
                    stage = iv
                    break
            if stage == 1:
                _persist_progress_for_completed_mission(1)
                if int(current_save().get("tutorialStep", 0) or 0) < 3:   # never undo a finished tutorial (replays)
                    write_current_save(tutorialStep=1, skippedTutorial=False)
                print("[progress] I1016 tutorial stage 1; Tutorial 1 completed, Tutorial 2 unlocked")
            elif stage == 2:
                _persist_progress_for_completed_mission(2)
                save = _normalize_progress(current_save())
                plants = set(save["unlockedPlants"])
                plants.add(17)
                if int(save.get("tutorialStep", 0) or 0) < 3:   # never undo a finished tutorial (replays)
                    write_current_save(unlockedPlants=sorted(plants), tutorialStep=2, skippedTutorial=False)
                else:
                    write_current_save(unlockedPlants=sorted(plants))
                print("[progress] I1016 tutorial stage 2; Tutorial 2 completed, Tutorial 3 unlocked, Cherry Bomb (17) granted")
            else:
                # Final/unspecified tutorial completion is normalized as the
                # full sequential chain so no prerequisite mission is missing.
                _persist_progress_for_completed_mission(1)
                _persist_progress_for_completed_mission(2)
                _persist_progress_for_completed_mission(3)
                save = _normalize_progress(current_save())
                plants = set(save["unlockedPlants"])
                plants.add(17)
                write_current_save(
                    tutorialStep=int(save.get("tutorialStep", 0) or 0) | _TUTORIAL_COMPLETE_FULL,  # keep rampage/prompt bits
                    skippedTutorial=False,
                    unlockedPlants=sorted(plants),
                )
                print("[progress] I1016 tutorial complete; Tutorials 1-3 finished, Cherry Bomb granted, first real Adventure level unlocked")
            payload = generic_payload()
        elif "I1016Skip" in body.target:
            # Cancel button on the TD-tutorial confirm dialog - see
            # TownTutorialFlow.skipTdTutorial(). Persists via
            # write_current_save() - the active website account's save if
            # one is logged in, otherwise local_save.json - so the tutorial
            # doesn't restart on next launch either way, no website visit
            # required. _TUTORIAL_COMPLETE_FULL (not just
            # TUTORIAL_STEP_COMPLETE=3) also see the comment on that
            # constant: without it, isCompleteTutorial goes true correctly,
            # but TownUIPanel's citizen/shop/card/rampage buttons check
            # their OWN individual bits and stay hidden regardless.
            _persist_progress_for_completed_mission(1)
            _persist_progress_for_completed_mission(2)
            _persist_progress_for_completed_mission(3)
            save = _normalize_progress(current_save())
            plants = set(save["unlockedPlants"])
            plants.add(17)
            write_current_save(
                tutorialStep=int(save.get("tutorialStep", 0) or 0) | _TUTORIAL_COMPLETE_FULL,  # keep rampage/prompt bits
                skippedTutorial=True,
                unlockedPlants=sorted(plants),
            )
            payload = generic_payload()
        elif "I2020" in body.target:
            # TownFlow.requestIncome() -> sendAndCall("services.I2020", null,
            # buyId) - fire-and-forget like every other queue-adjacent call,
            # so the response content doesn't matter, but this was never
            # handled at all before, meaning every income collection from a
            # BLD_TYPE_BIZ building played its money/exp drop animation
            # (itself confirmed working - see TownFlow.as's onGetPrizeResult
            # patch) without ever actually crediting the save. buyId alone
            # doesn't say which building or tier it was, but placedBuildings
            # (see the I2012 handler) already maps buyId -> resourceId once
            # a building's been placed, so that's used here to look up its
            # real per-tier income/exp from the same building settings the
            # shop itself uses - not a separate, potentially-inconsistent
            # number.
            try:
                args = service_args(body)
                buy_id = int(args[0]) if args else None
            except (ValueError, TypeError, IndexError) as exc:
                print(f"[save] I2020 argument decode failed: {exc}")
                buy_id = None
            if buy_id is not None:
                save = current_save()
                placed = save.get("placedBuildings", [])
                match = next((b for b in placed if int(b.get("buyId", -1)) == buy_id), None)
                if match is not None:
                    all_tiers = _extra_building_settings(True)  # active flag irrelevant here, just need income/exp
                    entry = all_tiers.get(str(match["resourceId"]))
                    if entry is not None:
                        write_current_save(
                            money=save["money"] + entry.get("income", 0),
                            experience=save["experience"] + entry.get("exp", 0),
                        )
            payload = generic_payload()
        elif "I2012" in body.target:
            # AmfCaller prepends three common arguments before queueArr.
            # Manager.__onBuildComplete also reads the returned building id,
            # which must match the id supplied by I2001 on the next login.
            try:
                args = service_args(body)
                queue = args[0] if args else []
                updates, replies = apply_town_queue(current_save(), queue)
                if updates:
                    write_current_save(**updates)
                    print(f"[save] I2012 saved {len(updates['placedBuildings'])} placed building(s)")
                if replies:
                    payload = {"result": True, "buildings": replies, "code": 0}
                elif queue and not updates:
                    print("[save] I2012 decoded the queue but found no supported building change")
            except (ValueError, TypeError, KeyError) as exc:
                print(f"[save] I2012 placement decode failed: {exc}")
            if payload is None:
                payload = generic_payload()
        elif "I2015" in body.target:
            # PlantBuilding harvest: sendAndCall(DEventManager.CMD_SELL_PLANT =
            # "services.I2015", sellSunFlowerEffect, buyId). The client drops the
            # coins and empties the plot; remove the plant from the save too,
            # otherwise it came back after a restart.
            try:
                args = service_args(body)
                plant_id = int(args[0]) if args else -1
            except (TypeError, ValueError, IndexError):
                plant_id = -1
            cur = current_save()
            plants = [dict(p) for p in cur.get("plants", [])]
            match = next((p for p in plants if int(p.get("id", -1) or -1) == plant_id), None)
            if match is not None:
                plants.remove(match)
                gain = int(_plant_settings().get(str(match.get("seedId")), {}).get("yield", 0) or 0)
                write_current_save(plants=plants, money=int(cur.get("money", 0)) + gain)
                print(f"[save] I2015 harvested plant id={plant_id} seed={match.get('seedId')} +{gain} coins")
            else:
                print(f"[save] I2015 harvest: no saved plant with id={plant_id}")
            payload = {"result": True, "code": 0}
        elif "I2017" in body.target:
            # Planting a seed: Manager sends the add-plant queue (I2012,
            # action 9) and then sendAndCall("services.I2017",
            # __onPlantComplete, seedId, position). __onPlantComplete reads
            # param1.plant.id / .position and stores the id as the plant's
            # buyId, so later moves refer to the saved plant. Both requests
            # go through apply_town_queue, which ignores a second add at the
            # same position - so whichever arrives first records the plant.
            payload = i2017_payload(body)
        elif "I2021" in body.target:
            # CitizenListPanel.confirmUpgradeBld() -> sendAndCall("services.I2021",
            # this.upGpgradeResult, this.selBld.buyId). Confirmed directly:
            # upGpgradeResult() ignores its param1 entirely - the whole
            # upgrade (which tier to become, new stats, new art) is computed
            # client-side from itemConfArr via a groupId+level search, then
            # applied locally. So this response's content genuinely doesn't
            # matter, same as I2020's income collection.
            #
            # Upgrade cost and level changes remain a separate persistence
            # task. I2012 now tracks the placed instance id, but this call
            # does not yet update its tier.
            payload = generic_payload()
        elif "I5013" in body.target:
            # Flow.onGetAlmancResource()'s inner callback:
            # DataManager.upgradeCard = param1.list; if null, = new Object()
            # - already null-safe, so the generic fallback's empty list
            # was fine here too. Modeled explicitly anyway for clarity: this
            # is per-card upgrade LEVEL tracking (keyed by permanentId, per
            # ComposeCardModel.initModel()), separate from the config-per-
            # target-level table in conf/PlantData.xml's <upgradeConfig> -
            # empty means "nothing's been upgraded yet", which is correct
            # for every card here.
            payload = generic_payload()
        elif "I1017" in body.target:
            # AlmanacDialog.show()/getAlmanacS2C() - fired once, the first
            # time the almanac opens (zombiesConfigMap/synthesisConfigMap
            # start empty). ZombiesContainer.setZombiesWithPage() reads
            # zombiesConfigMap.get(zombieId).dropList/.rareDropList
            # unconditionally - with zombieSettings empty (as it was before
            # this), that lookup returns null and .dropList on null throws
            # #1009 the moment the zombie tab is opened. No real drop-table
            # data exists for this reconstruction, so both lists are just
            # empty - that's enough to not crash, not to show real drops.
            payload = generic_payload()
            payload["zombieSettings"] = {
                str(zid): {"dropList": [], "rareDropList": []}
                for zid in _ZOMBIE_ALMANAC_IDS
            }
            payload["synthesisSettings"] = {}
        elif "I5001" in body.target:
            # I5001 is intentionally shared by two client features:
            #   * shop purchases send a numeric resourceId
            #   * TownBaseMap.confirmUnlock() sends "" + areaIndex, i.e. a
            #     STRING.  AMF preserves that distinction, so do not coerce
            #     the argument before deciding which operation it represents.
            payload = None
            try:
                args = service_args(body)
                raw_arg = args[0] if args else None
                quantity = int(args[1]) if len(args) > 1 else 1
            except (ValueError, TypeError, IndexError) as exc:
                print(f"[save] I5001 argument decode failed: {exc}")
                raw_arg = None
                quantity = 1

            if isinstance(raw_arg, str):
                # Area unlock: the client sends the zero-based area index as
                # a string.  Unlocks are sequential: the only valid next
                # area is the current number of already-open areas.
                try:
                    area_index = int(raw_arg)
                except (TypeError, ValueError):
                    area_index = -1
                save = current_save()
                unlocked = sorted({int(x) for x in save.get("unlockedAreas", [8, 9, 12, 13])})
                # The starter area is a non-sequential 12x12 rectangle (8,9,12,13),
                # so the old "next area == len(unlocked)" rule cannot be used.
                # The client sends the ACTUAL plot the player clicked.  Allow any
                # currently locked plot to be purchased, while using the current
                # number of open plots to select the next price. This keeps the
                # price shown by TownBaseMap (which indexes unlockRules by
                # opendAreaTileList.length) in sync with the server.
                if area_index in range(16) and area_index not in unlocked:
                    rules = _land_plot_unlock_rules()["2"]
                    rule = rules.get(str(len(unlocked)))
                    if rule is not None:
                        price = int(rule["money"])
                        if int(save.get("money", 0)) >= price:
                            unlocked.append(area_index)
                            unlocked = sorted(set(unlocked))
                            write_current_save(
                                money=int(save.get("money", 0)) - price,
                                unlockedAreas=unlocked,
                            )
                            payload = {
                                "result": True,
                                "items": [],
                                "code": 0,
                            }
                            print(f"[save] I5001 unlocked town area {area_index} for {price} coins")
                        else:
                            print(f"[save] I5001 area {area_index} denied: need {price}, have {save.get('money', 0)}")
                    else:
                        print(f"[save] I5001 no unlock rule for open-area count {len(unlocked)}")
                else:
                    print(f"[save] I5001 invalid/already-open area unlock: requested={area_index}")
            else:
                # Existing shop/card purchase path.  Keep the original numeric
                # semantics completely intact.
                try:
                    resource_id = int(raw_arg)
                except (ValueError, TypeError):
                    resource_id = None
                if resource_id is not None and resource_id in _PLANT_ALMANAC_IDS:
                    if _buy_plant_with_gems(resource_id):
                        payload = {"result": True, "items": [{"tid": resource_id, "count": 1}], "code": 0}
                elif resource_id is not None and resource_id in _ALL_BUILDING_PRICES:
                    price = _ALL_BUILDING_PRICES[resource_id]
                    save = current_save()
                    owned = list(save.get("ownedBuildings", []))
                    owned.append(resource_id)
                    write_current_save(money=save["money"] - price, ownedBuildings=owned)
                    payload = {
                        "result": True,
                        "items": [{"tid": resource_id, "count": owned.count(resource_id)}],
                        "code": 0,
                    }
                elif resource_id is not None and resource_id in _FUNCTION_CARD_PRICES:
                    price = _FUNCTION_CARD_PRICES[resource_id]
                    save = current_save()
                    owned_cards = list(save.get("ownedFunctionCards", []))
                    owned_cards.append(resource_id)
                    write_current_save(money=save["money"] - price, ownedFunctionCards=owned_cards)
                    payload = {
                        "result": True,
                        "items": [{"tid": resource_id, "count": owned_cards.count(resource_id)}],
                        "code": 0,
                    }
            if payload is None:
                payload = generic_payload()
        elif "I1016Accept" in body.target:
            # Accept button - see TownTutorialFlow.completeTdTutorialWithoutBattle().
            # Same persisted end state as Skip (no real TD battle module in
            # this build to route into - see that function's comment), just
            # recorded as accepted rather than skipped.
            _persist_progress_for_completed_mission(1)
            _persist_progress_for_completed_mission(2)
            _persist_progress_for_completed_mission(3)
            save = _normalize_progress(current_save())
            plants = set(save["unlockedPlants"])
            plants.add(17)
            write_current_save(
                tutorialStep=int(save.get("tutorialStep", 0) or 0) | _TUTORIAL_COMPLETE_FULL,  # keep rampage/prompt bits
                skippedTutorial=False,
                unlockedPlants=sorted(plants),
            )
            payload = generic_payload()
        else:
            payload = generic_payload()
        responses.append((body.response, translate_payload(payload)))
    return responses


def _account_page_html():
    """Self-contained login/register/dashboard page for GET /accounts -
    plain fetch() calls against the JSON API below, no build step needed."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PvZ Social Offline - Accounts</title>
<style>
  body { font-family: system-ui, sans-serif; background: #1b2b1b; color: #eee; max-width: 480px; margin: 40px auto; padding: 0 20px; }
  h1 { color: #8fd94f; font-size: 22px; }
  .card { background: #24352c; border: 1px solid #3a5240; border-radius: 8px; padding: 20px; margin-bottom: 16px; }
  input { display: block; width: 100%; box-sizing: border-box; padding: 8px; margin: 6px 0 12px; border-radius: 4px; border: 1px solid #3a5240; background: #16211a; color: #eee; }
  button { background: #4a9c2e; color: #fff; border: none; padding: 9px 16px; border-radius: 4px; cursor: pointer; font-weight: bold; }
  button:hover { background: #5cb83a; }
  button.secondary { background: #555; }
  button.secondary:hover { background: #777; }
  .msg { margin-top: 10px; font-size: 14px; }
  .msg.error { color: #ff8a7a; }
  .msg.ok { color: #8fd94f; }
  .stat { display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px solid #2e4436; font-size: 14px; }
  .note { font-size: 12px; color: #9ab89a; margin-top: 12px; line-height: 1.5; }
  a { color: #8fd94f; }
</style>
</head>
<body>
<h1>PvZ Social Offline - Accounts</h1>
<div style="margin:-6px 0 14px"><select id="langSel" title="Language / 语言 / 語言" style="background:#16211a;color:#eee;border:1px solid #3a5240;border-radius:4px;padding:3px 6px;margin-right:6px"></select>
<script>
(async function(){
  const sel = document.getElementById("langSel");
  try {
    const r = await (await fetch("/api/language")).json();
    for (const [code, name] of Object.entries(r.languages)) {
      const o = document.createElement("option"); o.value = code; o.textContent = name;
      if (code === r.language) o.selected = true; sel.appendChild(o);
    }
  } catch (e) { sel.style.display = "none"; }
  sel.addEventListener("change", async function(){
    await fetch("/api/language", {method: "POST", headers: {"Content-Type": "application/json"},
                                  body: JSON.stringify({language: sel.value})});
    location.reload();
  });
})();
</script></div>
<div id="app">Loading...</div>

<script>
async function api(path, body) {
  const res = await fetch(path, {
    method: body === undefined ? "GET" : "POST",
    headers: body === undefined ? undefined : {"Content-Type": "application/json"},
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  return res.json();
}

function esc(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

async function render() {
  const app = document.getElementById("app");
  const state = await api("/api/whoami");

  if (!state.loggedIn) {
    app.innerHTML = `
      <div class="card">
        <h3>Log in</h3>
        <input id="li-user" placeholder="Username">
        <input id="li-pass" type="password" placeholder="Password">
        <button onclick="doLogin()">Log in</button>
        <div id="li-msg" class="msg"></div>
      </div>
      <div class="card">
        <h3>Create an account</h3>
        <input id="reg-user" placeholder="Username">
        <input id="reg-pass" type="password" placeholder="Password (4+ characters)">
        <button onclick="doRegister()">Create account</button>
        <div id="reg-msg" class="msg"></div>
      </div>
      <div class="note">
        Each phone, tablet or browser logs in separately and plays its own
        account, all through the one server running on the PC. Accounts are
        shared with the PC launcher, so an account made here can also be
        picked there (and vice versa).
      </div>`;
    return;
  }

  const s = state.save;
  const tutorialText = s.tutorialStep >= 3
    ? (s.skippedTutorial ? "Skipped" : "Completed")
    : "Not finished yet";
  app.innerHTML = `
    <div class="card">
      <h3>Logged in as ${esc(state.username)}</h3>
      <div class="stat"><span>Money</span><span>${s.money}</span></div>
      <div class="stat"><span>Gems</span><span>${s.gems}</span></div>
      <div class="stat"><span>Level</span><span>${s.level}</span></div>
      <div class="stat"><span>Experience</span><span>${s.experience}</span></div>
      <div class="stat"><span>Tutorial</span><span>${tutorialText}</span></div>
      <div class="stat"><span>Houses saved</span><span>${s.houses.length} (not wired up yet)</span></div>
      <div class="stat"><span>Levels finished</span><span>${s.levelsFinished.length} (no battle system yet)</span></div>
      <a href="/play"><button style="margin-top:14px;">Play in browser</button></a>
      <button class="secondary" onclick="doLogout()" style="margin-top:14px;">Log out</button>
    </div>
    <div class="note">
      "Play in browser" runs the game through Ruffle, a Flash emulator, so it
      works on Android phones and in any modern browser. On a phone, tap the
      play button once it appears, then use Full screen and hold the phone
      sideways. Money and level above are what's saved on the server; refresh
      this page to update them.
    </div>`;
}

async function doLogin() {
  const username = document.getElementById("li-user").value;
  const password = document.getElementById("li-pass").value;
  const r = await api("/api/login", {username, password});
  const msg = document.getElementById("li-msg");
  if (r.ok) { render(); } else { msg.textContent = r.error; msg.className = "msg error"; }
}

async function doRegister() {
  const username = document.getElementById("reg-user").value;
  const password = document.getElementById("reg-pass").value;
  const r = await api("/api/register", {username, password});
  const msg = document.getElementById("reg-msg");
  if (r.ok) { render(); } else { msg.textContent = r.error; msg.className = "msg error"; }
}

async function doLogout() {
  await api("/api/logout", {});
  render();
}

render();
</script>
</body>
</html>"""


def _play_page_html(username, token):
    """Ruffle page served at /play (needs a website login - do_GET redirects
    to /accounts otherwise). Works in desktop browsers and in Chrome /
    Firefox on Android.

    Ruffle (a Flash emulator in WebAssembly) is bundled in ruffle/ and a
    Chinese font subset in fonts/, so nothing is fetched from the internet
    and phones can play on a Wi-Fi network with no internet access.

    The window.util object is the same JavaScript bridge the original
    Renren page provided; Flow.as calls it through ExternalInterface:
      util.getAmfGateway -> this server, at whatever address the device used
                            (otherwise Config.HOST_URL's 127.0.0.1 would
                            point a phone at itself)
      util.getSessionKey -> this browser's login, which the server uses to
                            pick the right save for every call (see
                            "Multi-device play" in server.py)."""
    page = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no, viewport-fit=cover">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="theme-color" content="#000000">
<title>PvZ Social Offline - Play</title>
<style>
  html, body { margin: 0; padding: 0; width: 100%; height: 100%; background: #000; overflow: hidden;
               font-family: system-ui, sans-serif; overscroll-behavior: none; touch-action: none; }
  #wrap { position: fixed; inset: 0; display: flex; flex-direction: column; }
  #topbar { flex: 0 0 auto; background: #1b2b1b; color: #eee; font-size: 13px; padding: 5px 10px;
            display: flex; gap: 12px; align-items: center; justify-content: space-between; }
  #topbar a, #topbar button { color: #8fd94f; background: none; border: 1px solid #3a5240; border-radius: 4px;
            padding: 3px 9px; font-size: 13px; text-decoration: none; cursor: pointer; }
  #stage { flex: 1 1 auto; position: relative; min-height: 0; }
  #stage ruffle-player, #stage ruffle-object, #stage ruffle-embed { display: block; width: 100%; height: 100%; }
  #wrap:fullscreen #topbar { display: none; }
  #rotate { display: none; position: fixed; inset: 0; background: rgba(0,0,0,.88); color: #eee; z-index: 20;
            align-items: center; justify-content: center; text-align: center; font-size: 18px; padding: 30px; }
  #rotate button { margin-top: 18px; font-size: 16px; padding: 10px 18px; background: #4a9c2e; color: #fff;
            border: 0; border-radius: 6px; }
  @media (orientation: portrait) and (max-width: 900px) { #rotate.enabled { display: flex; } }
</style>
<script>
  // JavaScript bridge the game expects (see Flow.as / util.* calls).
  window.util = {
    getAmfGateway: function () { return location.origin + "/"; },
    getSessionKey: function () { return __TOKEN__; }
  };
  window.RufflePlayer = window.RufflePlayer || {};
  window.RufflePlayer.config = {
    publicPath: "/ruffle/",
    autoplay: "auto",            // phones need one tap before sound can play
    unmuteOverlay: "hidden",
    letterbox: "on",
    scale: "showAll",
    forceScale: true,            // always fit the 760x600 stage to the screen
    salign: "",
    forceAlign: true,            // ...and centre it (the game asks for top-left)
    backgroundColor: "#000000",
    quality: "medium",
    allowScriptAccess: true,
    logLevel: "warn",
    warnOnUnsupportedContent: false,
    openUrlMode: "deny",
    fontSources: ["/fonts/pvz-cjk.otf"],
    defaultFonts: {
      sans: ["Noto Sans CJK SC"],
      serif: ["Noto Sans CJK SC"],
      typewriter: ["Noto Sans CJK SC"]
    }
  };
</script>
<script src="/ruffle/ruffle.js"></script>
</head>
<body>
<div id="wrap">
  <div id="topbar">
    <span>Playing as <b>__USERNAME__</b></span>
    <span>
      <select id="langSel" title="Language / 语言 / 語言" style="background:#16211a;color:#eee;border:1px solid #3a5240;border-radius:4px;padding:3px 6px;margin-right:6px"></select>
      <script>
      (async function(){
        const sel = document.getElementById("langSel");
        try {
          const r = await (await fetch("/api/language")).json();
          for (const [code, name] of Object.entries(r.languages)) {
            const o = document.createElement("option"); o.value = code; o.textContent = name;
            if (code === r.language) o.selected = true; sel.appendChild(o);
          }
        } catch (e) { sel.style.display = "none"; }
        sel.addEventListener("change", async function(){
          await fetch("/api/language", {method: "POST", headers: {"Content-Type": "application/json"},
                                        body: JSON.stringify({language: sel.value})});
          location.reload();
        });
      })();
      </script>
      <button id="fsBtn" type="button">Full screen</button>
      <a href="/accounts">Accounts</a>
    </span>
  </div>
  <div id="stage">
    <object type="application/x-shockwave-flash" data="/main.swf" width="100%" height="100%">
      <param name="movie" value="/main.swf">
      <param name="allowScriptAccess" value="always">
      <param name="allowNetworking" value="all">
      <embed src="/main.swf" type="application/x-shockwave-flash" width="100%" height="100%"
             allowScriptAccess="always" allowNetworking="all">
    </object>
  </div>
</div>
<div id="rotate"><div>Turn your phone sideways to play.<br>
  <button type="button" onclick="goFull()">Full screen + landscape</button></div></div>
<script>
  var isTouch = ("ontouchstart" in window) || navigator.maxTouchPoints > 0;
  if (isTouch) document.getElementById("rotate").classList.add("enabled");
  function goFull() {
    var el = document.getElementById("wrap");
    var req = el.requestFullscreen || el.webkitRequestFullscreen;
    if (!req) return;
    Promise.resolve(req.call(el)).then(function () {
      if (screen.orientation && screen.orientation.lock) {
        screen.orientation.lock("landscape").catch(function () {});
      }
    }).catch(function () {});
  }
  document.getElementById("fsBtn").addEventListener("click", goFull);
  // Stop the page itself from scrolling/zooming while dragging the town.
  document.addEventListener("touchmove", function (e) { e.preventDefault(); }, { passive: false });
  document.addEventListener("contextmenu", function (e) { e.preventDefault(); });
</script>
</body>
</html>"""
    import html as _html
    return (page.replace("__TOKEN__", json.dumps(token or ""))
                .replace("__USERNAME__", _html.escape(username)))


def _session_cookie(token, expire=False):
    cookie = f"pvz_session={token}; Path=/; HttpOnly; SameSite=Lax"
    if expire:
        cookie += "; Max-Age=0"
    else:
        cookie += "; Max-Age=31536000"
    return cookie


class PvZServerHandler(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path):
        """Case-insensitive fallback for static files.

        The game asks for some files with a different letter case than they
        have on disk (conf/plantData.xml vs conf/PlantData.xml,
        conf/zombieData.xml vs conf/ZombieData.xml). Windows ignores case, so
        this never showed on the PC, but on Linux / Android hosting those
        requests 404 and the TD battle loads without plant or zombie data.
        If the exact path is missing, match each path part ignoring case."""
        real = super().translate_path(path)
        code = get_language()
        if code != DEFAULT_LANGUAGE:
            root_ = os.path.abspath(getattr(self, "directory", None) or os.getcwd())
            rel_ = os.path.relpath(real, root_)
            if not rel_.startswith("..") and not rel_.startswith("lang" + os.sep):
                alt = os.path.join(root_, "lang", code, rel_)
                if os.path.isfile(alt):
                    return alt
                # same case-insensitive matching as below, inside lang/<code>/
                cur = os.path.join(root_, "lang", code)
                for part in rel_.split(os.sep):
                    if not os.path.isdir(cur):
                        cur = None; break
                    low = part.lower()
                    match = next((n for n in os.listdir(cur) if n.lower() == low), None)
                    if match is None:
                        cur = None; break
                    cur = os.path.join(cur, match)
                if cur and os.path.isfile(cur):
                    return cur
        if os.path.exists(real):
            return real
        root = os.path.abspath(getattr(self, "directory", None) or os.getcwd())
        rel = os.path.relpath(real, root)
        if rel.startswith(".."):
            return real
        cur = root
        for part in rel.split(os.sep):
            if part in ("", "."):
                continue
            nxt = os.path.join(cur, part)
            if not os.path.exists(nxt):
                try:
                    low = part.lower()
                    match = next((n for n in os.listdir(cur) if n.lower() == low), None)
                except OSError:
                    match = None
                if match is None:
                    return real
                nxt = os.path.join(cur, match)
                print(f"[DEBUG-CASEFIX] {path} -> {os.path.relpath(nxt, root)}")
            cur = nxt
        return cur

    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".wasm": "application/wasm",
        ".otf": "font/otf",
        ".swf": "application/x-shockwave-flash",
    }

    def _begin_request(self):
        # Each request runs on its own thread (ThreadingPvZServer below);
        # reset the per-thread identity so nothing leaks between requests.
        _request_ctx.scoped = False
        _request_ctx.username = None
        _request_ctx.token = None
        _request_ctx.host = self.headers.get("Host")

    def _session_token(self):
        raw = self.headers.get("Cookie")
        if not raw:
            return None
        try:
            jar = http.cookies.SimpleCookie(raw)
        except http.cookies.CookieError:
            return None
        morsel = jar.get("pvz_session")
        return morsel.value if morsel else None

    def _web_username(self):
        """Account this browser is logged into (cookie session), or None."""
        return session_username(self._session_token())

    def do_GET(self):
        self._begin_request()
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        if path == "/__build":
            # Lets launcher.py check WHICH folder's server is on port 9090, so a
            # server left running from an older copy of the game is not reused.
            body = json.dumps({"label": BUILD_LABEL, "folder": HERE}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if path == "/crossdomain.xml":
            self.send_response(200)
            self.send_header("Content-Type", "text/xml")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            xml_content = """<?xml version="1.0"?>
<!DOCTYPE cross-domain-policy SYSTEM "http://www.adobe.com/xml/dtds/cross-domain-policy.dtd">
<cross-domain-policy>
    <allow-access-from domain="*" headers="*" secure="false"/>
</cross-domain-policy>"""
            self.wfile.write(xml_content.encode("utf-8"))
            return

        if path in ("/", "/accounts", "/accounts/"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(_account_page_html().encode("utf-8"))
            return

        if path in ("/play", "/play/"):
            username = self._web_username()
            if username is None:
                self.send_response(302)
                self.send_header("Location", "/accounts")
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(_play_page_html(username, self._session_token()).encode("utf-8"))
            return

        if path == "/api/language":
            self._send_json({"language": get_language(), "languages": LANGUAGES})
            return

        if path == "/api/whoami":
            username = self._web_username()
            self._send_json({
                "loggedIn": username is not None,
                "username": username,
                "save": load_save(username) if username else None,
            })
            return

        if path == "/itemShop.swf":
            try:
                with open(os.path.join(HERE, "itemShop.swf"), "rb") as f:
                    contents = f.read()
                print(f"[DEBUG-SERVING-ITEMSHOP] about to serve itemShop.swf: "
                      f"{len(contents)} bytes, md5={hashlib.md5(contents).hexdigest()}")
            except Exception as e:
                print(f"[DEBUG-SERVING-ITEMSHOP] FAILED to read itemShop.swf for logging: {e!r}")

        return super().do_GET()

    def _send_json(self, obj, status=200, cookie=None):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        if cookie is not None:
            self.send_header("Set-Cookie", cookie)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}

    def do_POST(self):
        self._begin_request()
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        # Website account API - separate from the AMF endpoint below, which
        # only ever receives POSTs to "/" (Config.HOST_URL, see Config.as).
        # Website logins are per browser (cookie session) - they no longer
        # touch active_account.json, which belongs to the launcher / Flash
        # projector on the PC. That way a phone logging in can't switch the
        # account the PC is playing as, and several devices can each play
        # their own account at the same time.
        if path == "/api/language":
            body = self._read_json_body()
            ok = set_language(str(body.get("language", "")))
            print(f"[lang] language set to {get_language()}" if ok else "[lang] unknown language requested")
            self._send_json({"ok": ok, "language": get_language()})
            return

        if path == "/api/register":
            body = self._read_json_body()
            with _state_lock:
                ok, error = create_account(body.get("username", ""), body.get("password", ""))
            cookie = None
            if ok:
                cookie = _session_cookie(create_session(body["username"].strip()))
            self._send_json({"ok": ok, "error": error}, cookie=cookie)
            return

        if path == "/api/login":
            body = self._read_json_body()
            username = str(body.get("username", "")).strip()
            ok, error = check_login(username, body.get("password", ""))
            cookie = None
            if ok:
                cookie = _session_cookie(create_session(username))
            self._send_json({"ok": ok, "error": error}, cookie=cookie)
            return

        if path == "/api/logout":
            token = self._session_token()
            if token:
                delete_session(token)
            self._send_json({"ok": True}, cookie=_session_cookie("", expire=True))
            return

        # This is where flash.net.NetConnection sends every services.I****
        # call - AmfCaller connects to Config.HOST_URL (this server) and
        # posts each RPC here as application/x-amf.
        length = int(self.headers.get("Content-Length", 0))
        data = self.rfile.read(length)
        try:
            version, req_bodies = amf.parse_request(data)
            print(f"[amf] POST {self.path}: {len(req_bodies)} call(s)")
            responses = build_amf_response(req_bodies)
            out = amf.build_response(version, responses)
            self.send_response(200)
            self.send_header("Content-Type", "application/x-amf")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(out)
        except Exception as e:
            print(f"[amf] FAILED to handle request: {e!r}")
            self.send_response(500)
            self.end_headers()

    def end_headers(self):
        path = urllib.parse.urlparse(self.path).path
        if path.startswith("/ruffle/") or path.startswith("/fonts/"):
            # The emulator (~14 MB of WebAssembly) and the font never change
            # between game builds - let phones keep them instead of
            # re-downloading them on every page load.
            self.send_header("Cache-Control", "public, max-age=604800")
        else:
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def log_message(self, format, *args):
        # Highlight non-200/3xx responses (almost always a 404 on a missing
        # asset/xml file) so they're impossible to scroll past unnoticed -
        # this is usually the actual cause of a stuck loading bar.
        status = str(args[1]) if len(args) > 1 else ""
        if status and not status.startswith("2") and not status.startswith("3"):
            print(f"    !!!! {status} NOT FOUND: {self.path}  <-- probably what's blocking the loading bar")
        super().log_message(format, *args)


check_build()

print("=========================================================")
print(" Starting PvZ Local Python Server (Server ID: pvz_server_2026)")
print("=========================================================\n")
print(f"[*] Launching server on http://127.0.0.1:{PORT}/ ...")
print("[*] Serves static files + crossdomain.xml + a minimal AMF stub for services.I****")
print("[*] Keep this terminal window OPEN while playing.\n")

if not os.path.exists("config.gz"):
    print("[!] config.gz not found - run: python build_config.py   (once, before first launch)\n")

class ThreadingPvZServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    # One thread per connection, so a phone downloading the emulator or a
    # big SWF doesn't stall every other device. Game state itself is still
    # handled one AMF request at a time (_state_lock).
    allow_reuse_address = True
    daemon_threads = True


# "" = listen on every network interface, so other devices on the same
# Wi-Fi can connect - not just this PC.
with ThreadingPvZServer(("", PORT), PvZServerHandler) as httpd:
    print("=========================================================")
    print(" PvZ Social Remake Asset Server Active")
    print("=========================================================")
    print(f"[*] Server running on: http://127.0.0.1:{PORT}/")
    _lan = lan_addresses()
    if _lan:
        for _ip in _lan:
            print(f"[*] Phones / other devices on your Wi-Fi: http://{_ip}:{PORT}/")
    else:
        print("[!] Could not detect this PC's network address - run ipconfig to find it.")
    print()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Shutting down server...")
        httpd.server_close()
