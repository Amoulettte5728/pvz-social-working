#!/usr/bin/env python3
"""Graphical launcher and local account manager for PvZ Social Edition."""

import hashlib
import hmac
import json
import os
import queue
import re
import secrets
import socket
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
from datetime import datetime, timezone
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, simpledialog, ttk

try:
    from PIL import Image, ImageOps, ImageTk
except ImportError:
    Image = ImageOps = ImageTk = None


HERE = Path(__file__).resolve().parent
SERVER_SCRIPT = HERE / "server.py"
PROJECTOR = HERE / "flashplayer_32_sa_debug.exe"
GAME_URL = "http://127.0.0.1:9090/main.swf"
PORT = 9090

ACCOUNTS_PATH = HERE / "accounts.json"
SAVES_DIR = HERE / "saves"
AVATARS_DIR = HERE / "avatars"
ACTIVE_ACCOUNT_PATH = HERE / "active_account.json"
CONFIG_PATH = HERE / "launcher_config.json"
LANGUAGE_PATH = HERE / "language.json"
LANGUAGES = {"zh-CN": "简体中文", "zh-TW": "繁體中文", "en": "English"}


def read_language():
    try:
        code = json.loads(LANGUAGE_PATH.read_text(encoding="utf-8")).get("language", "zh-CN")
    except (OSError, ValueError):
        code = "zh-CN"
    return code if code in LANGUAGES else "zh-CN"


def write_language(code):
    LANGUAGE_PATH.write_text(json.dumps({"language": code}, ensure_ascii=False, indent=2), encoding="utf-8")
SERVER_LOG_PATH = HERE / "server_log.txt"
FLASH_LOG_PATH = Path(os.environ.get("APPDATA", "")) / "Macromedia" / "Flash Player" / "Logs" / "flashlog.txt"
MM_CFG_PATH = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "mm.cfg"

LOCAL_PROFILE = "Local save (no account)"
USERNAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0
MAX_PROFILE_SOURCE_SIZE = 20 * 1024 * 1024
PROFILE_IMAGE_SIZE = 256

DEFAULT_SAVE = {
    "tutorialStep": 1,
    "skippedTutorial": None,
    "money": 4500,
    "gems": 500,
    "level": 1,
    "experience": 0,
    "houses": [],
    "levelsFinished": [],
    "ownedBuildings": [],
    "placedBuildings": [],
    "ownedFunctionCards": [],
}

BG = "#172218"
PANEL = "#243226"
PANEL_2 = "#2d3e2f"
FG = "#eef4e8"
MUTED = "#a5b6a0"
ACCENT = "#83c94c"
ACCENT_HOVER = "#98dc60"
STOP = "#bd5b40"
WARN = "#ddb64a"
LOG_BG = "#101711"


