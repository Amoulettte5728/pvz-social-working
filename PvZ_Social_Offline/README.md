# PvZ Social offline kit - patch notes

## What was actually wrong

1. **`Config.HOST_URL` inside `main.swf` was corrupted.** Its compiled default
   value was the literal string `[http://127.0.0.1:9090/](http://127.0.0.1:9090/)`
   — a Markdown link left over from however this build was last patched — instead
   of a plain URL. Every server call in the game connects with
   `new NetConnection().connect(Config.HOST_URL)`, so this broke *every* network
   call at the source, before anything even reached the network.
2. **The game never used FlashVars.** `index.html`'s `id=`, `serverId=`,
   `sessionKey=` etc. are all ignored. The real client pulls its config through
   `ExternalInterface.call("util.getXxx")` into JavaScript on the host page (see
   `pvzs_1_.js`) — none of which existed here.
3. **A startup gate (`Main.testVar` → `md5FileId`) blocks the game** unless an
   external `loader.swf` (not in your files) injects a key before `main.swf`
   initializes. Without it you'd see the alert *"没有获取到玩家的id,无法进行下一步操作!"*
   ("Failed to get the player's ID, cannot proceed").
4. **Actual gameplay runs over Flash Remoting (AMF over HTTP)**, not REST — the
   original static-file `server.py` had no way to answer any of it.

## What this patch does

- **`main.swf`** — recompiled with `Config.HOST_URL` fixed and
  `Config.OFFLINE_MODE = true`. That flag is a real, built-in dev/QA mode:
  it makes `Flow.start()` tolerate a missing `md5FileId` (solves #3 without
  needing `loader.swf`), and makes asset-path resolution use local relative
  paths instead of the original CDN URLs.
- **`PVZEntry_1_.swf`** — recompiled with `PVZConfig.TD_OFFLINE_MODE = true`,
  which switches the tower-defense module onto its own bundled mock mission
  data instead of requiring server calls.
- **`server.py`** — same static file server as before, plus a `do_POST` handler
  that decodes incoming AMF (`amf.py`) and replies to `services.I1001` (the
  very first login call) with a plausible fake player payload, and to every
  other `services.I****` call with a generic `{result: true}` so nothing hangs
  waiting on a response. **It will not have correct data for anything beyond
  the initial login** — expect to extend `i1001_payload()` / add more branches
  in `build_amf_response()` in `server.py` as you hit each new call, the same
  way we found this one.
- **`Start_Game.bat` / `Start_Server.bat`** — now open `launcher.py`, a
  graphical launcher for controlling the server, game, accounts, avatars,
  and logs. `Start_Server.bat` opens the same launcher and starts the server
  automatically.
- **Account identity in `main.swf`** — the selected account's username and
  uploaded avatar are loaded into the game's existing `FriendManager` model
  during login, so the town header can use them immediately.

## Graphical launcher

Open `Start_Game.bat` for the full launcher. It can:

- start and close the local server independently;
- start and close the standalone Flash game independently;
- create username/password accounts and delete their local saves;
- select the account used by the next game launch;
- crop a PNG/JPEG/GIF/BMP/WebP image to a 256×256 in-game avatar;
- display the server and Flash logs, and export both to one text file.

`Start Game` also starts the server when it is not already running. Account
controls use the existing `accounts.json`, `saves/`, and
`active_account.json` format, so the browser account page and launcher stay
compatible. Avatar import uses Pillow; if it is missing, install it with
`py -m pip install Pillow`.

## Town building saves

The server now records building placement, moves, and sales from the game's
`I2012` action queue in the selected account's save (or `local_save.json`
without an account). Placed buildings are returned to the game through
`I2001` on the next launch. The purchase cost and sale return are saved too.
Restart the server after updating these files; restarting only the game
does not load the new server code.

Buildings placed before this fix were never written to a save, so the server
cannot restore their exact positions retroactively. Battle results, plants,
decorations, and building upgrades are still separate unfinished save paths.

## Debug tracing patch (new)

`main.swf` has a second patch layered on top of the `Config` fix, adding
checkpoint tracing through the whole boot sequence so a stuck loading bar is
diagnosable instead of a black box:

- **`Main.as`** - a global `uncaughtErrorEvents` handler, so any unhandled
  AS3 exception anywhere in the game gets logged instead of failing silently.