def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as source:
            return json.load(source)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def write_json_atomic(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as target:
            json.dump(value, target, ensure_ascii=False, indent=2)
            target.write("\n")
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def write_bytes_atomic(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "wb") as target:
            target.write(value)
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def load_accounts():
    accounts = load_json(ACCOUNTS_PATH, {})
    return accounts if isinstance(accounts, dict) else {}


def current_account():
    value = load_json(ACTIVE_ACCOUNT_PATH, {"username": None})
    username = value.get("username") if isinstance(value, dict) else None
    return username if username in load_accounts() else None


def set_active_account(username):
    write_json_atomic(ACTIVE_ACCOUNT_PATH, {"username": username})


def create_account(username, password):
    username = username.strip()
    if not USERNAME_RE.fullmatch(username):
        raise ValueError("Username must be 1–32 characters using only letters, numbers, - or _.")
    if len(password) < 4:
        raise ValueError("Password must be at least 4 characters.")

    accounts = load_accounts()
    if any(existing.casefold() == username.casefold() for existing in accounts):
        raise ValueError("That username is already taken.")

    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000
    ).hex()
    accounts[username] = {
        "salt": salt,
        "password_hash": digest,
        "created": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    write_json_atomic(ACCOUNTS_PATH, accounts)
    save_path = SAVES_DIR / (username + ".json")
    if not save_path.exists():
        write_json_atomic(save_path, DEFAULT_SAVE)
    set_active_account(username)


def delete_account(username):
    if not USERNAME_RE.fullmatch(username):
        raise ValueError("The account has an invalid username and was not deleted.")
    accounts = load_accounts()
    if username not in accounts:
        raise LookupError("That account no longer exists.")
    active = load_json(ACTIVE_ACCOUNT_PATH, {"username": None})
    del accounts[username]
    write_json_atomic(ACCOUNTS_PATH, accounts)

    save_path = SAVES_DIR / (username + ".json")
    avatar_path = AVATARS_DIR / (username + ".png")
    for path in (save_path, avatar_path):
        try:
            path.unlink()
        except FileNotFoundError:
            pass
    if isinstance(active, dict) and active.get("username") == username:
        set_active_account(None)


# --- Friends -----------------------------------------------------------
#
# friends.json (shared, matching accounts.json's pattern) is keyed by
# username, each entry: {"friends": [...], "incoming": [...], "outgoing": [...]}
# - "friends" are confirmed both ways; "incoming"/"outgoing" are opposite
# sides of the same pending request (X's outgoing entry for Y means Y has
# a matching incoming entry for X - kept as two separate lists rather than
# one shared pending-request object so each account's own file section
# only ever needs read/written for actions that account actually took).
# This is necessarily a same-machine, shared-account-store feature (see
# the launcher's account model as a whole - server.py binds 127.0.0.1
# only) - "friend" here means another local account in this same
# accounts.json, not a real remote player.

FRIENDS_PATH = HERE / "friends.json"


def load_friends():
    data = load_json(FRIENDS_PATH, {})
    return data if isinstance(data, dict) else {}


def _friend_entry(data, username):
    entry = data.get(username)
    if not isinstance(entry, dict):
        entry = {}
    entry.setdefault("friends", [])
    entry.setdefault("incoming", [])
    entry.setdefault("outgoing", [])
    data[username] = entry
    return entry


def send_friend_request(from_username, to_username):
    """Raises ValueError with a user-facing message on any invalid request."""
    accounts = load_accounts()
    if to_username not in accounts:
        raise ValueError("No account named %r exists." % to_username)
    if to_username == from_username:
        raise ValueError("You can't befriend your own account.")
    data = load_friends()
    sender = _friend_entry(data, from_username)
    receiver = _friend_entry(data, to_username)
    if to_username in sender["friends"]:
        raise ValueError("%s is already your friend." % to_username)
    if to_username in sender["outgoing"]:
        raise ValueError("You already sent %s a friend request." % to_username)
    if to_username in sender["incoming"]:
        raise ValueError(
            "%s already sent you a friend request - accept or decline it instead of sending a new one."
            % to_username
        )
    sender["outgoing"].append(to_username)
    receiver["incoming"].append(from_username)
    write_json_atomic(FRIENDS_PATH, data)


def pending_incoming_requests(username):
    data = load_friends()
    return list(_friend_entry(data, username)["incoming"])


def respond_to_friend_request(username, other_username, accept):
    data = load_friends()
    me = _friend_entry(data, username)
    them = _friend_entry(data, other_username)
    if other_username in me["incoming"]:
        me["incoming"].remove(other_username)
    if username in them["outgoing"]:
        them["outgoing"].remove(username)
    if accept:
        if other_username not in me["friends"]:
            me["friends"].append(other_username)
        if username not in them["friends"]:
            them["friends"].append(username)
    write_json_atomic(FRIENDS_PATH, data)


def friends_of(username):
    data = load_friends()
    return list(_friend_entry(data, username)["friends"])


def remove_friend(username, other_username):
    data = load_friends()
    me = _friend_entry(data, username)
    them = _friend_entry(data, other_username)
    if other_username in me["friends"]:
        me["friends"].remove(other_username)
    if username in them["friends"]:
        them["friends"].remove(username)
    write_json_atomic(FRIENDS_PATH, data)


def normalize_profile_picture(path):
    if Image is None or ImageOps is None:
        raise RuntimeError("Avatar importing needs Pillow. Install it with: py -m pip install Pillow")
    if os.path.getsize(path) > MAX_PROFILE_SOURCE_SIZE:
        raise ValueError("The selected image is larger than 20 MB.")
    try:
        with Image.open(path) as source:
            width, height = source.size
            if width < 1 or height < 1:
                raise ValueError("The selected file has no usable image.")
            if width * height > 25_000_000:
                raise ValueError("The selected image is too large (maximum 25 megapixels).")
            source.seek(0)
            upright = ImageOps.exif_transpose(source)
            square = ImageOps.fit(
                upright.convert("RGBA"),
                (PROFILE_IMAGE_SIZE, PROFILE_IMAGE_SIZE),
                method=Image.Resampling.LANCZOS,
                centering=(0.5, 0.5),
            )
            from io import BytesIO

            output = BytesIO()
            square.save(output, format="PNG", optimize=True)
            return output.getvalue(), width, height
    except (ValueError, RuntimeError):
        raise
    except Exception as exc:
        raise ValueError("The selected file is not a readable image.") from exc


def console_python():
    executable = Path(sys.executable)
    if executable.name.lower() == "pythonw.exe":
        candidate = executable.with_name("python.exe")
        if candidate.exists():
            return str(candidate)
    return str(executable)


def lan_ip():
    """This PC's address on the local network (what phones should open)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))   # nothing is actually sent
            ip = s.getsockname()[0]
            return None if ip.startswith("127.") else ip
    except OSError:
        return None


def _footer_text():
    ip = lan_ip()
    phones = ("Phones on your Wi-Fi: http://%s:%d/" % (ip, PORT)) if ip else "Phones: run ipconfig to find this PC's address"
    return "This PC: 127.0.0.1:%d  ·  %s  ·  accounts and saves stay in this folder" % (PORT, phones)


def port_open(timeout=0.25):
    try:
        with socket.create_connection(("127.0.0.1", PORT), timeout=timeout):
            return True
    except OSError:
        return False


def pids_on_port():
    if os.name != "nt":
        return set()
    try:
        result = subprocess.run(
            ["netstat", "-ano", "-p", "TCP"],
            capture_output=True,
            text=True,
            timeout=8,
            creationflags=CREATE_NO_WINDOW,
        )
    except (OSError, subprocess.SubprocessError):
        return set()
    found = set()
    suffix = ":%d" % PORT
    for line in result.stdout.splitlines():
        fields = line.split()
        if len(fields) >= 5 and fields[1].endswith(suffix) and fields[3] == "LISTENING":
            try:
                found.add(int(fields[-1]))
            except ValueError:
                pass
    return found


def running_server_folder(timeout=1.5):
    """Folder of the server currently on the port (None if it does not say:
    an older server.py without the /__build endpoint)."""
    try:
        import urllib.request
        with urllib.request.urlopen("http://127.0.0.1:%d/__build" % PORT, timeout=timeout) as r:
            info = json.loads(r.read().decode("utf-8"))
        return str(info.get("folder") or "") or None
    except Exception:
        return None


def same_folder(a, b):
    try:
        return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))
    except Exception:
        return False


def stop_pid(pid):
    subprocess.run(
        ["taskkill", "/PID", str(pid), "/T", "/F"],
        capture_output=True,
        creationflags=CREATE_NO_WINDOW,
    )


def enable_flash_logging():
    values = {}
    try:
        for line in MM_CFG_PATH.read_text(encoding="utf-8").splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip()
    except OSError:
        pass
    values.update({"ErrorReportingEnable": "1", "TraceOutputFileEnable": "1", "MaxWarnings": "0"})
    MM_CFG_PATH.write_text(
        "".join("%s=%s\n" % item for item in values.items()), encoding="utf-8"
    )


class Launcher:
    def __init__(self, root, auto_start_server=False):
        self.root = root
        self.server = None
        self.game = None
        self.pending_game = False
        self.server_ready = False
        self.log_queue = queue.Queue()
        self.activity_lines = []
        self.log_visible = False
        self.log_window = None
        self.friends_window = None
        self._friends_window_username = None
        self._preview_photo = None
        self._closing = False
        self._build_ui()
        self._refresh_accounts()
        self._sanity_check()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(120, self._poll_output)
        self.root.after(500, self._poll_processes)
        if auto_start_server:
            self.root.after(350, self.start_server)

    def _build_ui(self):
        self.root.title("PvZ Social Edition — Launcher")
        self.root.configure(bg=BG)
        self.root.geometry("680x700")
        self.root.minsize(620, 620)

        header = tk.Frame(self.root, bg=BG)
        header.pack(fill="x", padx=22, pady=(18, 7))
        tk.Label(
            header,
            text="🌻  Plants vs. Zombies Social Edition",
            bg=BG,
            fg=FG,
            font=("Segoe UI", 17, "bold"),
        ).pack(anchor="w")
        tk.Label(
            header,
            text="Local server launcher",
            bg=BG,
            fg=MUTED,
            font=("Segoe UI", 10),
        ).pack(anchor="w")

        status = tk.Frame(self.root, bg=BG)
        status.pack(fill="x", padx=22, pady=5)
        self.server_status = self._status_card(status, "Server", 0)
        self.game_status = self._status_card(status, "Game", 1)

        account = tk.Frame(self.root, bg=PANEL)
        account.pack(fill="x", padx=22, pady=(8, 6))
        left = tk.Frame(account, bg=PANEL)
        left.pack(side="left", fill="both", expand=True, padx=14, pady=12)
        tk.Label(left, text="Play as", bg=PANEL, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w")

        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(
            "Launcher.TCombobox",
            fieldbackground=LOG_BG,
            background=PANEL_2,
            foreground=FG,
            arrowcolor=FG,
            bordercolor=PANEL_2,
            lightcolor=PANEL_2,
            darkcolor=PANEL_2,
            selectbackground=LOG_BG,
            selectforeground=FG,
            padding=5,
        )
        self.root.option_add("*TCombobox*Listbox.background", LOG_BG)
        self.root.option_add("*TCombobox*Listbox.foreground", FG)
        self.root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
        self.root.option_add("*TCombobox*Listbox.selectForeground", "#13200e")
        self.account_var = tk.StringVar(value=LOCAL_PROFILE)
        self.account_box = ttk.Combobox(
            left,
            textvariable=self.account_var,
            state="readonly",
            style="Launcher.TCombobox",
            font=("Segoe UI", 11),
        )
        self.account_box.pack(fill="x", pady=(4, 0))
        self.account_box.bind("<<ComboboxSelected>>", self._account_changed)

        tk.Label(left, text="Language / 语言 / 語言", bg=PANEL, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", pady=(10, 0))
        self.language_var = tk.StringVar(value=LANGUAGES.get(read_language(), LANGUAGES["zh-CN"]))
        self.language_box = ttk.Combobox(
            left,
            textvariable=self.language_var,
            state="readonly",
            style="Launcher.TCombobox",
            font=("Segoe UI", 11),
            values=list(LANGUAGES.values()),
        )
        self.language_box.pack(fill="x", pady=(4, 0))
        self.language_box.bind("<<ComboboxSelected>>", self._language_changed)

        preview_wrap = tk.Frame(account, bg=PANEL)
        preview_wrap.pack(side="right", padx=14, pady=10)
        self.avatar_preview = tk.Label(
            preview_wrap,
            text="Default\navatar",
            width=10,
            height=5,
            bg=LOG_BG,
            fg=MUTED,
            font=("Segoe UI", 8),
        )
        self.avatar_preview.pack()

        account_tools = tk.Frame(self.root, bg=BG)
        account_tools.pack(fill="x", padx=22, pady=(0, 8))
        self.create_btn = self._button(account_tools, "Create Account", self.create_account_dialog)
        self.create_btn.pack(side="left", expand=True, fill="x", padx=(0, 4))
        self.delete_btn = self._button(account_tools, "Delete Account", self.delete_selected_account)
        self.delete_btn.pack(side="left", expand=True, fill="x", padx=4)
        self.avatar_btn = self._button(account_tools, "Upload Avatar…", self.upload_avatar)
        self.avatar_btn.pack(side="left", expand=True, fill="x", padx=4)
        self.add_friend_btn = self._button(account_tools, "Add Friend", self.add_friend_dialog)
        self.add_friend_btn.pack(side="left", expand=True, fill="x", padx=4)
        self.see_friends_btn = self._button(account_tools, "See Friends", self.see_friends_dialog)
        self.see_friends_btn.pack(side="left", expand=True, fill="x", padx=(4, 0))

        controls = tk.Frame(self.root, bg=BG)
        controls.pack(fill="x", padx=22, pady=5)
        self.start_server_btn = self._button(
            controls, "Start Server", self.start_server, bg=ACCENT, fg="#13200e", bold=True
        )
        self.start_server_btn.pack(side="left", expand=True, fill="x", padx=(0, 4))
        self.start_game_btn = self._button(
            controls, "Start Game", self.start_game, bg=ACCENT, fg="#13200e", bold=True
        )
        self.start_game_btn.pack(side="left", expand=True, fill="x", padx=(4, 0))

        stop_controls = tk.Frame(self.root, bg=BG)
        stop_controls.pack(fill="x", padx=22, pady=(3, 8))
        self.close_game_btn = self._button(
            stop_controls, "Close Game", self.close_game, bg=STOP, bold=True
        )
        self.close_game_btn.pack(side="left", expand=True, fill="x", padx=(0, 4))
        self.close_server_btn = self._button(
            stop_controls, "Close Server", self.close_server, bg=STOP, bold=True
        )
        self.close_server_btn.pack(side="left", expand=True, fill="x", padx=(4, 0))

        tools = tk.Frame(self.root, bg=BG)
        tools.pack(fill="x", padx=22, pady=(0, 6))
        self.logs_btn = self._button(tools, "Display Logs", self.open_logs)
        self.logs_btn.pack(side="left", expand=True, fill="x", padx=(0, 4))
        self.export_btn = self._button(tools, "Export Logs…", self.export_logs)
        self.export_btn.pack(side="left", expand=True, fill="x", padx=(4, 0))

        self.activity_toggle = tk.Label(
            self.root,
            text="▸  Launcher activity",
            bg=BG,
            fg=MUTED,
            cursor="hand2",
            font=("Segoe UI", 9),
        )
        self.activity_toggle.pack(fill="x", padx=22, pady=(7, 0))
        self.activity_toggle.bind("<Button-1>", lambda _event: self.toggle_activity_log())

        self.activity_frame = tk.Frame(self.root, bg=BG)
        self.activity = scrolledtext.ScrolledText(
            self.activity_frame,
            height=10,
            bg=LOG_BG,
            fg="#c6d9b6",
            insertbackground=FG,
            relief="flat",
            wrap="word",
            font=("Consolas", 8),
        )
        self.activity.pack(fill="both", expand=True)
        self.activity.configure(state="disabled")

        footer = tk.Frame(self.root, bg=BG)
        footer.pack(side="bottom", fill="x", padx=22, pady=11)
        tk.Label(
            footer,
            text=_footer_text(),
            bg=BG,
            fg=MUTED,
            font=("Segoe UI", 8),
        ).pack(anchor="w")

        self._update_controls()

    def _status_card(self, parent, title, column):
        frame = tk.Frame(parent, bg=PANEL)
        frame.grid(row=0, column=column, sticky="ew", padx=(0, 4) if column == 0 else (4, 0))
        parent.grid_columnconfigure(column, weight=1)
        dot = tk.Canvas(frame, width=16, height=16, bg=PANEL, highlightthickness=0)
        dot.pack(side="left", padx=(12, 7), pady=10)
        dot_id = dot.create_oval(2, 2, 14, 14, fill="#777", outline="")
        label = tk.Label(frame, text=title + ": Stopped", bg=PANEL, fg=FG, font=("Segoe UI", 10, "bold"))
        label.pack(side="left", pady=10)
        return dot, dot_id, label, title

    def _button(self, parent, text, command, bg=PANEL_2, fg=FG, bold=False):
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=bg,
            fg=fg,
            activebackground=ACCENT_HOVER if bg == ACCENT else "#3c5140",
            activeforeground=fg,
            relief="flat",
            cursor="hand2",
            font=("Segoe UI", 10, "bold" if bold else "normal"),
            padx=10,
            pady=8,
            bd=0,
        )

    def _set_status(self, card, text, colour):
        dot, dot_id, label, title = card
        dot.itemconfigure(dot_id, fill=colour)
        label.configure(text=title + ": " + text)

    def _sanity_check(self):
        missing = [str(path) for path in (SERVER_SCRIPT, PROJECTOR, HERE / "main.swf") if not path.exists()]
        if missing:
            self._log("Missing required files:\n  " + "\n  ".join(missing))
            messagebox.showerror(
                "Launcher files missing",
                "The launcher is not beside all required game files:\n\n" + "\n".join(missing),
                parent=self.root,
            )

    def _refresh_accounts(self, select=None):
        accounts = sorted(load_accounts(), key=str.casefold)
        values = [LOCAL_PROFILE] + accounts
        self.account_box.configure(values=values)
        config = load_json(CONFIG_PATH, {})
        desired = select or current_account() or config.get("last_username") or LOCAL_PROFILE
        if desired not in values:
            desired = LOCAL_PROFILE
        self.account_var.set(desired)
        self._show_avatar_preview()
        self._update_controls()
        self._check_friend_requests()

    def _selected_username(self):
        value = self.account_var.get().strip()
        return None if value == LOCAL_PROFILE or value not in load_accounts() else value

    def _account_changed(self, _event=None):
        username = self._selected_username()
        try:
            set_active_account(username)
            write_json_atomic(CONFIG_PATH, {"last_username": username or LOCAL_PROFILE})
        except OSError as exc:
            messagebox.showerror("Account", "Couldn't select this account:\n%s" % exc, parent=self.root)
        self._show_avatar_preview()
        self._update_controls()
        if (
            self.friends_window is not None
            and self.friends_window.winfo_exists()
            and self._friends_window_username != username
        ):
            self.friends_window.destroy()
        self._check_friend_requests()

    def _show_avatar_preview(self):
        self._preview_photo = None
        username = self._selected_username()
        path = AVATARS_DIR / (username + ".png") if username else None
        if path and path.exists() and Image is not None and ImageTk is not None:
            try:
                with Image.open(path) as source:
                    image = source.convert("RGBA")
                    image.thumbnail((74, 74), Image.Resampling.LANCZOS)
                    self._preview_photo = ImageTk.PhotoImage(image)
                self.avatar_preview.configure(image=self._preview_photo, text="", width=74, height=74)
                return
            except Exception:
                pass
        self.avatar_preview.configure(image="", text="Default\navatar", width=10, height=5)

    def create_account_dialog(self):
        username = simpledialog.askstring(
            "Create Account",
            "Choose a username (letters, numbers, - and _; up to 32 characters):",
            parent=self.root,
        )
        if username is None:
            return
        password = simpledialog.askstring(
            "Create Account",
            "Choose a password (at least 4 characters):",
            show="*",
            parent=self.root,
        )
        if password is None:
            return
        try:
            create_account(username, password)
        except Exception as exc:
            messagebox.showerror("Create Account", str(exc), parent=self.root)
            return
        username = username.strip()
        self._refresh_accounts(username)
        self._log("Created account: %s" % username)
        messagebox.showinfo("Create Account", "Account %s was created and selected." % username, parent=self.root)

    def delete_selected_account(self):
        username = self._selected_username()
        if not username:
            messagebox.showwarning("Delete Account", "Select a named account first.", parent=self.root)
            return
        if self.game is not None and self.game.poll() is None:
            messagebox.showwarning("Delete Account", "Close the game before deleting its account.", parent=self.root)
            return
        if not messagebox.askyesno(
            "Delete Account",
            "Permanently delete %s, its save, and its avatar?\n\nThis cannot be undone." % username,
            icon="warning",
            parent=self.root,
        ):
            return
        try:
            delete_account(username)
        except Exception as exc:
            messagebox.showerror("Delete Account", "Couldn't delete the account:\n%s" % exc, parent=self.root)
            return
        self._refresh_accounts(LOCAL_PROFILE)
        self._account_changed()
        self._log("Deleted account: %s" % username)

    def upload_avatar(self):
        username = self._selected_username()
        if not username:
            messagebox.showwarning("Upload Avatar", "Select a named account first.", parent=self.root)
            return
        path = filedialog.askopenfilename(
            parent=self.root,
            title="Choose an avatar for %s" % username,
            filetypes=(
                ("Image files", "*.png;*.jpg;*.jpeg;*.gif;*.bmp;*.webp"),
                ("All files", "*.*"),
            ),
        )
        if not path:
            return
        try:
            data, width, height = normalize_profile_picture(path)
            write_bytes_atomic(AVATARS_DIR / (username + ".png"), data)
        except Exception as exc:
            messagebox.showerror("Upload Avatar", "Couldn't import the avatar:\n%s" % exc, parent=self.root)
            return
        self._show_avatar_preview()
        self._log("Imported avatar for %s from %s" % (username, path))
        suffix = "\n\nClose and restart the game to refresh it." if self.game is not None and self.game.poll() is None else ""
        messagebox.showinfo(
            "Upload Avatar",
            "%s's %d×%d image was cropped to a 256×256 PNG.%s" % (username, width, height, suffix),
            parent=self.root,
        )

    def add_friend_dialog(self):
        username = self._selected_username()
        if not username:
            messagebox.showwarning("Add Friend", "Select a named account first.", parent=self.root)
            return
        target = simpledialog.askstring(
            "Add Friend",
            "Enter the account name you want to befriend:",
            parent=self.root,
        )
        if target is None:
            return
        target = target.strip()
        if not target:
            return
        try:
            send_friend_request(username, target)
        except ValueError as exc:
            messagebox.showerror("Add Friend", str(exc), parent=self.root)
            return
        self._log("%s sent a friend request to %s" % (username, target))
        messagebox.showinfo(
            "Add Friend",
            "Friend request sent to %s.\n\nThey'll be asked to accept or decline next time they select their account here."
            % target,
            parent=self.root,
        )

    def _check_friend_requests(self):
        """Shows one accept/decline prompt per pending incoming request for
        the currently selected account. Called after account selection
        changes and once at startup for whichever account starts selected -
        matches this launcher's local, single-machine account model (see
        the friends.json comment in the data layer above): "a friend" is
        another account in this same accounts.json, so there is no
        separate always-on listener needed, just a check whenever an
        account becomes active."""
        username = self._selected_username()
        if not username:
            return
        for requester in pending_incoming_requests(username):
            if requester not in load_accounts():
                # the requester's account was deleted since the request was
                # sent - clean it up silently rather than prompt about a
                # request from an account that no longer exists
                respond_to_friend_request(username, requester, accept=False)
                continue
            accept = messagebox.askyesno(
                "Friend Request",
                "%s wants to be your friend.\n\nAccept?" % requester,
                parent=self.root,
            )
            respond_to_friend_request(username, requester, accept=accept)
            self._log(
                "%s %s %s's friend request" % (username, "accepted" if accept else "declined", requester)
            )

    def see_friends_dialog(self):
        username = self._selected_username()
        if not username:
            messagebox.showwarning("See Friends", "Select a named account first.", parent=self.root)
            return
        if self.friends_window is not None and self.friends_window.winfo_exists():
            self.friends_window.lift()
            self._refresh_friends_window()
            return
        win = tk.Toplevel(self.root)
        win.title("PvZ Social Edition — %s's Friends" % username)
        win.configure(bg=BG)
        win.geometry("420x460")
        win.minsize(340, 260)
        self.friends_window = win
        self._friends_window_username = username

        header = tk.Label(
            win, text="%s's Friends" % username, bg=BG, fg=FG, font=("Segoe UI", 12, "bold")
        )
        header.pack(fill="x", padx=14, pady=(14, 4))

        outer = tk.Frame(win, bg=BG)
        outer.pack(fill="both", expand=True, padx=14, pady=4)
        canvas = tk.Canvas(outer, bg=PANEL, highlightthickness=0)
        scrollbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        self.friends_list_frame = tk.Frame(canvas, bg=PANEL)
        self.friends_list_frame.bind(
            "<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=self.friends_list_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.friends_canvas = canvas

        actions = tk.Frame(win, bg=BG)
        actions.pack(fill="x", padx=14, pady=(4, 14))
        self._button(actions, "Close", win.destroy).pack(side="right")

        win.protocol("WM_DELETE_WINDOW", win.destroy)
        self._refresh_friends_window()

    def _refresh_friends_window(self):
        if self.friends_window is None or not self.friends_window.winfo_exists():
            return
        for child in self.friends_list_frame.winfo_children():
            child.destroy()
        username = self._friends_window_username
        friends = sorted(friends_of(username), key=str.casefold)
        if not friends:
            tk.Label(
                self.friends_list_frame,
                text="No friends yet.\n\nUse Add Friend to send a request.",
                bg=PANEL,
                fg=MUTED,
                font=("Segoe UI", 10),
                justify="center",
            ).pack(padx=10, pady=20)
            return
        for friend_username in friends:
            row = tk.Frame(self.friends_list_frame, bg=PANEL_2)
            row.pack(fill="x", padx=6, pady=3)
            tk.Label(
                row, text=friend_username, bg=PANEL_2, fg=FG, font=("Segoe UI", 10), anchor="w"
            ).pack(side="left", fill="x", expand=True, padx=(10, 4), pady=8)
            remove_btn = self._button(
                row,
                "Remove",
                lambda f=friend_username: self._remove_friend_clicked(f),
                bg=STOP,
            )
            remove_btn.pack(side="right", padx=(4, 10), pady=6)

    def _remove_friend_clicked(self, friend_username):
        username = self._friends_window_username
        if not messagebox.askyesno(
            "Remove Friend",
            "Remove %s from %s's friends?" % (friend_username, username),
            parent=self.friends_window,
        ):
            return
        remove_friend(username, friend_username)
        self._log("%s removed %s as a friend" % (username, friend_username))
        self._refresh_friends_window()


    def _language_changed(self, _event=None):
        name = self.language_var.get()
        code = next((c for c, n in LANGUAGES.items() if n == name), "zh-CN")
        try:
            write_language(code)
            self._log("Language set to %s. It applies the next time the game starts (reload the game if it is open)." % name)
        except OSError as exc:
            self._log("Could not save the language: %s" % exc)

    def start_server(self):
        if self.server is not None and self.server.poll() is None:
            return
        if port_open():
            other = running_server_folder()
            if other is None or not same_folder(other, str(HERE)):
                # A server from ANOTHER copy of the game (or an old build) is on
                # the port. Reusing it would load that folder's files instead of
                # this one's, so stop it and start this folder's server.
                self._log("A server from another game folder is on port %d (%s) - stopping it so this folder's files are used." % (PORT, other or "older build"))
                for pid in pids_on_port():
                    stop_pid(pid)
                for _ in range(20):
                    if not port_open(0.1):
                        break
                    time.sleep(0.15)
        if port_open():
            self.server_ready = True
            self._set_status(self.server_status, "Running (existing)", ACCENT)
            self._log("A server is already listening on port %d." % PORT)
            self._update_controls()
            if self.pending_game:
                self.pending_game = False
                self._launch_game_now()
            return
        if not SERVER_SCRIPT.exists():
            messagebox.showerror("Start Server", "server.py was not found beside the launcher.", parent=self.root)
            return
        self.server_ready = False
        self._set_status(self.server_status, "Starting…", WARN)
        self._log("Starting the local server…")
        environment = os.environ.copy()
        environment["PYTHONUTF8"] = "1"
        environment["PYTHONUNBUFFERED"] = "1"
        try:
            self.server = subprocess.Popen(
                [console_python(), "-u", str(SERVER_SCRIPT)],
                cwd=str(HERE),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                env=environment,
                creationflags=CREATE_NO_WINDOW,
            )
        except Exception as exc:
            self.server = None
            self._set_status(self.server_status, "Failed", STOP)
            self._log("Could not start the server: %r" % exc)
            messagebox.showerror("Start Server", "Couldn't start the server:\n%s" % exc, parent=self.root)
            return
        threading.Thread(target=self._read_server_output, daemon=True).start()
        threading.Thread(target=self._wait_for_server, daemon=True).start()
        self._update_controls()

    def _read_server_output(self):
        process = self.server
        if process is None or process.stdout is None:
            return
        for line in process.stdout:
            self.log_queue.put(line.rstrip("\r\n"))
        self.log_queue.put(("server-exited", process.returncode))

    def _wait_for_server(self):
        for _ in range(80):
            if self._closing or self.server is None or self.server.poll() is not None:
                return
            if port_open():
                self.root.after(0, self._server_became_ready)
                return
            time.sleep(0.125)
        self.root.after(0, self._server_start_timed_out)

    def _server_became_ready(self):
        self.server_ready = True
        self._set_status(self.server_status, "Running", ACCENT)
        self._log("Server ready at %s" % GAME_URL)
        self._update_controls()
        if self.pending_game:
            self.pending_game = False
            self._launch_game_now()

    def _server_start_timed_out(self):
        if not port_open():
            self._set_status(self.server_status, "Not responding", STOP)
            self._log("The server did not open port %d within 10 seconds. Check the logs." % PORT)
            self.pending_game = False
        self._update_controls()

    def start_game(self):
        if self.game is not None and self.game.poll() is None:
            return
        username = self._selected_username()
        try:
            set_active_account(username)
            write_json_atomic(CONFIG_PATH, {"last_username": username or LOCAL_PROFILE})
        except OSError as exc:
            messagebox.showerror("Start Game", "Couldn't select the save to use:\n%s" % exc, parent=self.root)
            return
        if not port_open():
            self.pending_game = True
            self.start_server()
            return
        self._launch_game_now()

    def _launch_game_now(self):
        if not PROJECTOR.exists():
            messagebox.showerror("Start Game", "The standalone Flash Player is missing.", parent=self.root)
            return
        try:
            enable_flash_logging()
        except OSError as exc:
            self._log("Could not enable Flash logging: %s" % exc)
        try:
            FLASH_LOG_PATH.unlink()
        except FileNotFoundError:
            pass
        except OSError as exc:
            self._log("Could not clear the previous Flash log: %s" % exc)
        username = self._selected_username()
        self._log("Launching the game as %s…" % (username or "the local save"))
        try:
            self.game = subprocess.Popen([str(PROJECTOR), GAME_URL], cwd=str(HERE))
        except Exception as exc:
            self.game = None
            messagebox.showerror("Start Game", "Couldn't open the game:\n%s" % exc, parent=self.root)
            return
        self.account_box.configure(state="disabled")
        self._set_status(self.game_status, "Running", ACCENT)
        self._update_controls()

    def close_game(self, quiet=False):
        process = self.game
        if process is None or process.poll() is not None:
            self.game = None
            self._set_status(self.game_status, "Stopped", "#777")
            self._update_controls()
            return
        try:
            process.terminate()
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            if os.name == "nt":
                stop_pid(process.pid)
        except OSError:
            pass
        self.game = None
        self._set_status(self.game_status, "Stopped", "#777")
        self._log("Game closed.")
        self.account_box.configure(state="readonly")
        self._update_controls()
        if not quiet:
            self._show_avatar_preview()

    def close_server(self, quiet=False):
        process = self.server
        if process is not None and process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                if os.name == "nt":
                    stop_pid(process.pid)
            except OSError:
                pass
            self.server = None
        elif port_open():
            pids = pids_on_port()
            if not pids:
                if not quiet:
                    messagebox.showwarning(
                        "Close Server", "A server is using port %d, but its process could not be identified." % PORT, parent=self.root
                    )
                return
            if quiet or messagebox.askyesno(
                "Close Existing Server",
                "The launcher did not start the server on port %d. Close that existing process anyway?" % PORT,
                parent=self.root,
            ):
                for pid in pids:
                    stop_pid(pid)
            else:
                return
        self.server = None
        self.server_ready = False
        self.pending_game = False
        self._set_status(self.server_status, "Stopped", "#777")
        self._log("Server closed.")
        self._update_controls()

    def toggle_activity_log(self):
        if self.log_visible:
            self.activity_frame.pack_forget()
            self.activity_toggle.configure(text="▸  Launcher activity")
        else:
            self.activity_frame.pack(fill="both", expand=True, padx=22, pady=(3, 0))
            self.activity_toggle.configure(text="▾  Launcher activity")
        self.log_visible = not self.log_visible

    def _read_log(self, path):
        try:
            return Path(path).read_text(encoding="utf-8", errors="replace")
        except FileNotFoundError:
            return "No log has been created yet."
        except OSError as exc:
            return "Could not read this log: %s" % exc

    def open_logs(self):
        if self.log_window is not None and self.log_window.winfo_exists():
            self.log_window.lift()
            self._refresh_log_window()
            return
        win = tk.Toplevel(self.root)
        win.title("PvZ Social Edition — Logs")
        win.configure(bg=BG)
        win.geometry("820x560")
        win.minsize(620, 420)
        self.log_window = win
        notebook = ttk.Notebook(win)
        notebook.pack(fill="both", expand=True, padx=12, pady=(12, 6))
        self.server_log_view = scrolledtext.ScrolledText(
            notebook, bg=LOG_BG, fg="#c6d9b6", insertbackground=FG, wrap="none", font=("Consolas", 9)
        )
        self.flash_log_view = scrolledtext.ScrolledText(
            notebook, bg=LOG_BG, fg="#c6d9b6", insertbackground=FG, wrap="none", font=("Consolas", 9)
        )
        notebook.add(self.server_log_view, text="Server log")
        notebook.add(self.flash_log_view, text="Flash / game log")
        actions = tk.Frame(win, bg=BG)
        actions.pack(fill="x", padx=12, pady=(0, 12))
        self._button(actions, "Refresh", self._refresh_log_window).pack(side="left", padx=(0, 4))
        self._button(actions, "Export Logs…", self.export_logs).pack(side="left", padx=4)
        self._button(actions, "Close", win.destroy).pack(side="right")
        win.protocol("WM_DELETE_WINDOW", win.destroy)
        self._refresh_log_window()

    def _refresh_log_window(self):
        if self.log_window is None or not self.log_window.winfo_exists():
            return
        for widget, value in (
            (self.server_log_view, self._read_log(SERVER_LOG_PATH)),
            (self.flash_log_view, self._read_log(FLASH_LOG_PATH)),
        ):
            widget.configure(state="normal")
            widget.delete("1.0", "end")
            widget.insert("1.0", value)
            widget.configure(state="disabled")

    def export_logs(self):
        username = self._selected_username() or "local"
        safe_username = re.sub(r"[^A-Za-z0-9_-]", "_", username)
        filename = "pvz-social-logs-%s-%s.txt" % (datetime.now().strftime("%Y%m%d-%H%M%S"), safe_username)
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title="Export logs",
            initialdir=str(HERE),
            initialfile=filename,
            defaultextension=".txt",
            filetypes=(("Text files", "*.txt"), ("Log files", "*.log"), ("All files", "*.*")),
        )
        if not path:
            return
        contents = [
            "=== PvZ Social Edition log export ===",
            "Generated: %s" % datetime.now().astimezone().isoformat(),
            "Selected account: %s" % username,
            "",
            "=== SERVER LOG ===",
            self._read_log(SERVER_LOG_PATH),
            "",
            "=== FLASH / GAME LOG ===",
            self._read_log(FLASH_LOG_PATH),
            "",
            "=== LAUNCHER ACTIVITY ===",
            "\n".join(self.activity_lines) or "No launcher activity recorded.",
            "",
        ]
        try:
            Path(path).write_text("\n".join(contents), encoding="utf-8")
        except OSError as exc:
            messagebox.showerror("Export Logs", "Couldn't export the logs:\n%s" % exc, parent=self.root)
            return
        self._log("Exported logs to %s" % path)
        messagebox.showinfo("Export Logs", "Logs exported to:\n%s" % path, parent=self.root)

    def _log(self, line):
        text = str(line).rstrip()
        if not text:
            return
        stamped = "[%s] %s" % (datetime.now().strftime("%H:%M:%S"), text)
        self.activity_lines.append(stamped)
        if len(self.activity_lines) > 10_000:
            self.activity_lines = self.activity_lines[-10_000:]
        self.activity.configure(state="normal")
        self.activity.insert("end", stamped + "\n")
        self.activity.see("end")
        self.activity.configure(state="disabled")

    def _poll_output(self):
        try:
            while True:
                item = self.log_queue.get_nowait()
                if isinstance(item, tuple) and item and item[0] == "server-exited":
                    if not self._closing:
                        self._log("Server process exited with code %s." % item[1])
                else:
                    self._log(item)
        except queue.Empty:
            pass
        if not self._closing:
            self.root.after(120, self._poll_output)

    def _poll_processes(self):
        if self.server is not None and self.server.poll() is not None:
            self.server = None
            self.server_ready = port_open()
            self._set_status(
                self.server_status,
                "Running (existing)" if self.server_ready else "Stopped",
                ACCENT if self.server_ready else "#777",
            )
        elif port_open():
            self.server_ready = True
            self._set_status(self.server_status, "Running", ACCENT)
        elif self.server is None:
            self.server_ready = False
            self._set_status(self.server_status, "Stopped", "#777")

        if self.game is not None and self.game.poll() is not None:
            self.game = None
            self.account_box.configure(state="readonly")
            self._set_status(self.game_status, "Stopped", "#777")
            self._log("Game exited.")
        self._update_controls()
        if not self._closing:
            self.root.after(500, self._poll_processes)

    def _update_controls(self):
        server_running = port_open(0.05)
        game_running = self.game is not None and self.game.poll() is None
        self.start_server_btn.configure(state="disabled" if server_running else "normal")
        self.close_server_btn.configure(state="normal" if server_running else "disabled")
        self.start_game_btn.configure(state="disabled" if game_running else "normal")
        self.close_game_btn.configure(state="normal" if game_running else "disabled")
        has_account = self._selected_username() is not None
        self.delete_btn.configure(state="normal" if has_account and not game_running else "disabled")
        self.avatar_btn.configure(state="normal" if has_account else "disabled")
        self.account_box.configure(state="disabled" if game_running else "readonly")

    def on_close(self):
        running = (self.game is not None and self.game.poll() is None) or (
            self.server is not None and self.server.poll() is None
        )
        if running and not messagebox.askokcancel(
            "Quit Launcher", "Close the game and the server started by this launcher?", parent=self.root
        ):
            return
        self._closing = True
        self.close_game(quiet=True)
        if self.server is not None:
            self.close_server(quiet=True)
        self.root.destroy()


def main():
    auto_start_server = "--server" in sys.argv[1:]
    root = tk.Tk()
    Launcher(root, auto_start_server=auto_start_server)
    root.mainloop()


if __name__ == "__main__":
    main()