- **`Flow.as`** - trace lines at every stage of `start() -> requestServerConfUrl()
  -> onInitPvzsComplete() -> parseConfigXml() -> checkIsAllFileLoaded() -> loadUI()`,
  plus (the actual bug this was built to catch) an `MyEvent.ERROR` listener on
  all six `TxtLoader`s in `parseConfigXml()` (conf, Localization, GamePropItem,
  QuestList, EventList, FeedPost) and on the `config.gz` loader. None of these
  had an error listener in the original code - if one 404s, the load just
  hangs forever with zero indication why. Now it's traced.
- **`TxtLoader.as`** - added an `HTTPStatusEvent` listener so a failed load
  reports the actual HTTP status code, not just "ioError".

All added lines are tagged `[DEBUG-...]` so they're easy to pick out of the
noisier native trace output the original code already had.

`server.py`'s console output now also flags any non-2xx/3xx response with a
`!!!!` marker, since a missing file on the server side is the other half of
the same failure mode.

**To use it:** the graphical launcher enables Flash logging automatically
when it starts the game. Play, then use **Display Logs** in the launcher (or
run `View_Debug_Log.bat`) to see
just the checkpoint trace. The last `[DEBUG-FLOW]` line before it stops is
where things got stuck; a `[DEBUG-LOADBAR-BLOCKED]` or `[DEBUG-IO-ERROR]`
line names the exact file that failed.

**`[DEBUG-SHOP]`/`[DEBUG-BUILD]` checkpoints** trace the shop-purchase-to-
building-placement path specifically (`ItemShopListItem.onClickItem()` ->
`TownFlow.onTakingBuilding()` -> `Manager.createNewItem()`/
`addAndDrapNewItem()` -> `Manager.putDownBuilding()`), since none of the
original loading-bar tracing above covers that - it only shows what the
town does on boot. These show up in the same flashlog.txt, filtered by
the same `View_Debug_Log.bat`.

The launcher's **Export Logs** button writes a timestamped combined log.
The older **`Export_Debug_Log.bat`** still writes `debug_export.txt` - the filtered
checkpoint lines, the full flashlog.txt, and `server_log.txt` (the
server's own console output, now also written to a file automatically,
truncated fresh each time `server.py` starts) all bundled into one plain
text file in this folder. Attach/upload that file directly instead of
screenshotting terminal windows.

Note: this patch only touches `main.swf` (the town/loading-bar code). It
doesn't reach the tower-defense module's own file loads inside
`PVZEntry_1_.swf` - if that ends up needing the same treatment, the same
approach applies, it just hasn't been done yet.

## Before you launch

If `config.gz` is missing or you add more assets later, run this in the game
folder:

```
python build_config.py
```

It scans whatever `.swf`/`.xml` files are sitting in the folder and generates
`config.gz` (the client fetches this right after login to learn where every
asset actually lives) plus a couple of files at hardcoded paths the
tower-defense module expects. It'll print a short report, including:

- **Missing:** `conf/PlantData.xml`, `conf/ZombieData.xml`, `conf/BoostData.xml`
  — not in anything you've uploaded. These will 404 once you reach an actual
  battle. Not fixable until you find or extract those three.
- **Stubbed:** `Localization.xml` — you don't have the real one, so a
  placeholder empty file is generated just so the loader doesn't hang. Expect
  blank/missing UI text, not a crash.

## Important: use the standalone player, not a browser

`flash.net.NetConnection` (what carries every AMF call) is a real socket-style
connection Ruffle does not support in its web build. Opening `index.html` in
Chrome/Firefox will render the shell but **cannot** log in. Use
`Start_Game.bat` (which launches the real `flashplayer_32_sa_debug.exe`) every time.

## Turn on the debug log

Since you have the `sa_debug` build, create `mm.cfg` next to it (or in
`%APPDATA%\Macromedia\Flash Player\`) with:

```
ErrorReportingEnable=1
TraceOutputFileEnable=1
```

That writes a `flashlog.txt` with the real AS3 trace/error output — the
fastest way to see exactly where things stop working next.

## What to expect

This should get you **past the login screen and into (or close to) the town**.
Watch two things while it runs:

1. The `server.py` console — `[amf] target=... response=...` lines show every
   RPC call as it happens, in order. Whatever's called right after the ones
   already modeled is your next thing to implement.
2. `flashlog.txt` — any AS3 exception (usually a null-reference on some field
   the generic stub payload didn't include) tells you exactly which key to
   add to `server.py`'s payloads.
