"""
Nova Browser - a tabbed web browser built with PyQt6, with Nova built in.

Setup (run once):
    pip install PyQt6 PyQt6-WebEngine

Run:
    python nova_browser.py      (or rename to .pyw to hide the console)

Shortcuts:
    Ctrl+K        command palette (search every feature, tab, bookmark and history)
    Ctrl+T / W    new tab / close tab        Ctrl+Shift+T  reopen closed tab
    Ctrl+Shift+N  private tab                Ctrl+L        address bar
    Ctrl+F        find in page               F5            reload
    Ctrl+D        bookmark page              Ctrl+H        history
    Ctrl+J        downloads                  F9            reader mode
    Ctrl+= / - / 0  zoom in / out / reset (remembered per site)
    Ctrl+Shift+S  screenshot                 Ctrl+Shift+D  dark websites on/off
    Alt+] / Alt+[ / Alt+\\   video faster / slower / normal speed (works on any site's video)
    Alt+N         open/close Nova            Alt+Left / Alt+Right   back / forward
    Ctrl+Shift+F  float tab on top (picture-in-picture for any site)
    Ctrl+\\        split view                 Ctrl+Shift+V  paste and go
    Ctrl+Shift+L  save page for later        Ctrl+Shift+M  notes for this site
    Right-click selected text: Ask Nova about it, translate it with Nova, or search it.
    Right-click a tab: float, save for later, sleep, auto-refresh, duplicate, mute, close others.
    ☰ menu: workspaces, read later, screen time, focus mode, themes, memory saver, chameleon toolbar.
    🎨 Customize (Ctrl+,): 260+ options, live wallpapers, widgets, style packs, rebind every shortcut.
    🎮 Games (Ctrl+Shift+G): 12 free games, updates for games you own, free games of the week.
    📣 Following (Ctrl+Shift+U): teams, leagues, YouTube channels, subreddits, sites & topics you pick.
    (The hubs live in nova_hub.py: keep it in the same folder. Turn either hub off in Customize.)
    📺 Anime tracker (📣 Following → Anime), 💸 game deals + 🏆 XP/levels/badges (🎮 Games).
    🕹 Game Mode (Ctrl+Shift+E), 🧠 tab manager (Shift+Esc), 🖱 mouse gestures (hold right-click + draw),
    🎯 zapper (Alt+Z), 📌 sidebar apps (Alt+B), 🎙 "Hey Nova" voice control (Jarvis section 13ZD).
    🎤 The browser's OWN voice control (Ctrl+Shift+Space or "hey browser"): offline, no Nova needed.
    Nova is optional: without Jarvis.py the browser just runs (Customize → Nova to hide her button).
    (These live in nova_extras.py: keep it in the same folder too.)

Nova panel:
    The ✦ button opens Nova in a side panel. It talks to Jarvis.py through
    her private browser link (Section 13ZC, this PC only). Opening the browser
    starts Nova in the background if she isn't running (she still needs your
    passcode). Closing it shuts her down only if the browser started her.
    🔊 toggles her voice, ⛶ opens her full HUD.

Everything (bookmarks, history, settings, logins) is saved in:
    <your home folder>/.nova_browser/
"""

import os
import sys
import json
import signal
import subprocess
import shutil
import urllib.request
import html
import time
import re
import colorsys
import urllib.parse
from pathlib import Path


# Started with python.exe (which always opens a console window)? Restart right away with pythonw.exe
# (no window) and let the console close. Runs before the slow Qt imports so the console disappears fast.
# Add --console when starting it if you WANT the console (e.g. to see errors).
if __name__ == "__main__" and sys.platform == "win32" and "--console" not in sys.argv \
        and not os.environ.get("NOVA_BROWSER_NO_CONSOLE") and Path(sys.executable).name.lower() == "python.exe":
    _pyw = Path(sys.executable).with_name("pythonw.exe")
    if _pyw.exists():
        try:
            subprocess.Popen([str(_pyw), str(Path(__file__).resolve())] + sys.argv[1:], cwd=os.getcwd(),
                             env=dict(os.environ, NOVA_BROWSER_NO_CONSOLE="1"),
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
                             close_fds=True)
            sys.exit(0)
        except OSError:
            pass                      # couldn't relaunch: just carry on with the console

from PyQt6.QtCore import QUrl, qInstallMessageHandler, Qt, QTimer, QByteArray, QEvent, QObject, pyqtSignal
from PyQt6.QtGui import QAction, QKeySequence, QDesktopServices, QColor, QCursor
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QToolBar, QLineEdit,
    QProgressBar, QToolButton, QMenu, QDockWidget, QWidget, QVBoxLayout,
    QHBoxLayout, QTextBrowser, QPushButton, QLabel, QFileDialog, QDialog,
    QListWidget, QListWidgetItem, QInputDialog, QMessageBox, QSplitter, QCheckBox, QComboBox,
    QSpinBox, QKeySequenceEdit, QTextEdit, QColorDialog, QScrollArea, QTabBar, QStackedWidget, QSizePolicy,
    QFrame, QSystemTrayIcon, QStyle, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView
)
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkProxy, QNetworkReply
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import (
    QWebEngineProfile, QWebEnginePage, QWebEngineScript, QWebEngineSettings,
    QWebEngineUrlRequestInterceptor, QWebEngineUrlRequestInfo, QWebEngineDownloadRequest
)

# Hide Qt + website console spam in the terminal
qInstallMessageHandler(lambda *args: None)

# 🎮 Games + 📣 Following hubs live in nova_hub.py (keep it next to this file). The browser works without it.
try:
    import nova_hub as HUB
except Exception as _hub_error:
    HUB = None
    print("[hubs] nova_hub.py not loaded:", _hub_error)

# Game Mode, tab manager, gestures, zapper, sidebar apps, voice link live in nova_extras.py (same folder).
try:
    import nova_extras as EX
except Exception as _ex_error:
    EX = None
    print("[extras] nova_extras.py not loaded:", _ex_error)

# ---------- settings & storage ----------
MAX_HISTORY = 500

# Running as the packaged "Nova Browser.exe" (PyInstaller) or as a Python script?
FROZEN = bool(getattr(sys, "frozen", False))
APP_PATH = Path(sys.executable).resolve() if FROZEN else Path(__file__).resolve()
RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", APP_PATH.parent))      # where nova.ico is bundled
ICON_FILE = RESOURCE_DIR / "nova.ico"

DATA_DIR = Path.home() / ".nova_browser"
DATA_DIR.mkdir(exist_ok=True)
BOOKMARKS_FILE = DATA_DIR / "bookmarks.json"
HISTORY_FILE = DATA_DIR / "history.json"
SESSION_FILE = DATA_DIR / "session.json"
START_FILE = DATA_DIR / "start.html"
START_URL = QUrl.fromLocalFile(str(START_FILE))
SETTINGS_FILE = DATA_DIR / "settings.json"
PROFILE_DIR = DATA_DIR / "profile"            # cookies + logins, so you stay signed in
SCREENSHOT_DIR = Path.home() / "Pictures" / "Nova Browser"
DOWNLOAD_DIR = Path.home() / "Downloads"

# Nova link: while Jarvis.py runs (Section 13ZC) she writes her private port + secret code here
BRIDGE_FILE = DATA_DIR / "nova_bridge.json"
NOVA_LOG = DATA_DIR / "nova_log.txt"           # what Nova prints while the browser runs her in the background
ALIVE_FILE = DATA_DIR / "nova_alive.json"      # written by Jarvis.py the moment she starts (even before her link is up)
PAGE_TEXT_LIMIT = 6000                         # how much of the open page Nova gets to read
ZAPS_FILE = DATA_DIR / "zaps.json"             # things you zapped off websites (per site)
VOICE_DIR = DATA_DIR / "voice"                 # the offline speech model for 🎤 voice control
HELP_FILE = DATA_DIR / "help.html"             # the ❓ Help page (rebuilt with your colours + shortcuts)

def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def save_json(path, data):
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_settings():
    raw = load_json(SETTINGS_FILE, {})
    raw = raw if isinstance(raw, dict) else {}
    out = dict(raw)
    for k, v in DEFAULT_SETTINGS.items():
        o = OPTION_BY_KEY.get(k)
        if k not in out:
            out[k] = json.loads(json.dumps(v))
        elif o is not None and not valid_value(o, out[k]):
            out[k] = json.loads(json.dumps(v))
        elif o is None and not (isinstance(out[k], type(v)) or (isinstance(v, (int, float)) and isinstance(out[k], (int, float)))):
            out[k] = json.loads(json.dumps(v))
    return out


def pid_alive(pid) -> bool:
    """Is the process with this id still running? (only looks, never touches it)"""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        h = k32.OpenProcess(0x1000, False, pid)          # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return ctypes.get_last_error() == 5           # access denied = it exists (e.g. Nova runs as admin)
        code = ctypes.c_ulong()
        ok = k32.GetExitCodeProcess(h, ctypes.byref(code))
        k32.CloseHandle(h)
        return bool(ok) and code.value == 259             # STILL_ACTIVE
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def nova_running_pid():
    """Process id of a running Nova (fully up or still booting), or 0."""
    for f in (ALIVE_FILE, BRIDGE_FILE):
        info = load_json(f, {})
        if isinstance(info, dict) and pid_alive(info.get("pid")):
            return int(info["pid"])
    return 0


def is_start_page(url: QUrl) -> bool:
    return url.isLocalFile() and url.fileName() == START_FILE.name


def is_web(url: str) -> bool:
    return url.startswith(("http://", "https://"))


def host_of(url) -> str:
    h = (url.host() if isinstance(url, QUrl) else QUrl(url).host()).lower()
    return h[4:] if h.startswith("www.") else h


# ==============================================================================
# CUSTOMIZATION: every option lives in this one list. The Customize window is built from it,
# and each option's "apply" says what refreshes when it changes:
#   chrome = the browser's look, start = the start page, web = how pages load/behave,
#   nova = the Nova panel, keys = keyboard shortcuts, use = read whenever the feature is used
# ==============================================================================
OPTIONS = []
FONTS = ["Segoe UI", "Bahnschrift", "Cascadia Code", "Consolas", "Arial", "Verdana", "Tahoma", "Trebuchet MS",
         "Georgia", "Times New Roman", "Calibri", "Candara", "Corbel", "Franklin Gothic Medium", "Lucida Console",
         "Comic Sans MS", "Impact", "Segoe Print", "Ink Free", "Courier New"]
POSITIONS = ["Left", "Center", "Right", "Hidden"]
WALLPAPERS = ["Constellation", "Starfield", "Matrix rain", "Aurora", "Fireflies", "Snow", "Rain", "Synthwave grid",
              "Bubbles", "Waves", "Sakura petals", "Hyperspace", "Nebula", "Time-of-day sky", "Flowing gradient",
              "Gradient", "Solid colour", "Your image", "Your video", "Slideshow"]


def opt(key, cat, label, kind, default, apply="use", **kw):
    OPTIONS.append(dict(key=key, cat=cat, label=label, kind=kind, default=default, apply=apply, **kw))


# ---- Appearance --------------------------------------------------------------
A = "Appearance"
opt("theme", A, "Accent colour", "choice", "Nova Blue", "chrome",
    choices=["Nova Blue", "Neon Purple", "Cyber Green", "Sunset Orange", "Sakura Pink", "Ice Cyan", "Crimson",
             "Gold", "Mint", "Lavender", "Custom"])
opt("custom_accent", A, "Custom accent colour (pick 'Custom' above)", "color", "#6c8cff", "chrome")
opt("base_palette", A, "Background palette", "choice", "Graphite", "chrome",
    choices=["Graphite", "Midnight", "OLED Black", "Navy", "Plum", "Forest", "Mocha", "Slate", "Crimson Night", "Ocean"])
opt("ui_font", A, "Interface font", "choice", "Segoe UI", "chrome", choices=FONTS)
opt("ui_font_size", A, "Interface text size", "int", 13, "chrome", min=9, max=20, suffix=" px")
opt("corner_radius", A, "Roundness of buttons & fields", "int", 8, "chrome", min=0, max=20, suffix=" px")
opt("button_size", A, "Toolbar icon size", "int", 14, "chrome", min=10, max=24, suffix=" px")
opt("toolbar_spacing", A, "Space between toolbar buttons", "int", 4, "chrome", min=0, max=16, suffix=" px")
opt("toolbar_position", A, "Toolbar position", "choice", "Top", "chrome", choices=["Top", "Bottom"])
opt("address_style", A, "Address bar style", "choice", "Rounded", "chrome", choices=["Rounded", "Pill", "Square", "Underline"])
opt("address_font_size", A, "Address bar text size", "int", 13, "chrome", min=10, max=20, suffix=" px")
opt("address_centered", A, "Center the address bar text", "bool", False, "chrome")
opt("tab_shape", A, "Tab shape", "choice", "Rounded", "chrome", choices=["Rounded", "Pill", "Square", "Underline", "Slanted glow"])
opt("tab_height", A, "Tab size", "choice", "Normal", "chrome", choices=["Compact", "Normal", "Roomy"])
opt("tab_max_width", A, "Maximum tab width", "int", 220, "chrome", min=100, max=420, suffix=" px")
opt("tab_title_length", A, "Characters shown in tab titles", "int", 24, "chrome", min=6, max=60)
opt("tab_position", A, "Tab bar position", "choice", "Top", "chrome", choices=["Top", "Bottom"])
opt("tab_close_buttons", A, "Show close (×) on tabs", "bool", True, "chrome")
opt("tabs_movable", A, "Drag tabs to reorder", "bool", True, "chrome")
opt("tab_glow", A, "Glow under the selected tab", "bool", True, "chrome")
opt("show_status_bar", A, "Show the status bar", "bool", True, "chrome")
opt("window_opacity", A, "Window see-through-ness (100 = solid)", "int", 100, "chrome", min=40, max=100, suffix=" %")
opt("always_on_top", A, "Keep the browser above other windows", "bool", False, "chrome")
opt("custom_titlebar", A, "Browser-style window (no Windows title bar, tabs at the very top)", "bool", True, "chrome")
opt("menu_roundness", A, "Menu roundness", "int", 6, "chrome", min=0, max=16, suffix=" px")
opt("scrollbar_style", A, "Scrollbars in Nova's own windows", "choice", "Slim", "chrome", choices=["Slim", "Hidden", "Standard"])
opt("loading_bar_size", A, "Loading bar thickness", "int", 2, "chrome", min=1, max=8, suffix=" px")
for _k, _l in (("back", "Back"), ("forward", "Forward"), ("reload", "Reload"), ("home", "Home"), ("star", "Bookmark star"),
               ("bookmarks", "Bookmarks menu"), ("history", "History menu"), ("downloads", "Downloads"),
               ("shield", "Ad blocker shield"), ("newtab", "New tab (+)"), ("nova", "Nova (✦)"), ("customize", "Customize (🎨)"),
               ("games", "Games (🎮)"), ("follow", "Following (📣)"), ("gamemode", "Game Mode (🕹)"),
               ("ram", "Memory meter (🧠)"), ("mic", "Voice (🎤)"), ("help", "Help (❓)"),
               ("menu", "Main menu (☰)")):
    opt(f"show_btn_{_k}", "Toolbar buttons", f"Show “{_l}” button", "bool", True, "chrome")

# ---- Start page ---------------------------------------------------------------
SP = "Start page"
opt("sp_title", SP, "Start page tab title", "text", "New Tab", "start")
opt("sp_layout", SP, "Center column position", "choice", "Centered", "start", choices=["Centered", "Top", "Left"])
opt("sp_font", SP, "Start page font", "choice", "Segoe UI", "start", choices=FONTS)
opt("sp_text_color", SP, "Start page text colour", "color", "#e6e6e6", "start")
opt("sp_show_logo", SP, "Show the logo", "bool", True, "start")
opt("sp_logo_text", SP, "Logo text", "text", "NOVA", "start")
opt("sp_logo_size", SP, "Logo size", "int", 64, "start", min=16, max=160, suffix=" px")
opt("sp_logo_font", SP, "Logo font", "choice", "Segoe UI", "start", choices=FONTS)
opt("sp_logo_style", SP, "Logo style", "choice", "Glow", "start", choices=["Glow", "Gradient", "Outline", "Plain"])
opt("sp_show_greeting", SP, "Show greeting", "bool", True, "start")
opt("sp_user_name", SP, "Your name (for the greeting)", "text", "", "start")
opt("sp_greeting_mode", SP, "Greeting", "choice", "Time of day", "start", choices=["Time of day", "Custom"])
opt("sp_custom_greeting", SP, "Custom greeting text", "text", "Welcome back", "start")
opt("sp_show_tip", SP, "Show a random tip at the bottom", "bool", True, "start")
opt("sp_links_new_tab", SP, "Open start page links in a new tab", "bool", False, "start")
opt("sp_show_search", SP, "Show the search box", "bool", True, "start")
opt("sp_search_position", SP, "Search box position", "choice", "Above widgets", "start", choices=["Above widgets", "Below widgets"])
opt("sp_search_style", SP, "Search box style", "choice", "Pill", "start", choices=["Pill", "Rounded", "Square", "Underline"])
opt("sp_search_width", SP, "Search box width", "int", 600, "start", min=280, max=1000, suffix=" px")
opt("sp_search_placeholder", SP, "Search box hint text", "text", "Search the web", "start")
opt("sp_search_autofocus", SP, "Put the cursor in the search box", "bool", True, "start")
opt("sp_search_glow", SP, "Glow around the search box", "bool", True, "start")
opt("sp_show_tiles", SP, "Show site tiles", "bool", True, "start")
opt("sp_tile_source", SP, "Tiles show", "choice", "Bookmarks", "start", choices=["Bookmarks", "Most visited", "Both"])
opt("sp_tile_count", SP, "Number of tiles", "int", 12, "start", min=1, max=36)
opt("sp_tile_size", SP, "Tile size", "int", 104, "start", min=64, max=180, suffix=" px")
opt("sp_tile_shape", SP, "Tile shape", "choice", "Rounded", "start", choices=["Rounded", "Square", "Circle"])
opt("sp_tile_style", SP, "Tile style", "choice", "Glass", "start", choices=["Glass", "Solid", "Outline", "Minimal"])
opt("sp_tile_labels", SP, "Show tile names", "bool", True, "start")

# ---- Wallpaper ------------------------------------------------------------------
WP = "Wallpaper"
opt("wp_type", WP, "Wallpaper", "choice", "Constellation", "start", choices=WALLPAPERS)
opt("wp_speed", WP, "Animation speed", "int", 5, "start", min=1, max=10)
opt("wp_density", WP, "Amount (particles, stars, drops…)", "int", 5, "start", min=1, max=10)
opt("wp_color_mode", WP, "Wallpaper colours", "choice", "Accent", "start", choices=["Accent", "Rainbow", "Custom", "White"])
opt("wp_color", WP, "Custom colour 1 (also gradient / solid colour)", "color", "#6c8cff", "start")
opt("wp_color2", WP, "Custom colour 2 (also gradient end)", "color", "#ff6fae", "start")
opt("wp_gradient_angle", WP, "Gradient angle", "int", 135, "start", min=0, max=360, suffix="°")
opt("wp_mouse", WP, "Wallpaper reacts to your mouse", "bool", True, "start")
opt("wp_dim", WP, "Darken wallpaper", "int", 20, "start", min=0, max=90, suffix=" %")
opt("wp_blur", WP, "Blur wallpaper", "int", 0, "start", min=0, max=30, suffix=" px")
opt("wp_vignette", WP, "Dark edges (vignette)", "bool", False, "start")
opt("wp_fps", WP, "Animation smoothness", "choice", "60", "start", choices=["30", "60", "Unlimited"])
opt("wp_image", WP, "Your image (for 'Your image')", "file", "", "start", filter="Images (*.png *.jpg *.jpeg *.gif *.webp *.bmp)")
opt("wp_video", WP, "Your video (for 'Your video')", "file", "", "start", filter="Videos (*.mp4 *.webm *.ogg *.mov)")
opt("wp_folder", WP, "Image folder (for 'Slideshow')", "folder", "", "start")
opt("wp_interval", WP, "Slideshow: seconds per image", "int", 30, "start", min=5, max=3600, suffix=" s")

# ---- Widgets ------------------------------------------------------------------------
WS = "Widget style"
opt("wg_style", WS, "Widget style", "choice", "Glass", "start", choices=["Glass", "Solid", "Outline", "Neon", "Minimal"])
opt("wg_opacity", WS, "Widget background strength", "int", 70, "start", min=0, max=100, suffix=" %")
opt("wg_radius", WS, "Widget roundness", "int", 16, "start", min=0, max=32, suffix=" px")
opt("wg_blur", WS, "Glass blur", "int", 12, "start", min=0, max=40, suffix=" px")
opt("wg_scale", WS, "Widget text size", "int", 100, "start", min=70, max=160, suffix=" %")
opt("wg_shadow", WS, "Widget shadows", "bool", True, "start")
opt("wg_accent_titles", WS, "Colour widget titles with the accent", "bool", False, "start")
opt("wg_animate", WS, "Widgets fade in", "bool", True, "start")
opt("wg_draggable", WS, "Show ✎ Layout (drag widgets anywhere)", "bool", True, "start")

WD = "Widgets"
WIDGETS = [  # id, title, default position, extra options [(key, label, kind, default, kw)]
    ("clock", "Clock", "Center", [("style", "Clock style", "choice", "Digital", {"choices": ["Digital", "Analog", "Big", "Minimal", "Binary"]}),
                                  ("h24", "24-hour time", "bool", False, {}), ("seconds", "Show seconds", "bool", False, {}),
                                  ("date", "Show the date", "bool", True, {}),
                                  ("date_format", "Date format", "choice", "Weekday, Month Day",
                                   {"choices": ["Weekday, Month Day", "Nov 4", "2026-11-04", "11/04/2026", "04/11/2026"]})]),
    ("asknova", "Ask Nova", "Hidden", []),
    ("weather", "Weather", "Right", [("city", "City", "text", "", {}), ("units", "Units", "choice", "°F", {"choices": ["°F", "°C"]}),
                                     ("days", "Forecast days", "int", 3, {"min": 0, "max": 7})]),
    ("spark", "Daily spark", "Right", []),
    ("todo", "To-do", "Left", []),
    ("notes", "Notes", "Hidden", []),
    ("pomodoro", "Pomodoro", "Hidden", [("work", "Focus minutes", "int", 25, {"min": 1, "max": 120}),
                                        ("brk", "Break minutes", "int", 5, {"min": 1, "max": 60}),
                                        ("sound", "Beep when time is up", "bool", True, {})]),
    ("countdown", "Countdown", "Hidden", [("date", "Count down to (YYYY-MM-DD HH:MM)", "text", "", {})]),
    ("calendar", "Calendar", "Hidden", [("week_start", "Week starts on", "choice", "Sunday", {"choices": ["Sunday", "Monday"]})]),
    ("worldclock", "World clock", "Hidden", [("zones", "Cities (Name:Time/Zone, …)", "text",
                                              "Tokyo:Asia/Tokyo, London:Europe/London, New York:America/New_York", {}),
                                             ("h24", "24-hour time", "bool", False, {})]),
    ("stopwatch", "Stopwatch", "Hidden", []),
    ("history", "Recently visited", "Hidden", [("count", "How many", "int", 8, {"min": 1, "max": 30})]),
    ("readlater", "Read later", "Hidden", []),
    ("screentime", "Screen time today", "Hidden", []),
    ("scores", "My teams", "Hidden", []),
    ("followfeed", "Following", "Hidden", [("count", "How many", "int", 6, {"min": 1, "max": 20})]),
    ("gamenews", "Game updates", "Hidden", [("count", "How many", "int", 5, {"min": 1, "max": 20})]),
    ("anime", "Next episodes", "Hidden", [("count", "How many", "int", 5, {"min": 1, "max": 12})]),
]
for _id, _title, _pos, _extra in WIDGETS:
    opt(f"w_{_id}_pos", WD, f"{_title}: where", "choice", _pos, "start", choices=POSITIONS)
    opt(f"w_{_id}_title", WD, f"{_title}: title", "text", "" if _id == "clock" else _title, "start")
    for _k, _l, _kind, _d, _kw in _extra:
        opt(f"w_{_id}_{_k}", WD, f"{_title}: {_l.lower()}", _kind, _d, "start", **_kw)

# ---- Browsing -----------------------------------------------------------------------
B = "Browsing"
SEARCH_ENGINES = {
    "DuckDuckGo": "https://duckduckgo.com/?q=%s", "Google": "https://www.google.com/search?q=%s",
    "Bing": "https://www.bing.com/search?q=%s", "Brave": "https://search.brave.com/search?q=%s",
    "Startpage": "https://www.startpage.com/do/search?q=%s", "Ecosia": "https://www.ecosia.org/search?q=%s",
    "YouTube": "https://www.youtube.com/results?search_query=%s", "Custom": "",
}
opt("search_engine", B, "Search engine", "choice", "DuckDuckGo", "start", choices=list(SEARCH_ENGINES))
opt("custom_search", B, "Custom search address (%s = your words)", "text", "https://example.com/search?q=%s", "start")
opt("new_tab_page", B, "New tabs open", "choice", "Start page", "use", choices=["Start page", "Blank page", "Home address"])
opt("home_url", B, "Home address", "text", "", "use")
opt("home_button_opens", B, "⌂ button opens", "choice", "Start page", "use", choices=["Start page", "Home address"])
opt("restore_session", B, "Reopen my tabs when the browser starts", "bool", True, "use")
opt("confirm_close", B, "Ask before closing with several tabs open", "bool", False, "use")
opt("link_hover_status", B, "Show link address when hovering", "bool", True, "use")
opt("https_only", B, "HTTPS-only (upgrade insecure pages)", "bool", False, "use")
opt("default_zoom", B, "Default page zoom", "int", 100, "use", min=30, max=300, suffix=" %")
opt("smooth_scroll", B, "Smooth scrolling", "bool", True, "web")
opt("show_scrollbars", B, "Show page scrollbars", "bool", True, "web")
opt("javascript", B, "JavaScript", "bool", True, "web")
opt("images", B, "Load images", "bool", True, "web")
opt("popups", B, "Let pages open pop-up windows", "bool", True, "web")
opt("autoplay_gesture", B, "Videos wait for a click before playing", "bool", False, "web")
opt("pdf_viewer", B, "Built-in PDF viewer", "bool", True, "web")
opt("webgl", B, "WebGL (3D graphics on pages)", "bool", True, "web")
opt("canvas_accel", B, "Hardware-accelerated canvas", "bool", True, "web")
opt("local_storage", B, "Let sites save data (local storage)", "bool", True, "web")
opt("dns_prefetch", B, "Pre-load links for speed (DNS prefetch)", "bool", False, "web")
opt("spatial_nav", B, "Arrow keys jump between links", "bool", False, "web")
opt("print_backgrounds", B, "Print backgrounds", "bool", True, "web")
opt("error_pages", B, "Friendly error pages", "bool", True, "web")
opt("focus_on_load", B, "Pages grab keyboard focus when they load", "bool", True, "web")
opt("page_font", B, "Default page font", "choice", "Segoe UI", "web", choices=FONTS)
opt("page_fixed_font", B, "Default code font", "choice", "Consolas", "web", choices=FONTS)
opt("page_font_size", B, "Default page text size", "int", 16, "web", min=8, max=32, suffix=" px")
opt("min_font_size", B, "Smallest text allowed on pages", "int", 0, "web", min=0, max=24, suffix=" px")
opt("user_agent", B, "Pretend to be (user agent)", "choice", "Default", "web",
    choices=["Default", "Chrome on Windows", "Edge on Windows", "Firefox on Windows", "Safari on Mac", "Chrome on Android", "Safari on iPhone"])
opt("accept_language", B, "Preferred page languages", "text", "en-US,en;q=0.9", "web")
opt("cache_size_mb", B, "Cache size limit (0 = automatic)", "int", 0, "web", min=0, max=4000, suffix=" MB")
opt("memory_saver", B, "Memory saver (sleep unused tabs)", "bool", True, "use")
opt("ram_meter", B, "Show how much memory the browser uses (🧠 on the toolbar)", "bool", True, "extras")
opt("sleep_minutes", B, "Sleep tabs unused for", "int", 30, "use", min=5, max=240, suffix=" min")
opt("dark_web", B, "Dark websites", "bool", False, "web")
opt("adblock", B, "Block ads & trackers", "bool", True, "web")
opt("chameleon", B, "Chameleon toolbar (site colours)", "bool", False, "use")

V = "Video & reading"
opt("video_step", V, "Video speed step", "choice", "0.25", "use", choices=["0.1", "0.25", "0.5"])
opt("speed_badge", V, "Show the speed badge on videos", "bool", True, "web")
opt("reader_font", V, "Reader mode font", "choice", "Georgia", "use", choices=FONTS)
opt("reader_size", V, "Reader mode text size", "int", 19, "use", min=12, max=32, suffix=" px")
opt("reader_width", V, "Reader mode column width", "int", 720, "use", min=480, max=1200, suffix=" px")
opt("reader_line", V, "Reader mode line spacing", "choice", "1.75", "use", choices=["1.4", "1.6", "1.75", "2.0"])
opt("reader_bg", V, "Reader mode background", "choice", "Dark", "use", choices=["Dark", "Sepia", "Light", "OLED"])
opt("global_css", V, "Your CSS for every website (advanced)", "multiline", "", "web")

PR = "Privacy"
opt("history_enabled", PR, "Save browsing history", "bool", True, "use")
opt("max_history", PR, "Pages kept in history", "int", 500, "use", min=50, max=10000)
opt("screen_time_enabled", PR, "Count screen time", "bool", True, "use")
opt("private_by_default", PR, "New tabs are private", "bool", False, "use")
opt("dnt", PR, "Send 'Do Not Track'", "bool", True, "web")
opt("gpc", PR, "Send 'Global Privacy Control'", "bool", True, "web")
opt("block_3p_cookies", PR, "Block third-party cookies", "bool", True, "web")
opt("clear_history_exit", PR, "Clear history when closing", "bool", False, "use")
opt("clear_cookies_exit", PR, "Clear cookies when closing (signs you out)", "bool", False, "use")
opt("clear_cache_exit", PR, "Clear cache when closing", "bool", False, "use")

NV = "Nova"
opt("nova_on", NV, "✦ Nova assistant features (Jarvis.py). Turn off if Nova isn't on this PC", "bool", True, "extras")
opt("nova_autostart", NV, "Start Nova with the browser", "bool", True, "use")
opt("nova_open_on_start", NV, "Open the Nova panel at start", "bool", False, "use")
opt("nova_side", NV, "Nova panel side", "choice", "Right", "nova", choices=["Right", "Left"])
opt("nova_width", NV, "Nova panel width", "int", 380, "nova", min=300, max=800, suffix=" px")
opt("nova_speaks", NV, "Nova speaks her answers", "bool", True, "nova")
opt("nova_selection_menu", NV, "Ask Nova in the right-click menu", "bool", True, "use")
opt("nova_voice_control", NV, "🎙 Let Nova control the browser when you talk to her (needs Jarvis section 13ZD)", "bool", True, "extras")
opt("nova_voice_raise", NV, "Bring the browser to the front when you tell Nova to open something", "bool", True, "use")
opt("nova_chip1", NV, "Quick button 1 (Label | what to ask)", "text", "Summarize page | Summarize this page for me.", "nova")
opt("nova_chip2", NV, "Quick button 2", "text", "Explain simply | Explain this page simply, like I'm new to it.", "nova")
opt("nova_chip3", NV, "Quick button 3", "text", "Key points | Give me the key points of this page.", "nova")

HB = "Games & Following"
opt("hub_games", HB, "🎮 Games hub (free games to play + updates for games you own)", "bool", True, "hub")
opt("hub_follow", HB, "📣 Following hub (teams, leagues, channels, sites & topics you pick)", "bool", True, "hub")
opt("hub_notify", HB, "Alerts for things you follow", "bool", True, "hub")
opt("hub_notify_scores", HB, "Alerts: your team's game starts & final scores", "bool", True, "hub")
opt("hub_notify_news", HB, "Alerts: new videos, posts & news", "bool", True, "hub")
opt("hub_notify_games", HB, "Alerts: new updates for your games", "bool", True, "hub")
opt("hub_notify_free", HB, "Alerts: new free games", "bool", True, "hub")
opt("hub_windows_notify", HB, "Also show alerts as Windows notifications (when the browser isn't in front)", "bool", False, "hub")
opt("hub_badges", HB, "Show new-update counts on the 🎮 and 📣 buttons", "bool", True, "hub")
opt("hub_refresh", HB, "Check for updates every", "int", 15, "hub", min=5, max=180, suffix=" min")
opt("hub_live_refresh", HB, "Live score refresh while your team is playing", "int", 60, "hub", min=20, max=300, suffix=" s")
opt("games_free_week", HB, "Show free games of the week (Epic Games Store)", "bool", True, "hub")
opt("games_web_sites", HB, "Show links to free web game sites", "bool", True, "hub")
opt("hub_notify_anime", HB, "Alerts: new anime episodes", "bool", True, "hub")
opt("hub_notify_deals", HB, "Alerts: price drops on your deals wishlist", "bool", True, "hub")
opt("games_deals", HB, "💸 Game deals (wishlist price tracking, CheapShark)", "bool", True, "hub")
opt("games_top_deals", HB, "Show today's top game deals", "bool", True, "hub")
opt("xp_on", HB, "🏆 XP, levels, badges & unlockable style packs", "bool", True, "hub")
opt("steam_api_key", HB, "Steam Web API key (optional: import your whole Steam library; saved only on this PC)", "text", "", "hub")
opt("steam_id", HB, "Steam ID or profile link (optional, goes with the key above)", "text", "", "hub")

VC = "Voice control"
VOICE_MODES = ["Push to talk (🎤 button or Ctrl+Shift+Space)", "Always listening for the wake word"]
opt("voice_on", VC, "🎤 Built-in voice control (works without Nova, runs offline on this PC)", "bool", True, "extras")
opt("voice_mode", VC, "How to talk to the browser", "choice", VOICE_MODES[0], "extras", choices=VOICE_MODES)
opt("voice_wake", VC, "Wake word (for always-listening mode)", "text", "hey browser", "extras")
opt("voice_model", VC, "Speech model", "choice", "Small (40 MB, fastest)", "extras",
    choices=list(EX.VOSK_MODELS) if EX else ["Small (40 MB, fastest)"])
opt("voice_command_mode", VC, "Command mode: match what you say to real commands (stops words getting mixed up)", "bool", True, "extras")
opt("voice_speak", VC, "Speak answers out loud (scores, episodes, deals …)", "bool", True, "use")
opt("voice_rate", VC, "Speaking speed", "int", 0, "use", min=-5, max=5)
opt("voice_unknown_search", VC, "If I don't understand, search the web for what you said", "bool", False, "use")
opt("voice_while_gaming", VC, "Keep listening for the wake word during Game Mode", "bool", False, "extras")
opt("voice_bubble", VC, "Show what I heard at the bottom of the window", "bool", True, "use")

GM = "Game Mode"
opt("game_mode_auto", GM, "Turn on Game Mode when you start a game from 🎮 Games", "bool", True, "use")
opt("game_mode_detect", GM, "Also turn it on when one of your linked games starts any other way (Steam, Epic, desktop)", "bool", True, "extras")
opt("game_mode_exit", GM, "Turn Game Mode off by itself when the game closes", "bool", True, "use")
opt("game_mode_sleep", GM, "Put background tabs to sleep (frees memory for the game)", "bool", True, "use")
opt("game_mode_mute", GM, "Mute every tab", "bool", True, "use")
opt("game_mode_pause", GM, "Pause videos & music playing in tabs", "bool", True, "use")
opt("game_mode_hold_alerts", GM, "Hold alerts until you're done playing", "bool", True, "use")
opt("game_mode_minimize", GM, "Minimize the browser", "bool", False, "use")

GESTURE_ACTIONS = [("back", "Back"), ("forward", "Forward"), ("reload", "Reload"), ("new_tab", "New tab"),
                   ("close_tab", "Close tab"), ("reopen", "Reopen closed tab"), ("next_tab", "Next tab"),
                   ("prev_tab", "Previous tab"), ("scroll_top", "Scroll to top"), ("scroll_bottom", "Scroll to bottom"),
                   ("home", "Home"), ("zoom_in", "Zoom in"), ("zoom_out", "Zoom out"), ("zoom_reset", "Reset zoom"),
                   ("reader", "Reader mode"), ("screenshot", "Screenshot"), ("bookmark", "Bookmark page"),
                   ("mute", "Mute / unmute tab"), ("fullscreen", "Full-screen window"), ("nova", "Open/close Nova"),
                   ("summarize", "Nova: summarize this page"), ("palette", "Command palette"), ("float", "Float tab on top"),
                   ("split", "Split view"), ("later", "Save for later"), ("games", "Games hub"), ("following", "Following hub"),
                   ("game_mode", "Game Mode on/off"), ("tab_manager", "Tab manager"), ("zap", "Zap things on this page"),
                   ("sidebar", "Show/hide sidebar app"), ("private_tab", "New private tab")]
GESTURE_LABEL = {cid: label for cid, label in GESTURE_ACTIONS}
GESTURE_ID = {label: cid for cid, label in GESTURE_ACTIONS}
_G_ARROWS = [("L", "←"), ("R", "→"), ("U", "↑"), ("D", "↓"), ("DR", "↓→"), ("DL", "↓←"), ("UD", "↑↓"), ("DU", "↓↑"),
             ("UL", "↑←"), ("UR", "↑→"), ("LR", "←→"), ("RL", "→←")]
_G_DEFAULT = {"L": "back", "R": "forward", "U": "scroll_top", "D": "scroll_bottom", "DR": "close_tab", "DL": "reopen",
              "UD": "reload", "DU": "new_tab", "UL": "prev_tab", "UR": "next_tab", "LR": "", "RL": ""}

GS = "Gestures & Zapper"
opt("gestures", GS, "Mouse gestures: hold the right mouse button and draw", "bool", True, "use")
opt("gesture_hint", GS, "Show what a gesture will do while you draw it", "bool", True, "use")
for _code, _arrows in _G_ARROWS:
    opt(f"gesture_{_code}", GS, f"Gesture {_arrows}", "choice", GESTURE_LABEL.get(_G_DEFAULT[_code], "Nothing"), "use",
        choices=["Nothing"] + [label for _cid, label in GESTURE_ACTIONS])
opt("zapper_menu", GS, "Show “🎯 Zap something on this page” in the right-click menu", "bool", True, "use")

SB = "Sidebar apps"
opt("sidebar_on", SB, "Sidebar apps strip (open Discord, music & chats beside your tabs)", "bool", True, "extras")
opt("sidebar_side", SB, "Sidebar side", "choice", "Left", "extras", choices=["Left", "Right"])
opt("sidebar_width", SB, "Sidebar app width", "int", 420, "extras", min=300, max=1000, suffix=" px")
for _sid, _sname, _sicon, _surl, _son in (EX.SIDEBAR_APPS if EX else []):
    opt(f"sb_{_sid}", SB, f"{_sicon}  {_sname}", "bool", _son, "extras")
opt("sidebar_custom", SB, "Your own sidebar apps  (Name | address; Name | address)", "text", "", "extras")

FC = "Focus"
opt("focus_default", FC, "Focus session length (Ctrl+K → Focus)", "int", 25, "use", min=5, max=240, suffix=" min")
opt("focus_show_timer", FC, "Show the focus countdown", "bool", True, "use")

# ---- Keyboard shortcuts (every command can be rebound) --------------------------------
KEY_COMMANDS = [
    ("palette", "Command palette", "Ctrl+K"), ("customize", "Customize", "Ctrl+,"), ("new_tab", "New tab", "Ctrl+T"),
    ("private_tab", "New private tab", "Ctrl+Shift+N"), ("reopen", "Reopen closed tab", "Ctrl+Shift+T"),
    ("close_tab", "Close tab", "Ctrl+W"), ("next_tab", "Next tab", "Ctrl+Tab"), ("prev_tab", "Previous tab", "Ctrl+Shift+Tab"),
    ("address", "Go to address bar", "Ctrl+L"), ("back", "Back", "Alt+Left"), ("forward", "Forward", "Alt+Right"),
    ("reload", "Reload", "F5"), ("home", "Home", "Alt+Home"), ("bookmark", "Bookmark page", "Ctrl+D"),
    ("history", "History", "Ctrl+H"), ("downloads", "Downloads", "Ctrl+J"), ("find", "Find on page", "Ctrl+F"),
    ("reader", "Reader mode", "F9"), ("screenshot", "Screenshot", "Ctrl+Shift+S"),
    ("dark", "Dark websites on/off", "Ctrl+Shift+D"), ("adblock", "Ad blocker on/off", ""),
    ("faster", "Video faster", "Alt+]"), ("slower", "Video slower", "Alt+["), ("normal_speed", "Video normal speed", "Alt+\\"),
    ("zoom_in", "Zoom in", "Ctrl+="), ("zoom_in2", "Zoom in (other key)", "Ctrl++"), ("zoom_out", "Zoom out", "Ctrl+-"),
    ("zoom_reset", "Reset zoom", "Ctrl+0"), ("float", "Float tab on top", "Ctrl+Shift+F"), ("split", "Split view", "Ctrl+\\"),
    ("paste_go", "Paste and go", "Ctrl+Shift+V"), ("later", "Save for later", "Ctrl+Shift+L"),
    ("notes", "Notes for this site", "Ctrl+Shift+M"), ("nova", "Open/close Nova", "Alt+N"),
    ("fullscreen", "Full-screen window", "F11"), ("screen_time", "Screen time", ""), ("focus", "Start focus mode", ""),
    ("workspace_save", "Save tabs as workspace", ""), ("qr", "Send page to phone", ""), ("surprise", "Surprise me (random look)", ""),
    ("mute", "Mute / unmute tab", ""), ("print", "Save page as PDF", "Ctrl+P"),
    ("games", "Games hub", "Ctrl+Shift+G"), ("following", "Following hub", "Ctrl+Shift+U"),
    ("game_mode", "Game Mode on/off", "Ctrl+Shift+E"), ("tab_manager", "Tab manager (memory)", "Shift+Esc"),
    ("zap", "Zap things on this page", "Alt+Z"), ("unzap", "Un-zap this site", ""),
    ("sidebar", "Show/hide sidebar app", "Alt+B"), ("summarize", "Nova: summarize this page", "Alt+S"),
    ("scroll_top", "Scroll to top", ""), ("scroll_bottom", "Scroll to bottom", ""),
    ("voice", "Voice command (talk to the browser)", "Ctrl+Shift+Space"), ("read_aloud", "Read this page out loud", ""),
    ("help", "Help & features guide", "F1"), ("tour", "Welcome tour", ""),
]
for _id, _label, _key in KEY_COMMANDS:
    opt(f"key_{_id}", "Keyboard shortcuts", _label, "key", _key, "keys")

OPTION_BY_KEY = {o["key"]: o for o in OPTIONS}
CATEGORIES = []
for _o in OPTIONS:
    if _o["cat"] not in CATEGORIES:
        CATEGORIES.append(_o["cat"])

# Settings that are not in the Customize list but still saved
EXTRA_DEFAULTS = {"zoom": {}, "focus_until": 0, "custom_widgets": [], "site_css": {},
                  "focus_sites": ["youtube.com", "reddit.com", "tiktok.com", "instagram.com", "x.com", "twitter.com",
                                  "twitch.tv", "netflix.com", "crunchyroll.com", "facebook.com"]}
DEFAULT_SETTINGS = dict(EXTRA_DEFAULTS, **{o["key"]: o["default"] for o in OPTIONS})


def valid_value(o, v):
    """Is v an acceptable value for option o?"""
    k = o["kind"]
    if k == "bool":
        return isinstance(v, bool)
    if k == "int":
        return isinstance(v, int) and not isinstance(v, bool) and o.get("min", -10**9) <= v <= o.get("max", 10**9)
    if k == "choice":
        return v in o["choices"]
    return isinstance(v, str)


# ---- style packs: one click changes many options --------------------------------------
STYLE_PACKS = {
    "Nova Classic": {},
    "Cyberpunk": {"theme": "Neon Purple", "base_palette": "Midnight", "wp_type": "Synthwave grid", "wp_color_mode": "Accent",
                  "wg_style": "Neon", "tab_shape": "Slanted glow", "sp_logo_style": "Gradient", "sp_logo_font": "Bahnschrift",
                  "ui_font": "Bahnschrift", "sp_search_style": "Square", "sp_tile_style": "Outline", "wp_vignette": True},
    "Hacker": {"theme": "Cyber Green", "base_palette": "OLED Black", "wp_type": "Matrix rain", "wg_style": "Outline",
               "ui_font": "Cascadia Code", "sp_font": "Cascadia Code", "sp_logo_font": "Cascadia Code", "sp_logo_style": "Glow",
               "tab_shape": "Square", "address_style": "Square", "sp_search_style": "Square", "corner_radius": 0,
               "wg_radius": 0, "sp_tile_shape": "Square", "w_clock_style": "Binary"},
    "Anime Night": {"theme": "Sakura Pink", "base_palette": "Plum", "wp_type": "Sakura petals", "wp_color_mode": "Accent",
                    "wg_style": "Glass", "sp_logo_style": "Gradient", "tab_shape": "Pill", "sp_search_style": "Pill",
                    "sp_tile_shape": "Circle", "wp_dim": 10},
    "Deep Space": {"theme": "Ice Cyan", "base_palette": "Midnight", "wp_type": "Nebula", "wg_style": "Glass",
                   "sp_logo_style": "Glow", "w_clock_style": "Big", "wp_vignette": True},
    "Hyperdrive": {"theme": "Nova Blue", "base_palette": "OLED Black", "wp_type": "Hyperspace", "wg_style": "Minimal",
                   "sp_logo_style": "Outline", "w_clock_style": "Minimal"},
    "Cozy Cabin": {"theme": "Sunset Orange", "base_palette": "Mocha", "wp_type": "Fireflies", "ui_font": "Georgia",
                   "sp_font": "Georgia", "sp_logo_font": "Georgia", "sp_logo_style": "Plain", "wg_style": "Solid",
                   "w_clock_style": "Analog", "tab_shape": "Rounded", "reader_bg": "Sepia"},
    "Ocean": {"theme": "Ice Cyan", "base_palette": "Ocean", "wp_type": "Waves", "wg_style": "Glass", "sp_logo_style": "Gradient"},
    "Winter": {"theme": "Lavender", "base_palette": "Slate", "wp_type": "Snow", "wg_style": "Glass", "sp_logo_style": "Glow"},
    "Rainy Day": {"theme": "Ice Cyan", "base_palette": "Slate", "wp_type": "Rain", "wg_style": "Solid", "wp_dim": 30},
    "Minimal": {"theme": "Nova Blue", "base_palette": "Graphite", "wp_type": "Solid colour", "wp_color": "#15161b",
                "wg_style": "Minimal", "sp_show_greeting": False, "sp_show_tip": False, "sp_logo_style": "Plain",
                "w_weather_pos": "Hidden", "w_spark_pos": "Hidden", "w_todo_pos": "Hidden", "tab_shape": "Underline",
                "address_style": "Underline", "sp_search_style": "Underline", "sp_tile_style": "Minimal", "wg_draggable": False},
    "OLED Crimson": {"theme": "Crimson", "base_palette": "OLED Black", "wp_type": "Constellation", "wg_style": "Outline",
                     "tab_shape": "Underline", "wp_dim": 0},
    "Golden Hour": {"theme": "Gold", "base_palette": "Mocha", "wp_type": "Time-of-day sky", "wg_style": "Glass",
                    "sp_logo_style": "Gradient", "w_clock_style": "Big"},
}

# ---- colours ---------------------------------------------------------------------------
THEMES = {
    "Nova Blue":     "#6c8cff", "Neon Purple": "#a46cff", "Cyber Green": "#2fd38a", "Sunset Orange": "#ff8a4c",
    "Sakura Pink":   "#ff6fae", "Ice Cyan":    "#36c9e6", "Crimson":     "#ff4d5e", "Gold":          "#f2b33d",
    "Mint":          "#4fe0c0", "Lavender":    "#b9a4ff",
}
# Every style in this file is written in the Graphite palette; themed() swaps in the chosen one.
PALETTE_KEYS = ["#1e1f24", "#26282e", "#2b2d34", "#3a3d46", "#33353d", "#e6e6e6", "#9a9ca6", "#17181d",
                "#15161b", "#23252c", "#2c2e36", "#31343d", "#262a3a", "#8a8d98", "#b8b8b8", "#2c3550"]
PALETTES = {  # bar, panel, field, border, hover, text, dim, deep, page, card, line, tilehover, glowtop, dim2, tabtext, bubble
    "Graphite":      ["#1e1f24", "#26282e", "#2b2d34", "#3a3d46", "#33353d", "#e6e6e6", "#9a9ca6", "#17181d", "#15161b", "#23252c", "#2c2e36", "#31343d", "#262a3a", "#8a8d98", "#b8b8b8", "#2c3550"],
    "Midnight":      ["#141621", "#1b1e2b", "#212536", "#2f3448", "#283046", "#e4e7f2", "#8f96ad", "#10121b", "#0d0f17", "#1a1d2b", "#232838", "#262c40", "#1d2340", "#7f869c", "#aab0c4", "#26305a"],
    "OLED Black":    ["#000000", "#0b0b0d", "#121214", "#26262b", "#1a1a1f", "#f0f0f0", "#8b8b93", "#050506", "#000000", "#0e0e10", "#1a1a1e", "#18181c", "#0a0a12", "#77777f", "#a8a8b0", "#1c2340"],
    "Navy":          ["#121a2e", "#18223a", "#1d2943", "#2c3a5c", "#24314f", "#e3e9f7", "#8d9bbb", "#0f1627", "#0b1220", "#172038", "#203050", "#24345a", "#16244a", "#7d8bab", "#a8b4cf", "#25386b"],
    "Plum":          ["#1f1622", "#28202d", "#2e2534", "#433549", "#382d3e", "#f0e6f2", "#a596aa", "#1a121c", "#150e17", "#251c29", "#33283a", "#3a2d40", "#2d1d34", "#958499", "#c3b4c7", "#43284f"],
    "Forest":        ["#141c18", "#1b2520", "#202c26", "#2f3f36", "#28362f", "#e3efe7", "#8ea596", "#101714", "#0c1310", "#18221d", "#22302a", "#26372e", "#16281f", "#7f9586", "#a9bdb0", "#1f3d30"],
    "Mocha":         ["#1f1a17", "#29221e", "#302824", "#463a33", "#3a302a", "#f2e9e3", "#a99a90", "#1a1512", "#15110e", "#26201c", "#352c27", "#3b312b", "#2d221b", "#998a80", "#c8b8ad", "#453326"],
    "Slate":         ["#1c2127", "#242a31", "#2a3139", "#3a434e", "#323a44", "#e6ebf0", "#97a2ae", "#171b20", "#13171b", "#21272e", "#2c333c", "#323b45", "#222a35", "#87929e", "#b3bdc8", "#2c3a52"],
    "Crimson Night": ["#1d1416", "#261b1e", "#2c2023", "#432f34", "#38282c", "#f2e6e8", "#a8959a", "#181012", "#130c0e", "#231a1c", "#33262a", "#3a2a2e", "#2d1a1f", "#98858a", "#c6b3b7", "#4a2530"],
    "Ocean":         ["#0f1d22", "#15262c", "#1a2d34", "#28434c", "#213941", "#e1f1f4", "#8aa8b0", "#0c181c", "#091317", "#132228", "#1d333b", "#213a43", "#123038", "#7b989f", "#a6c3c9", "#174452"],
}
CURRENT_THEME = {"accent": "#6c8cff", "palette": "Graphite"}


def mix(hex1, hex2, t):
    a = [int(hex1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(hex2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b))


def set_theme_from(settings):
    accent = settings.get("custom_accent", "#6c8cff") if settings.get("theme") == "Custom" else THEMES.get(settings.get("theme"), "#6c8cff")
    if not (isinstance(accent, str) and len(accent) == 7 and accent.startswith("#")):
        accent = "#6c8cff"
    CURRENT_THEME["accent"] = accent.lower()
    CURRENT_THEME["palette"] = settings.get("base_palette") if settings.get("base_palette") in PALETTES else "Graphite"


def theme_colors():
    a = CURRENT_THEME["accent"]
    return a, mix(a, "#ffffff", .28), mix(a, "#ffffff", .14)


def themed(text: str) -> str:
    """Swap the Nova Blue accent + Graphite palette written in a style for the chosen ones."""
    accent, light, hover = theme_colors()
    table = {"#6c8cff": accent, "#8fa6ff": light, "#7f9bff": hover}
    pal = PALETTES[CURRENT_THEME["palette"]]
    if CURRENT_THEME["palette"] != "Graphite":
        table.update({k: v for k, v in zip(PALETTE_KEYS, pal)})
    return re.sub(r"#[0-9a-fA-F]{6}\b", lambda m: table.get(m.group(0).lower(), m.group(0)), text)


def pal(name):
    """One colour of the current palette by role name."""
    roles = ["bar", "panel", "field", "border", "hover", "text", "dim", "deep", "page", "card", "line", "tilehover",
             "glowtop", "dim2", "tabtext", "bubble"]
    return PALETTES[CURRENT_THEME["palette"]][roles.index(name)]


USER_AGENTS = {
    "Chrome on Windows": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Edge on Windows": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0",
    "Firefox on Windows": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
    "Safari on Mac": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15",
    "Chrome on Android": "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36",
    "Safari on iPhone": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1",
}


def chrome_extra_style(s):
    """Stylesheet rules added on top of DARK_STYLE for the Appearance options."""
    r = int(s["corner_radius"])
    fs = int(s["ui_font_size"])
    accent, light, _ = theme_colors()
    pad = {"Compact": (3, 10), "Normal": (6, 14), "Roomy": (10, 18)}[s["tab_height"]]
    bottom = s["tab_position"] == "Bottom"
    tr = 8
    shape = s["tab_shape"]
    if shape == "Pill":
        tab_corners = "border-radius: 14px; margin: 3px 2px;"
    elif shape == "Square":
        tab_corners = "border-radius: 0px;"
    elif shape == "Underline":
        tab_corners = "border-radius: 0px; background: transparent;"
    elif shape == "Slanted glow":
        tab_corners = (f"border-radius: 0px; border-top-left-radius: 12px; border-bottom-right-radius: 12px;"
                       if not bottom else "border-radius: 0px; border-bottom-left-radius: 12px; border-top-right-radius: 12px;")
    else:
        tab_corners = (f"border-radius: 0px; border-bottom-left-radius: {tr}px; border-bottom-right-radius: {tr}px;" if bottom
                       else f"border-radius: 0px; border-top-left-radius: {tr}px; border-top-right-radius: {tr}px;")
    edge = "border-top" if bottom else "border-bottom"
    selected = f"{edge}: 2px solid {accent};" if s["tab_glow"] or shape == "Underline" else f"{edge}: none;"
    if shape == "Slanted glow":
        selected += f" background: {mix(pal('hover'), accent, .18)};"
    addr = {"Rounded": f"border-radius: {r}px;", "Pill": "border-radius: 14px;", "Square": "border-radius: 0px;",
            "Underline": f"border-radius: 0px; border: none; border-bottom: 2px solid {pal('border')}; background: transparent;"}[s["address_style"]]
    scroll = {"Slim": f"QScrollBar:vertical {{ width: 8px; background: transparent; }} QScrollBar::handle:vertical {{ background: {pal('border')}; border-radius: 4px; min-height: 30px; }}"
              f" QScrollBar:horizontal {{ height: 8px; background: transparent; }} QScrollBar::handle:horizontal {{ background: {pal('border')}; border-radius: 4px; min-width: 30px; }}"
              " QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }",
              "Hidden": "QScrollBar { width: 0px; height: 0px; }", "Standard": ""}[s["scrollbar_style"]]
    font = s["ui_font"].replace('"', "")
    return f"""
* {{ font-family: "{font}"; font-size: {fs}px; }}
QToolBar {{ spacing: {int(s['toolbar_spacing'])}px; }}
QToolButton {{ font-size: {int(s['button_size'])}px; border-radius: {r}px; }}
QLineEdit {{ border-radius: {r}px; }}
QMainWindow QToolBar QLineEdit {{ {addr} font-size: {int(s['address_font_size'])}px; }}
QTabBar::tab {{ {tab_corners} padding: {pad[0]}px {pad[1]}px; max-width: {int(s['tab_max_width'])}px; }}
QTabBar::tab:selected {{ {selected} }}
QMenu {{ border-radius: {int(s['menu_roundness'])}px; }}
QProgressBar {{ max-height: {int(s['loading_bar_size'])}px; }}
{scroll}
"""


# ---------- start page (live wallpapers + widgets) ----------
START_HTML = r"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="nova-page" content="start"><title>New Tab</title>
<style>
:root { --accent:#6c8cff; --accent-l:#8fa6ff; --text:#e6e6e6; --dim:#9a9ca6; --bg:#15161b; --card:35,37,44;
        --wg-op:.7; --wg-r:16px; --wg-blur:12px; --wg-scale:1; --font:"Segoe UI",sans-serif; }
* { box-sizing: border-box; }
html, body { margin: 0; height: 100%; overflow: hidden; }
body { background: var(--bg); color: var(--text); font-family: var(--font); }
#wp, #wpv, #wpimg, #wpimg2, #dim { position: fixed; inset: 0; width: 100%; height: 100%; z-index: 0; }
#wpv, #wpimg, #wpimg2 { object-fit: cover; display: none; }
#wpimg, #wpimg2 { background-size: cover; background-position: center; transition: opacity 1.5s; }
#dim { pointer-events: none; z-index: 1; }
#root { position: relative; z-index: 2; height: 100%; display: grid; grid-template-columns: minmax(0,330px) 1fr minmax(0,330px);
        gap: 24px; padding: 28px; overflow-y: auto; }
.zone { display: flex; flex-direction: column; gap: 16px; min-width: 0; }
#zone-center { align-items: center; padding-top: 9vh; }
body.layout-top #zone-center { padding-top: 2vh; }
body.layout-left #zone-center { align-items: flex-start; }
#logo { margin: 0; letter-spacing: .12em; line-height: 1.1; text-align: center; font-weight: 700; }
#logo.glow { color: var(--accent-l); text-shadow: 0 0 28px color-mix(in srgb, var(--accent) 45%, transparent); }
#logo.gradient { background: linear-gradient(90deg, var(--accent), var(--accent-l), #fff, var(--accent));
                 background-size: 300% 100%; -webkit-background-clip: text; background-clip: text; color: transparent;
                 animation: shine 6s linear infinite; }
#logo.outline { color: transparent; -webkit-text-stroke: 2px var(--accent-l); }
#logo.plain { color: var(--text); }
@keyframes shine { to { background-position: 300% 0; } }
#greet { color: var(--dim); font-size: 17px; text-align: center; }
#search { width: min(var(--sw,600px), 92%); }
#search input { width: 100%; padding: 14px 22px; border: 1px solid rgba(255,255,255,.12); outline: none; font: inherit; font-size: 16px;
                color: #fff; background: rgba(var(--card), .78); backdrop-filter: blur(10px); }
#search.pill input { border-radius: 30px; } #search.rounded input { border-radius: 12px; } #search.square input { border-radius: 0; }
#search.underline input { border-radius: 0; background: transparent; border: none; border-bottom: 2px solid var(--accent); backdrop-filter: none; }
#search input:focus { border-color: var(--accent); }
#search.glow input:focus { box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent) 30%, transparent), 0 0 30px color-mix(in srgb, var(--accent) 35%, transparent); }
#tiles { display: flex; flex-wrap: wrap; gap: 14px; justify-content: center; width: min(820px, 96%); }
.tile { width: var(--ts,110px); }
.tile { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 8px; height: var(--ts,110px);
        padding: 10px 6px; color: var(--text); text-decoration: none; font-size: 12px; text-align: center; transition: transform .15s, background .15s; }
.tile img { width: 34%; max-width: 40px; aspect-ratio: 1; }
.tile span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; width: 100%; }
.tile:hover { transform: translateY(-3px); }
.tiles-glass .tile { background: rgba(var(--card), .55); backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,.08); }
.tiles-solid .tile { background: rgb(var(--card)); }
.tiles-outline .tile { border: 1px solid color-mix(in srgb, var(--accent) 60%, transparent); }
.tiles-minimal .tile:hover { background: rgba(255,255,255,.06); }
.tiles-rounded .tile { border-radius: 16px; } .tiles-square .tile { border-radius: 2px; } .tiles-circle .tile { border-radius: 50%; }
.tiles-nolabel .tile span { display: none; }
/* widgets */
.wg { position: relative; padding: 14px 16px; border-radius: var(--wg-r); font-size: calc(14px * var(--wg-scale)); color: var(--text);
      width: 100%; max-width: 560px; }
#zone-center .wg { width: min(560px, 92%); }
.wg-glass .wg { background: rgba(var(--card), var(--wg-op)); backdrop-filter: blur(var(--wg-blur)); border: 1px solid rgba(255,255,255,.08); }
.wg-solid .wg { background: rgba(var(--card), var(--wg-op)); }
.wg-outline .wg { border: 1px solid color-mix(in srgb, var(--accent) 60%, transparent); background: rgba(0,0,0,calc(var(--wg-op) * .4)); }
.wg-neon .wg { background: rgba(10,10,18,var(--wg-op)); border: 1px solid var(--accent); box-shadow: 0 0 14px color-mix(in srgb, var(--accent) 50%, transparent), inset 0 0 14px color-mix(in srgb, var(--accent) 18%, transparent); }
.wg-minimal .wg { background: transparent; padding: 6px 4px; }
.wg-shadow .wg { box-shadow: 0 10px 30px rgba(0,0,0,.35); }
.wg-animate .wg { animation: rise .5s ease both; }
@keyframes rise { from { opacity: 0; transform: translateY(10px); } }
.wg h4 { margin: 0 0 8px; font-size: .78em; letter-spacing: .14em; text-transform: uppercase; color: var(--dim); font-weight: 600; }
.wg-accent-titles .wg h4 { color: var(--accent-l); }
.wg button, .wg input, .wg textarea, .wg select { font: inherit; color: var(--text); background: rgba(255,255,255,.07);
      border: 1px solid rgba(255,255,255,.12); border-radius: 8px; padding: 5px 9px; outline: none; }
.wg button { cursor: pointer; } .wg button:hover { border-color: var(--accent); }
.wg input:focus, .wg textarea:focus { border-color: var(--accent); }
.wg a { color: var(--accent-l); text-decoration: none; } .wg a:hover { text-decoration: underline; }
.row { display: flex; gap: 8px; align-items: center; }
.muted { color: var(--dim); font-size: .86em; }
.big { font-size: 2.4em; font-weight: 300; letter-spacing: .03em; }
.list { list-style: none; margin: 0; padding: 0; } .list li { padding: 4px 0; display: flex; gap: 8px; align-items: center; overflow: hidden; }
.list li span.t { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.done span.t { text-decoration: line-through; color: var(--dim); }
.x { background: none!important; border: none!important; color: var(--dim)!important; padding: 0 4px!important; }
textarea { width: 100%; min-height: 110px; resize: vertical; }
/* clock */
.clock-digital .time { font-size: calc(3.2em); font-weight: 300; text-align: center; letter-spacing: .04em; }
.clock-big .time { font-size: 6.5em; font-weight: 200; text-align: center; line-height: 1; }
.clock-minimal .time { font-size: 2em; font-weight: 300; text-align: center; }
.clock-date { text-align: center; color: var(--dim); }
.clock-wg { text-align: center; }
.binary { display: inline-grid; grid-auto-flow: column; gap: 10px; margin: 6px auto; }
.binary .col { display: grid; gap: 6px; } .binary i { width: 14px; height: 14px; border-radius: 50%; background: rgba(255,255,255,.12); display: block; }
.binary i.on { background: var(--accent); box-shadow: 0 0 8px var(--accent); }
/* calendar */
.cal { display: grid; grid-template-columns: repeat(7, 1fr); gap: 3px; text-align: center; font-size: .9em; }
.cal b { color: var(--dim); font-weight: 500; font-size: .8em; } .cal span { padding: 4px 0; border-radius: 6px; }
.cal .today { background: var(--accent); color: #fff; } .cal .other { opacity: .3; }
.bar { height: 8px; border-radius: 4px; background: var(--accent); }
.wx-days { display: flex; gap: 10px; margin-top: 8px; } .wx-days div { flex: 1; text-align: center; font-size: .85em; }
iframe.embed { width: 100%; height: 260px; border: none; border-radius: 10px; background: #fff; }
iframe.html { width: 100%; height: 200px; border: none; background: transparent; }
/* corner buttons + edit mode */
#corner { position: fixed; right: 14px; bottom: 12px; z-index: 5; display: flex; gap: 8px; }
#corner a, #corner button { font: 12px var(--font); color: var(--dim); background: rgba(var(--card), .6); border: 1px solid rgba(255,255,255,.1);
       border-radius: 8px; padding: 6px 10px; text-decoration: none; cursor: pointer; backdrop-filter: blur(8px); }
#corner a:hover, #corner button:hover { color: #fff; border-color: var(--accent); }
#tip { position: fixed; left: 50%; transform: translateX(-50%); bottom: 14px; color: var(--dim); font-size: 12px; z-index: 3; opacity: .8; }
kbd { background: rgba(255,255,255,.08); border: 1px solid rgba(255,255,255,.15); border-radius: 4px; padding: 1px 6px; }
body.editing .wg { outline: 2px dashed var(--accent); cursor: move; user-select: none; }
body.editing .wg * { pointer-events: none; }
</style></head>
<body>
<canvas id="wp"></canvas><video id="wpv" autoplay muted loop playsinline></video><div id="wpimg"></div><div id="wpimg2"></div><div id="dim"></div>
<div id="root"><div class="zone" id="zone-left"></div><div class="zone" id="zone-center"></div><div class="zone" id="zone-right"></div></div>
<div id="tip"></div>
<div id="corner"><button id="editbtn" title="Drag widgets around">✎ Layout</button><button id="resetbtn" style="display:none">↺ Reset layout</button>
<a href="nova://customize" title="Customize everything">⚙ Customize</a></div>
<script>window.N = /*NOVA_CONFIG*/{};</script>
<script>
(function () {
"use strict";
var N = window.N || {};
var $ = function (id) { return document.getElementById(id); };
function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
function store(key, val) { try { if (val === undefined) return JSON.parse(localStorage.getItem("nova-" + key) || "null"); localStorage.setItem("nova-" + key, JSON.stringify(val)); } catch (e) { return null; } }
var root = document.documentElement.style;
function setVar(k, v) { root.setProperty(k, v); }
function hexRgb(h) { h = (h || "#232329").replace("#", ""); if (h.length === 3) h = h.split("").map(function (c) { return c + c; }).join("");
  var n = parseInt(h, 16); return [(n >> 16) & 255, (n >> 8) & 255, n & 255]; }

/* ---------------- theme ---------------- */
setVar("--accent", N.accent || "#6c8cff"); setVar("--accent-l", N.accent_light || "#8fa6ff");
setVar("--text", N.text || "#e6e6e6"); setVar("--dim", N.dim || "#9a9ca6"); setVar("--bg", N.bg || "#15161b");
setVar("--card", hexRgb(N.card).join(","));
setVar("--font", N.font || '"Segoe UI",sans-serif');
var WG = N.wg || {};
setVar("--wg-op", ((WG.opacity == null ? 70 : WG.opacity) / 100).toString());
setVar("--wg-r", (WG.radius == null ? 16 : WG.radius) + "px");
setVar("--wg-blur", (WG.blur == null ? 12 : WG.blur) + "px");
setVar("--wg-scale", ((WG.scale || 100) / 100).toString());
document.body.classList.add("wg-" + (WG.style || "glass").toLowerCase());
if (WG.shadow) document.body.classList.add("wg-shadow");
if (WG.animate !== false) document.body.classList.add("wg-animate");
if (WG.accent_titles) document.body.classList.add("wg-accent-titles");
document.body.classList.add("layout-" + (N.layout || "centered").toLowerCase());

/* ---------------- center column ---------------- */
var center = $("zone-center");
var L = N.logo || {};
if (L.show !== false) {
  var logo = el("h1", (L.style || "glow").toLowerCase(), L.text == null ? "NOVA" : L.text);
  logo.id = "logo"; logo.style.fontSize = (L.size || 56) + "px"; if (L.font) logo.style.fontFamily = L.font;
  center.appendChild(logo);
}
var G = N.greeting || {};
if (G.show !== false) {
  var g = el("div"); g.id = "greet"; center.appendChild(g);
  var h = new Date().getHours();
  var base = G.mode === "Custom" && G.custom ? G.custom :
    (h < 5 ? "Up late" : h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening");
  g.textContent = base + (G.name && !(G.mode === "Custom" && G.custom) ? ", " + G.name : "") + (G.mode === "Custom" && G.custom ? "" : (h < 5 ? "?" : ""));
}
var S = N.search || {};
if (S.show !== false) {
  var f = el("form"); f.id = "search"; f.className = (S.style || "pill").toLowerCase() + (S.glow !== false ? " glow" : "");
  setVar("--sw", (S.width || 600) + "px");
  var inp = el("input"); inp.name = "q"; inp.autocomplete = "off"; inp.placeholder = S.placeholder || "Search the web";
  if (S.autofocus !== false) inp.autofocus = true;
  f.appendChild(inp); center.appendChild(f);
  var searchForm = f;
  f.addEventListener("submit", function (e) { e.preventDefault(); var q = inp.value.trim(); if (!q) return;
    var looksUrl = /^[^\s]+\.[^\s]{2,}$/.test(q) || /^https?:\/\//i.test(q);
    location.href = looksUrl ? (/^https?:\/\//i.test(q) ? q : "https://" + q) : (S.url || "https://duckduckgo.com/?q=%s").replace("%s", encodeURIComponent(q)); });
}

/* ---------------- widgets ---------------- */
var zones = { Left: $("zone-left"), Center: center, Right: $("zone-right") };
var layout = store("layout") || {};
var tilesHost = null;
function card(id, title, zone) {
  var c = el("div", "wg"); c.dataset.id = id;
  if (title) c.appendChild(el("h4", null, title));
  (zones[zone] || zones.Right).appendChild(c);
  var p = layout[id]; if (p) c.style.transform = "translate(" + p.x + "px," + p.y + "px)";
  return c;
}
function pad(n) { return (n < 10 ? "0" : "") + n; }
function fmtTime(d, h24, secs, tz) {
  var o = { hour: "numeric", minute: "2-digit", hour12: !h24 }; if (secs) o.second = "2-digit"; if (tz) o.timeZone = tz;
  try { return d.toLocaleTimeString([], o); } catch (e) { return d.toLocaleTimeString(); }
}
function fmtDate(d, style) {
  if (style === "2026-11-04") return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate());
  if (style === "11/04/2026") return pad(d.getMonth() + 1) + "/" + pad(d.getDate()) + "/" + d.getFullYear();
  if (style === "04/11/2026") return pad(d.getDate()) + "/" + pad(d.getMonth() + 1) + "/" + d.getFullYear();
  if (style === "Nov 4") return d.toLocaleDateString([], { month: "short", day: "numeric" });
  return d.toLocaleDateString([], { weekday: "long", month: "long", day: "numeric" });
}
var tickers = [];
var W = {};

W.clock = function (o, c) {
  c.classList.add("clock-wg"); var style = (o.style || "Digital").toLowerCase(); c.classList.add("clock-" + style);
  var t = el("div", "time"), d = el("div", "clock-date"), cv = null, bin = null;
  if (style === "analog") { cv = el("canvas"); cv.width = cv.height = 170; cv.style.display = "block"; cv.style.margin = "0 auto"; c.appendChild(cv); }
  else if (style === "binary") { bin = el("div", "binary"); c.appendChild(bin); c.appendChild(t); t.style.fontSize = "1.2em"; }
  else c.appendChild(t);
  if (o.date !== false) c.appendChild(d);
  function draw() {
    var now = new Date();
    t.textContent = fmtTime(now, o.h24, o.seconds || style === "binary");
    d.textContent = fmtDate(now, o.date_format);
    if (cv) {
      var x = cv.getContext("2d"), r = 80; x.clearRect(0, 0, 170, 170); x.save(); x.translate(85, 85);
      x.strokeStyle = "rgba(255,255,255,.18)"; x.lineWidth = 2; x.beginPath(); x.arc(0, 0, r, 0, 7); x.stroke();
      for (var i = 0; i < 12; i++) { x.save(); x.rotate(i * Math.PI / 6); x.fillStyle = i % 3 ? "rgba(255,255,255,.35)" : N.accent;
        x.fillRect(-1.5, -r + 5, 3, i % 3 ? 7 : 12); x.restore(); }
      var hh = now.getHours() % 12, mm = now.getMinutes(), ss = now.getSeconds();
      function hand(a, len, w, col) { x.save(); x.rotate(a); x.strokeStyle = col; x.lineWidth = w; x.lineCap = "round";
        x.beginPath(); x.moveTo(0, 10); x.lineTo(0, -len); x.stroke(); x.restore(); }
      hand((hh + mm / 60) * Math.PI / 6, 42, 5, N.text || "#fff"); hand((mm + ss / 60) * Math.PI / 30, 62, 3, N.text || "#fff");
      if (o.seconds !== false) hand(ss * Math.PI / 30, 70, 1.5, N.accent);
      x.fillStyle = N.accent; x.beginPath(); x.arc(0, 0, 4, 0, 7); x.fill(); x.restore();
    }
    if (bin) {
      bin.innerHTML = ""; var parts = [now.getHours(), now.getMinutes(), now.getSeconds()];
      parts.forEach(function (v) { [Math.floor(v / 10), v % 10].forEach(function (dgt) { var col = el("div", "col");
        for (var b = 3; b >= 0; b--) { var i = el("i"); if (dgt & (1 << b)) i.className = "on"; col.appendChild(i); } bin.appendChild(col); }); });
    }
  }
  draw(); tickers.push(draw);
};

var WX = { 0: ["☀️", "Clear"], 1: ["🌤️", "Mostly clear"], 2: ["⛅", "Partly cloudy"], 3: ["☁️", "Cloudy"], 45: ["🌫️", "Fog"], 48: ["🌫️", "Fog"],
  51: ["🌦️", "Drizzle"], 53: ["🌦️", "Drizzle"], 55: ["🌦️", "Drizzle"], 61: ["🌧️", "Rain"], 63: ["🌧️", "Rain"], 65: ["🌧️", "Heavy rain"],
  66: ["🌧️", "Freezing rain"], 67: ["🌧️", "Freezing rain"], 71: ["🌨️", "Snow"], 73: ["🌨️", "Snow"], 75: ["❄️", "Heavy snow"], 77: ["🌨️", "Snow grains"],
  80: ["🌦️", "Showers"], 81: ["🌧️", "Showers"], 82: ["⛈️", "Heavy showers"], 85: ["🌨️", "Snow showers"], 86: ["🌨️", "Snow showers"],
  95: ["⛈️", "Thunderstorm"], 96: ["⛈️", "Thunderstorm"], 99: ["⛈️", "Thunderstorm"] };
W.weather = function (o, c) {
  var body = el("div", null, o.city ? "Loading weather…" : "Set your city in ⚙ Customize → Widgets."); c.appendChild(body);
  if (!o.city) return;
  function show(data) {
    body.innerHTML = ""; var cur = data.current || {}, w = WX[cur.weather_code] || ["🌡️", ""];
    var top = el("div", "row"); top.appendChild(el("div", "big", w[0] + " " + Math.round(cur.temperature_2m) + "°"));
    var side = el("div"); side.appendChild(el("div", null, w[1])); side.appendChild(el("div", "muted", data.place + " · wind " + Math.round(cur.wind_speed_10m)));
    top.appendChild(side); body.appendChild(top);
    var days = Math.min(o.days == null ? 3 : o.days, 7);
    if (days > 0 && data.daily) {
      var row = el("div", "wx-days");
      for (var i = 0; i < days && i < data.daily.time.length; i++) {
        var dd = el("div"), dt = new Date(data.daily.time[i] + "T12:00");
        dd.appendChild(el("div", "muted", i === 0 ? "Today" : dt.toLocaleDateString([], { weekday: "short" })));
        dd.appendChild(el("div", null, (WX[data.daily.weather_code[i]] || ["🌡️"])[0]));
        dd.appendChild(el("div", null, Math.round(data.daily.temperature_2m_max[i]) + "° / " + Math.round(data.daily.temperature_2m_min[i]) + "°"));
        row.appendChild(dd);
      }
      body.appendChild(row);
    }
  }
  // The browser fetches the weather (local pages aren't allowed online) and hands it over here.
  function apply(w) {
    var same = function (a, b) { return String(a || "").trim().toLowerCase() === String(b || "").trim().toLowerCase(); };
    if (!w || !same(w.city, o.city) || w.units !== o.units) return;
    if (w.data) show(w.data); else if (w.error) body.textContent = "Weather unavailable (" + w.error + ").";
  }
  window.novaWeather = apply;
  apply(N.weather);
};

W.todo = function (o, c) {
  var items = store("todo") || [], ul = el("ul", "list"), form = el("form", "row"), inp = el("input");
  inp.placeholder = "Add a task…"; inp.style.flex = "1"; form.appendChild(inp); form.appendChild(el("button", null, "+"));
  function render() {
    ul.innerHTML = "";
    items.forEach(function (it, i) {
      var li = el("li", it.done ? "done" : ""), cb = el("input"); cb.type = "checkbox"; cb.checked = !!it.done;
      cb.onchange = function () { it.done = cb.checked; store("todo", items); render(); };
      var x = el("button", "x", "✕"); x.onclick = function () { items.splice(i, 1); store("todo", items); render(); };
      li.appendChild(cb); li.appendChild(el("span", "t", it.text)); li.appendChild(x); ul.appendChild(li);
    });
    if (!items.length) ul.appendChild(el("li", "muted", "Nothing to do. Nice."));
  }
  form.onsubmit = function (e) { e.preventDefault(); var v = inp.value.trim(); if (!v) return; items.push({ text: v }); inp.value = ""; store("todo", items); render(); };
  c.appendChild(ul); c.appendChild(form); render();
};

W.notes = function (o, c) {
  var ta = el("textarea"); ta.placeholder = "Type anything. It saves itself."; ta.value = store("notes") || "";
  ta.oninput = function () { store("notes", ta.value); }; c.appendChild(ta);
};

W.pomodoro = function (o, c) {
  var work = (o.work || 25) * 60, brk = (o.brk || 5) * 60, mode = "Focus", left = work, run = false;
  var t = el("div", "big", ""), m = el("div", "muted", ""), row = el("div", "row"), b1 = el("button", null, "Start"), b2 = el("button", null, "Reset");
  t.style.textAlign = "center"; m.style.textAlign = "center"; row.style.justifyContent = "center";
  row.appendChild(b1); row.appendChild(b2); c.appendChild(t); c.appendChild(m); c.appendChild(row);
  function beep() { if (o.sound === false) return; try { var a = new AudioContext(), osc = a.createOscillator(), gn = a.createGain();
    osc.frequency.value = 880; osc.connect(gn); gn.connect(a.destination); gn.gain.setValueAtTime(.2, a.currentTime);
    gn.gain.exponentialRampToValueAtTime(.001, a.currentTime + .8); osc.start(); osc.stop(a.currentTime + .8); } catch (e) {} }
  function draw() { t.textContent = pad(Math.floor(left / 60)) + ":" + pad(left % 60); m.textContent = mode + (run ? "" : " · paused"); b1.textContent = run ? "Pause" : "Start"; }
  b1.onclick = function () { run = !run; draw(); };
  b2.onclick = function () { run = false; mode = "Focus"; left = work; draw(); };
  tickers.push(function () { if (!run) return; left--; if (left <= 0) { beep(); mode = mode === "Focus" ? "Break" : "Focus"; left = mode === "Focus" ? work : brk; } draw(); });
  draw();
};

W.countdown = function (o, c) {
  var t = el("div", "big"), m = el("div", "muted"); c.appendChild(t); c.appendChild(m);
  var target = new Date((o.date || "").replace(" ", "T"));
  function draw() {
    if (isNaN(target)) { t.textContent = "—"; m.textContent = "Set a date in ⚙ Customize (YYYY-MM-DD HH:MM)."; return; }
    var s = Math.max(0, Math.floor((target - new Date()) / 1000));
    t.textContent = Math.floor(s / 86400) + "d " + pad(Math.floor(s % 86400 / 3600)) + "h " + pad(Math.floor(s % 3600 / 60)) + "m " + pad(s % 60) + "s";
    m.textContent = s ? "until " + target.toLocaleString([], { dateStyle: "medium", timeStyle: "short" }) : "It's here! 🎉";
  }
  draw(); tickers.push(draw);
};

W.calendar = function (o, c) {
  var monOff = o.week_start === "Monday" ? 1 : 0, view = new Date(), head = el("div", "row"), grid = el("div", "cal");
  var prev = el("button", "x", "‹"), next = el("button", "x", "›"), title = el("div", null, ""); title.style.flex = "1"; title.style.textAlign = "center";
  head.appendChild(prev); head.appendChild(title); head.appendChild(next); c.appendChild(head); c.appendChild(grid);
  function draw() {
    grid.innerHTML = ""; var y = view.getFullYear(), mo = view.getMonth(), today = new Date();
    title.textContent = view.toLocaleDateString([], { month: "long", year: "numeric" });
    var names = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"]; for (var i = 0; i < 7; i++) grid.appendChild(el("b", null, names[(i + monOff) % 7]));
    var first = (new Date(y, mo, 1).getDay() - monOff + 7) % 7, start = new Date(y, mo, 1 - first);
    for (var k = 0; k < 42; k++) { var d = new Date(start); d.setDate(start.getDate() + k);
      var s = el("span", null, d.getDate()); if (d.getMonth() !== mo) s.className = "other";
      if (d.toDateString() === today.toDateString()) s.className = "today"; grid.appendChild(s); }
  }
  prev.onclick = function () { view.setMonth(view.getMonth() - 1); draw(); };
  next.onclick = function () { view.setMonth(view.getMonth() + 1); draw(); };
  draw();
};

var SPARKS = ["Small steps still move you forward.", "Build the thing you wish existed.", "Rest is part of the work.",
  "Today's bug is tomorrow's lesson.", "Curiosity beats talent that stays home.", "Ship it, then make it better.",
  "You're allowed to start messy.", "One focused hour beats a distracted day.", "Be the main character of your own project.",
  "Hard things get easier the second time.", "Ask the question. Someone else wanted to know too.", "Progress, not perfection.",
  "Drink some water. Seriously.", "The best time to save your work is now.", "Every expert was once confused by this too.",
  "Make it work, make it right, make it fast.", "Your future self is cheering for you.", "Break it into smaller pieces.",
  "Done is a feature.", "Stay curious, stay kind.", "Level up a little every day.", "Good ideas show up while you're already working.",
  "Comparison is a thief. Run your own race.", "Learn the rules, then remix them.", "Momentum is a superpower.",
  "Take the break before you need it.", "Fix one thing today.", "The plan can change. Keep the goal.", "You've solved harder things than this.",
  "Write it down so your brain can relax.", "Start with the fun part.", "Nobody builds a castle in a day. Lay a brick."];
W.spark = function (o, c) {
  var day = Math.floor((Date.now() - new Date(new Date().getFullYear(), 0, 0)) / 86400000);
  var line = el("div", null, SPARKS[day % SPARKS.length]); line.style.fontSize = "1.15em"; line.style.lineHeight = "1.5"; c.appendChild(line);
};

function linkList(c, items, empty) {
  var ul = el("ul", "list");
  (items || []).forEach(function (it) { var li = el("li"), a = el("a", "t", it.t || it.u); a.href = it.u; a.title = it.u;
    if (N.links_new_tab) a.target = "_blank"; li.appendChild(a); ul.appendChild(li); });
  if (!(items || []).length) ul.appendChild(el("li", "muted", empty));
  c.appendChild(ul);
}
W.history = function (o, c) { linkList(c, ((N.data || {}).history || []).slice(0, o.count || 8), "No history yet."); };
W.readlater = function (o, c) { linkList(c, (N.data || {}).readlater || [], "Nothing saved. Right-click a page → Save for later."); };
W.screentime = function (o, c) {
  var st = (N.data || {}).screentime || [], top = st.length ? st[0][1] : 1, total = 0;
  st.forEach(function (p) { total += p[1]; });
  c.appendChild(el("div", "big", Math.floor(total / 3600) + "h " + pad(Math.floor(total % 3600 / 60)) + "m"));
  st.slice(0, 5).forEach(function (p) { var r = el("div"); r.style.margin = "6px 0";
    var lab = el("div", "row"); lab.appendChild(el("span", "t", p[0])); var tm = el("span", "muted", Math.round(p[1] / 60) + "m"); lab.appendChild(tm);
    lab.firstChild.style.flex = "1"; var bar = el("div", "bar"); bar.style.width = Math.max(3, 100 * p[1] / top) + "%";
    r.appendChild(lab); r.appendChild(bar); c.appendChild(r); });
  if (!st.length) c.appendChild(el("div", "muted", "No browsing counted yet today."));
};
W.worldclock = function (o, c) {
  var zonesList = (o.zones || "Tokyo:Asia/Tokyo, London:Europe/London, New York:America/New_York").split(",").map(function (s) {
    var p = s.split(":"); return { l: (p[0] || "").trim(), z: (p.slice(1).join(":") || "").trim() }; }).filter(function (z) { return z.l && z.z; });
  var ul = el("ul", "list"), spans = [];
  zonesList.forEach(function (z) { var li = el("li"); li.appendChild(el("span", "t", z.l)); var s = el("span"); li.appendChild(s); ul.appendChild(li); spans.push([s, z.z]); });
  c.appendChild(ul);
  function draw() { var now = new Date(); spans.forEach(function (p) { p[0].textContent = fmtTime(now, o.h24, false, p[1]); }); }
  draw(); tickers.push(draw);
};
W.stopwatch = function (o, c) {
  var ms = 0, run = false, last = 0, t = el("div", "big"), row = el("div", "row"), b1 = el("button", null, "Start"), b2 = el("button", null, "Lap"), b3 = el("button", null, "Reset"), laps = el("ul", "list");
  t.style.textAlign = "center"; row.style.justifyContent = "center"; [b1, b2, b3].forEach(function (b) { row.appendChild(b); });
  c.appendChild(t); c.appendChild(row); c.appendChild(laps);
  function fmt(v) { var s = Math.floor(v / 1000); return pad(Math.floor(s / 60)) + ":" + pad(s % 60) + "." + Math.floor(v % 1000 / 100); }
  function frame(now) { if (!run) return; ms += now - last; last = now; t.textContent = fmt(ms); requestAnimationFrame(frame); }
  b1.onclick = function () { run = !run; b1.textContent = run ? "Stop" : "Start"; if (run) { last = performance.now(); requestAnimationFrame(frame); } };
  b2.onclick = function () { if (ms) laps.insertBefore(el("li", "muted", "Lap " + (laps.children.length + 1) + " · " + fmt(ms)), laps.firstChild); };
  b3.onclick = function () { run = false; ms = 0; b1.textContent = "Start"; laps.innerHTML = ""; t.textContent = fmt(0); };
  t.textContent = fmt(0);
};
W.asknova = function (o, c) {
  var f = el("form", "row"), inp = el("input"); inp.placeholder = "Ask Nova anything…"; inp.style.flex = "1";
  f.appendChild(inp); f.appendChild(el("button", null, "✦")); c.appendChild(f);
  f.onsubmit = function (e) { e.preventDefault(); var q = inp.value.trim(); if (q) location.href = "nova://ask?q=" + encodeURIComponent(q); };
};
W.custom = function (o, c) {
  var kind = o.kind || "Text";
  if (kind === "Links") {
    var items = (o.content || "").split("\n").map(function (line) { var p = line.split("|"); var u = (p[1] || p[0] || "").trim(); var t = p[1] ? p[0].trim() : u;
      if (u && !/^https?:\/\//i.test(u)) u = "https://" + u; return { t: t, u: u }; }).filter(function (x) { return x.u; });
    linkList(c, items, "Add links as lines like: YouTube | youtube.com");
  } else if (kind === "Web embed") {
    var fr = el("iframe", "embed"); fr.src = /^https?:\/\//i.test(o.content || "") ? o.content : "https://" + (o.content || "example.com");
    fr.setAttribute("sandbox", "allow-scripts allow-same-origin allow-forms allow-popups"); fr.style.height = (o.height || 260) + "px"; c.appendChild(fr);
  } else if (kind === "HTML") {
    var hf = el("iframe", "html"); hf.setAttribute("sandbox", "allow-scripts"); hf.style.height = (o.height || 200) + "px";
    hf.srcdoc = "<style>body{margin:0;color:" + (N.text || "#eee") + ";font-family:" + (N.font || "sans-serif") + "}</style>" + (o.content || ""); c.appendChild(hf);
  } else {
    var p = el("div", null, o.content || ""); p.style.whiteSpace = "pre-wrap"; p.style.lineHeight = "1.5"; c.appendChild(p);
  }
};

/* ---- Games & Following widgets (data comes from the browser) ---- */
var HUBW = [];
function hubD() { return N.hub || {}; }
function hubAgo(t) { var s = Date.now() / 1000 - t; if (s < 3600) return Math.max(1, Math.floor(s / 60)) + "m"; if (s < 86400) return Math.floor(s / 3600) + "h";
  return Math.floor(s / 86400) + "d"; }
function hubWhen(t) { var d = new Date(t * 1000), n = new Date(), tm = d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  if (d.toDateString() === n.toDateString()) return "Today " + tm;
  return d.toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" }) + " " + tm; }
function hubSide(g, tid) { var home = g.home && g.home.id === tid; return { us: home ? g.home : g.away, them: home ? g.away : g.home, at: home ? "vs" : "@" }; }
function hubLine(t) {
  var g = t.today, v;
  if (g && g.type === "game") { v = hubSide(g, t.team_id);
    if (g.state === "in") return { live: true, text: "LIVE " + v.us.score + "–" + v.them.score + " " + v.at + " " + v.them.abbr + " · " + g.detail, link: g.link };
    if (g.state === "post") return { text: (v.us.winner ? "W " : v.them.winner ? "L " : "") + v.us.score + "–" + v.them.score + " " + v.at + " " + v.them.abbr, link: g.link };
    return { text: hubWhen(g.time) + " " + v.at + " " + v.them.abbr, link: g.link }; }
  if (t.next && t.next.type === "game") { v = hubSide(t.next, t.team_id); return { text: "Next: " + hubWhen(t.next.time) + " " + v.at + " " + v.them.abbr, link: t.next.link }; }
  if (t.last && t.last.type === "game") { v = hubSide(t.last, t.team_id);
    return { text: "Last: " + (v.us.winner ? "W " : v.them.winner ? "L " : "") + v.us.score + "–" + v.them.score + " " + v.at + " " + v.them.abbr, link: t.last.link }; }
  return { text: t.record ? "Record " + t.record : "", link: "" };
}
function hubMore(c, label, href) { var a = el("a", "muted", label); a.href = href; a.style.display = "inline-block"; a.style.marginTop = "6px"; c.appendChild(a); }
W.scores = function (o, c) {
  var box = el("div"); c.appendChild(box);
  function draw() {
    box.innerHTML = ""; var d = hubD(), teams = d.teams || [];
    if (d.follow_on === false) { box.appendChild(el("div", "muted", "📣 Following is turned off.")); return; }
    if (!teams.length) { hubMore(box, "📣 Follow your teams →", "nova://following"); return; }
    var ul = el("ul", "list");
    teams.forEach(function (t) {
      var li = el("li"), im = el("img"), ln = hubLine(t), a = el("a", "t");
      im.src = /^https?:/.test(t.logo || "") ? t.logo : ""; im.width = im.height = 22; im.onerror = function () { im.style.visibility = "hidden"; };
      a.textContent = t.name; if (ln.link) { a.href = ln.link; if (N.links_new_tab) a.target = "_blank"; }
      var sub = el("span", ln.live ? "" : "muted", ln.text); if (ln.live) { sub.style.color = "#ff5a6a"; sub.style.fontWeight = "700"; }
      sub.style.fontSize = ".85em"; sub.style.whiteSpace = "nowrap";
      li.appendChild(im); li.appendChild(a); li.appendChild(sub); ul.appendChild(li);
    });
    box.appendChild(ul);
  }
  draw(); HUBW.push(draw);
};
function hubItems(o, c, key, offMsg, emptyMsg, more, moreHref) {
  var box = el("div"); c.appendChild(box);
  function draw() {
    box.innerHTML = ""; var d = hubD();
    if (d[key + "_off"]) { box.appendChild(el("div", "muted", offMsg)); return; }
    var items = (d[key] || []).slice(0, o.count || 6);
    if (!items.length) { hubMore(box, emptyMsg, moreHref); return; }
    var ul = el("ul", "list");
    items.forEach(function (it) {
      var li = el("li"), col = el("div"), a = el("a"), m = el("div", "muted", (it.s || "") + " · " + hubAgo(it.time));
      col.style.minWidth = "0"; col.style.flex = "1"; a.textContent = it.t; a.href = it.u; if (N.links_new_tab) a.target = "_blank";
      a.style.display = "block"; a.style.overflow = "hidden"; a.style.textOverflow = "ellipsis"; a.style.whiteSpace = "nowrap";
      col.appendChild(a); col.appendChild(m); li.appendChild(col); ul.appendChild(li);
    });
    box.appendChild(ul); hubMore(box, more, moreHref);
  }
  draw(); HUBW.push(draw);
}
W.followfeed = function (o, c) { hubItems(o, c, "feed", "📣 Following is turned off.", "📣 Follow channels, sites & topics →", "See everything →", "nova://following"); };
W.gamenews = function (o, c) { hubItems(o, c, "gamenews", "🎮 Games hub is turned off.", "🎮 Link your games →", "All game updates →", "nova://games"); };
function hubIn(t) { var s = t - Date.now() / 1000; if (s <= 0) return "any minute"; var d = Math.floor(s / 86400), h = Math.floor(s % 86400 / 3600), m = Math.floor(s % 3600 / 60);
  return "in " + (d ? d + "d " + h + "h" : h ? h + "h " + m + "m" : Math.max(1, m) + "m"); }
W.anime = function (o, c) {
  var box = el("div"); c.appendChild(box);
  function draw() {
    box.innerHTML = ""; var d = hubD(), list = (d.anime || []).slice(0, o.count || 5);
    if (d.follow_on === false) { box.appendChild(el("div", "muted", "📣 Following is turned off.")); return; }
    if (!list.length) { hubMore(box, "📺 Track your anime →", "nova://following"); return; }
    var ul = el("ul", "list");
    list.forEach(function (a) {
      var li = el("li"), im = el("img"), col = el("div"), t = el(a.watch ? "a" : "span", "t"), sub;
      im.src = /^https?:/.test(a.img || "") ? a.img : ""; im.width = 26; im.height = 36; im.style.objectFit = "cover"; im.style.borderRadius = "4px";
      im.onerror = function () { im.style.visibility = "hidden"; };
      col.style.minWidth = "0"; col.style.flex = "1"; t.textContent = a.t; t.style.display = "block"; t.style.overflow = "hidden";
      t.style.textOverflow = "ellipsis"; t.style.whiteSpace = "nowrap";
      if (a.watch) { t.href = a.watch; if (N.links_new_tab) t.target = "_blank"; }
      if (a.new > 0) { sub = el("div", "", "▶ " + a.new + " new episode" + (a.new > 1 ? "s" : "") + " to watch"); sub.style.color = "#ff5a6a"; sub.style.fontWeight = "700"; }
      else if (a.next && a.at) sub = el("div", "muted", "Ep " + a.next + " " + hubIn(a.at));
      else sub = el("div", "muted", a.status === "FINISHED" ? "Finished" : "");
      sub.style.fontSize = ".85em";
      col.appendChild(t); col.appendChild(sub); li.appendChild(im); li.appendChild(col); ul.appendChild(li);
    });
    box.appendChild(ul); hubMore(box, "All your anime →", "nova://anime");
  }
  draw(); HUBW.push(draw);
};
window.novaHubData = function (d) {
  N.hub = d || {}; if (N.hub.follow_on === false) N.hub.feed_off = true; if (N.hub.games_on === false) N.hub.gamenews_off = true;
  HUBW.forEach(function (f) { try { f(); } catch (e) {} });
};
if (N.hub) { if (N.hub.follow_on === false) N.hub.feed_off = true; if (N.hub.games_on === false) N.hub.gamenews_off = true; }

(N.widgets || []).forEach(function (w) {
  if (!w || w.pos === "Hidden" || !W[w.type]) return;
  try { W[w.type](w, card(w.id || w.type, w.title, w.pos)); } catch (e) { console.error("widget", w.type, e); }
});

if (S.position === "Below widgets" && typeof searchForm !== "undefined") center.appendChild(searchForm);
/* tiles (always last in the center column) */
var T = N.tiles || {};
if (T.show !== false && (T.items || []).length) {
  var tg = el("div", "tiles-" + (T.style || "glass").toLowerCase() + " tiles-" + (T.shape || "rounded").toLowerCase() + (T.labels === false ? " tiles-nolabel" : ""));
  tg.id = "tiles"; setVar("--ts", (T.size || 110) + "px");
  T.items.forEach(function (it) { var a = el("a", "tile"); a.href = it.u; a.title = it.t; if (N.links_new_tab) a.target = "_blank";
    var im = el("img"); im.alt = ""; im.src = "https://icons.duckduckgo.com/ip3/" + it.h + ".ico"; im.onerror = function () { im.style.visibility = "hidden"; };
    a.appendChild(im); a.appendChild(el("span", null, it.t)); tg.appendChild(a); });
  center.appendChild(tg);
} else if (T.show !== false) {
  center.appendChild(el("div", "muted", "Press ☆ or Ctrl+D on any page to pin it here."));
}

if (N.tip !== false) {
  var tips = ["<kbd>Ctrl</kbd>+<kbd>K</kbd> finds any feature, tab or page", "<kbd>Alt</kbd>+<kbd>]</kbd> speeds up any video",
    "<kbd>F9</kbd> turns messy articles into clean reading", "Right-click selected text to ask Nova about it",
    "<kbd>Ctrl</kbd>+<kbd>,</kbd> opens Customize", "<kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>F</kbd> floats a tab on top of everything",
    "✎ Layout lets you drag these widgets anywhere", "Try a Style Pack in ⚙ Customize"];
  $("tip").innerHTML = "Tip: " + tips[Math.floor(Math.random() * tips.length)];
}

setInterval(function () { tickers.forEach(function (f) { try { f(); } catch (e) {} }); }, 1000);

/* ---------------- drag layout ---------------- */
var editing = false, drag = null;
$("editbtn").style.display = WG.draggable === false ? "none" : "";
$("editbtn").onclick = function () { editing = !editing; document.body.classList.toggle("editing", editing);
  $("editbtn").textContent = editing ? "✓ Done" : "✎ Layout"; $("resetbtn").style.display = editing ? "" : "none"; };
$("resetbtn").onclick = function () { store("layout", {}); layout = {}; document.querySelectorAll(".wg").forEach(function (w) { w.style.transform = ""; }); };
document.addEventListener("mousedown", function (e) {
  if (!editing) return; var w = e.target.closest(".wg"); if (!w) return; e.preventDefault();
  var p = layout[w.dataset.id] || { x: 0, y: 0 }; drag = { w: w, sx: e.clientX - p.x, sy: e.clientY - p.y };
});
document.addEventListener("mousemove", function (e) { if (!drag) return; var x = e.clientX - drag.sx, y = e.clientY - drag.sy;
  drag.w.style.transform = "translate(" + x + "px," + y + "px)"; layout[drag.w.dataset.id] = { x: x, y: y }; });
document.addEventListener("mouseup", function () { if (drag) { store("layout", layout); drag = null; } });

/* ---------------- wallpapers ---------------- */
var P = N.wp || {};
var cv = $("wp"), ctx = cv.getContext("2d"), Wd = 0, Ht = 0, DPR = Math.min(window.devicePixelRatio || 1, 1.5);
var mouse = { x: -9999, y: -9999, on: false };
var speed = (P.speed || 5) / 5, dens = (P.density || 5) / 5;
$("dim").style.background = "rgba(0,0,0," + ((P.dim == null ? 25 : P.dim) / 100) + ")";
if (P.vignette) $("dim").style.boxShadow = "inset 0 0 220px rgba(0,0,0,.75)";
if (P.blur) { [cv, $("wpv"), $("wpimg"), $("wpimg2")].forEach(function (x) { x.style.filter = "blur(" + P.blur + "px)"; x.style.transform = "scale(1.05)"; }); }
function resize() { Wd = innerWidth; Ht = innerHeight; cv.width = Wd * DPR; cv.height = Ht * DPR; ctx.setTransform(DPR, 0, 0, DPR, 0, 0); }
addEventListener("resize", function () { resize(); if (scene && scene.init) scene.init(); });
if (P.mouse !== false) { addEventListener("mousemove", function (e) { mouse.x = e.clientX; mouse.y = e.clientY; mouse.on = true; });
  document.addEventListener("mouseleave", function () { mouse.on = false; mouse.x = mouse.y = -9999; }); }
var A = hexRgb(N.accent), A2 = hexRgb(N.accent_light), C1 = hexRgb(P.c1 || N.accent), C2 = hexRgb(P.c2 || "#ff6fae");
var mode = P.color_mode || "Accent";
function col(i, a) { // colour for particle i
  a = a == null ? 1 : a;
  if (mode === "Rainbow") return "hsla(" + ((i * 47 + Date.now() / 60) % 360) + ",85%,65%," + a + ")";
  if (mode === "White") return "rgba(255,255,255," + a + ")";
  var c = mode === "Custom" ? (i % 2 ? C2 : C1) : (i % 3 === 0 ? A2 : A);
  return "rgba(" + c[0] + "," + c[1] + "," + c[2] + "," + a + ")";
}
function rnd(a, b) { return a + Math.random() * (b - a); }
var scene = null, S2 = {};

S2.Starfield = { init: function () { this.s = []; var n = Math.floor(450 * dens); for (var i = 0; i < n; i++) this.s.push(this.mk(true)); },
  mk: function (any) { return { x: rnd(-1, 1), y: rnd(-1, 1), z: any ? rnd(.05, 1) : 1, i: Math.floor(rnd(0, 99)) }; },
  draw: function () { ctx.fillStyle = "rgba(5,6,12,.55)"; ctx.fillRect(0, 0, Wd, Ht);
    var cx = mouse.on ? Wd / 2 + (mouse.x - Wd / 2) * .25 : Wd / 2, cy = mouse.on ? Ht / 2 + (mouse.y - Ht / 2) * .25 : Ht / 2, self = this;
    this.s.forEach(function (p, k) { var pz = p.z; p.z -= .006 * speed; if (p.z <= .02) { self.s[k] = self.mk(false); return; }
      var sx = cx + p.x / p.z * Wd * .5, sy = cy + p.y / p.z * Ht * .5, px = cx + p.x / pz * Wd * .5, py = cy + p.y / pz * Ht * .5;
      ctx.strokeStyle = col(p.i, Math.min(1, (1 - p.z) * 1.4)); ctx.lineWidth = Math.max(.5, (1 - p.z) * 2.6);
      ctx.beginPath(); ctx.moveTo(px, py); ctx.lineTo(sx, sy); ctx.stroke(); }); } };

S2.Constellation = { init: function () { this.p = []; var n = Math.floor(Wd * Ht / 14000 * dens); for (var i = 0; i < n; i++)
    this.p.push({ x: rnd(0, Wd), y: rnd(0, Ht), vx: rnd(-.4, .4), vy: rnd(-.4, .4), i: i }); },
  draw: function () { ctx.clearRect(0, 0, Wd, Ht); var p = this.p, d2 = 130 * 130;
    for (var i = 0; i < p.length; i++) { var a = p[i]; a.x += a.vx * speed; a.y += a.vy * speed;
      if (a.x < 0 || a.x > Wd) a.vx *= -1; if (a.y < 0 || a.y > Ht) a.vy *= -1;
      if (mouse.on) { var mx = mouse.x - a.x, my = mouse.y - a.y, md = mx * mx + my * my; if (md < 160 * 160) { a.x += mx * .006; a.y += my * .006;
        ctx.strokeStyle = col(i, .5 * (1 - md / (160 * 160))); ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(mouse.x, mouse.y); ctx.stroke(); } }
      for (var j = i + 1; j < p.length; j++) { var b = p[j], dx = a.x - b.x, dy = a.y - b.y, dd = dx * dx + dy * dy;
        if (dd < d2) { ctx.strokeStyle = col(i, .35 * (1 - dd / d2)); ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke(); } }
      ctx.fillStyle = col(i, .9); ctx.beginPath(); ctx.arc(a.x, a.y, 2, 0, 7); ctx.fill(); } } };

S2["Matrix rain"] = { init: function () { this.fs = 16; this.cols = Math.ceil(Wd / this.fs); this.y = [];
    for (var i = 0; i < this.cols; i++) this.y.push(rnd(-20, Ht / this.fs)); ctx.fillStyle = "#000"; ctx.fillRect(0, 0, Wd, Ht); },
  ch: "アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワン0123456789NOVA",
  draw: function () { ctx.fillStyle = "rgba(0,0,0,.08)"; ctx.fillRect(0, 0, Wd, Ht); ctx.font = this.fs + "px monospace";
    for (var i = 0; i < this.cols; i++) { if (Math.random() > dens * .9 + .1) continue;
      var c = this.ch[Math.floor(Math.random() * this.ch.length)], x = i * this.fs, y = this.y[i] * this.fs;
      ctx.fillStyle = Math.random() < .05 ? "#fff" : col(i, .9); ctx.fillText(c, x, y);
      this.y[i] += .5 * speed; if (y > Ht && Math.random() > .975) this.y[i] = 0; } } };

S2.Aurora = { init: function () { this.t = 0; },
  draw: function () { this.t += .004 * speed; ctx.globalCompositeOperation = "source-over"; ctx.fillStyle = "rgba(6,8,16,.35)"; ctx.fillRect(0, 0, Wd, Ht);
    ctx.globalCompositeOperation = "lighter"; var bands = Math.round(3 + dens * 2);
    for (var b = 0; b < bands; b++) { var base = Ht * (.25 + b * .07), amp = Ht * (.06 + .03 * b);
      var gr = ctx.createLinearGradient(0, base - amp * 2, 0, base + amp * 2); gr.addColorStop(0, col(b, 0)); gr.addColorStop(.5, col(b, .14)); gr.addColorStop(1, col(b, 0));
      ctx.fillStyle = gr; ctx.beginPath(); ctx.moveTo(0, Ht);
      for (var x = 0; x <= Wd; x += 20) { var y = base + Math.sin(x * .004 + this.t * (1 + b * .3) + b) * amp + Math.sin(x * .011 - this.t * 1.7) * amp * .4;
        if (mouse.on) y += Math.exp(-Math.pow((x - mouse.x) / 160, 2)) * 40; ctx.lineTo(x, y); }
      ctx.lineTo(Wd, Ht); ctx.closePath(); ctx.fill(); }
    ctx.globalCompositeOperation = "source-over"; } };

S2.Fireflies = { init: function () { this.f = []; var n = Math.floor(70 * dens); for (var i = 0; i < n; i++)
    this.f.push({ x: rnd(0, Wd), y: rnd(0, Ht), a: rnd(0, 6.28), s: rnd(.2, .8), p: rnd(0, 6.28), i: i }); },
  draw: function () { ctx.fillStyle = "rgba(4,6,10,.3)"; ctx.fillRect(0, 0, Wd, Ht);
    this.f.forEach(function (f) { f.a += rnd(-.2, .2); f.x += Math.cos(f.a) * f.s * speed; f.y += Math.sin(f.a) * f.s * speed; f.p += .03 * speed;
      if (mouse.on) { var dx = f.x - mouse.x, dy = f.y - mouse.y, d = Math.sqrt(dx * dx + dy * dy); if (d < 120) { f.x += dx / d * 2; f.y += dy / d * 2; } }
      if (f.x < -20) f.x = Wd + 20; if (f.x > Wd + 20) f.x = -20; if (f.y < -20) f.y = Ht + 20; if (f.y > Ht + 20) f.y = -20;
      var glow = (Math.sin(f.p) + 1) / 2, g = ctx.createRadialGradient(f.x, f.y, 0, f.x, f.y, 14);
      g.addColorStop(0, col(f.i, .9 * glow)); g.addColorStop(1, col(f.i, 0)); ctx.fillStyle = g; ctx.beginPath(); ctx.arc(f.x, f.y, 14, 0, 7); ctx.fill(); }); } };

S2.Snow = { init: function () { this.f = []; var n = Math.floor(260 * dens); for (var i = 0; i < n; i++) this.f.push({ x: rnd(0, Wd), y: rnd(0, Ht), r: rnd(1, 3.5), v: rnd(.5, 1.6), w: rnd(0, 6), i: i }); },
  draw: function () { ctx.clearRect(0, 0, Wd, Ht); var wind = mouse.on ? (mouse.x / Wd - .5) * 2 : 0;
    this.f.forEach(function (f) { f.y += f.v * speed; f.w += .01; f.x += Math.sin(f.w) * .5 + wind * f.r * .4;
      if (f.y > Ht + 5) { f.y = -5; f.x = rnd(0, Wd); } if (f.x > Wd + 5) f.x = -5; if (f.x < -5) f.x = Wd + 5;
      ctx.fillStyle = mode === "Accent" ? "rgba(255,255,255," + (.4 + f.r / 6) + ")" : col(f.i, .8); ctx.beginPath(); ctx.arc(f.x, f.y, f.r, 0, 7); ctx.fill(); }); } };

S2.Rain = { init: function () { this.d = []; var n = Math.floor(400 * dens); for (var i = 0; i < n; i++) this.d.push({ x: rnd(0, Wd), y: rnd(0, Ht), l: rnd(10, 25), v: rnd(8, 16), i: i }); this.flash = 0; },
  draw: function () { ctx.fillStyle = "rgba(8,10,16,.5)"; ctx.fillRect(0, 0, Wd, Ht);
    if (Math.random() < .002) this.flash = 1; if (this.flash > 0) { ctx.fillStyle = "rgba(200,210,255," + this.flash * .25 + ")"; ctx.fillRect(0, 0, Wd, Ht); this.flash -= .05; }
    ctx.lineWidth = 1; this.d.forEach(function (d) { d.y += d.v * speed; d.x -= d.v * speed * .15; if (d.y > Ht) { d.y = -d.l; d.x = rnd(0, Wd * 1.2); }
      ctx.strokeStyle = mode === "Accent" ? "rgba(170,190,230,.45)" : col(d.i, .5); ctx.beginPath(); ctx.moveTo(d.x, d.y); ctx.lineTo(d.x + d.l * .15, d.y - d.l); ctx.stroke(); }); } };

S2["Synthwave grid"] = { init: function () { this.t = 0; },
  draw: function () { this.t += .01 * speed; var hz = Ht * .55;
    var sky = ctx.createLinearGradient(0, 0, 0, hz); sky.addColorStop(0, "#0b0518"); sky.addColorStop(1, col(1, .55)); ctx.fillStyle = sky; ctx.fillRect(0, 0, Wd, hz);
    var sun = ctx.createLinearGradient(0, hz - 260, 0, hz); sun.addColorStop(0, "#ffd36e"); sun.addColorStop(1, mode === "Accent" ? "#ff4fa0" : col(2, 1));
    ctx.fillStyle = sun; ctx.beginPath(); ctx.arc(Wd / 2, hz, 170, Math.PI, 0); ctx.fill();
    ctx.fillStyle = "#0b0518"; for (var k = 0; k < 6; k++) ctx.fillRect(Wd / 2 - 180, hz - 12 - k * 22, 360, 3 + k);
    ctx.fillStyle = "#07030f"; ctx.fillRect(0, hz, Wd, Ht - hz); ctx.strokeStyle = col(0, .8); ctx.lineWidth = 1.5;
    for (var i = -20; i <= 20; i++) { ctx.beginPath(); ctx.moveTo(Wd / 2 + i * 30, hz); ctx.lineTo(Wd / 2 + i * Wd * .18, Ht); ctx.stroke(); }
    var off = this.t % 1; for (var j = 0; j < 14; j++) { var y = hz + Math.pow((j + off) / 14, 2.2) * (Ht - hz);
      ctx.globalAlpha = Math.min(1, (y - hz) / 60); ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(Wd, y); ctx.stroke(); } ctx.globalAlpha = 1; } };

S2.Bubbles = { init: function () { this.b = []; var n = Math.floor(45 * dens); for (var i = 0; i < n; i++) this.b.push(this.mk(i, true)); },
  mk: function (i, any) { return { x: rnd(0, Wd), y: any ? rnd(0, Ht) : Ht + 60, r: rnd(8, 46), v: rnd(.3, 1.1), w: rnd(0, 6), i: i }; },
  draw: function () { ctx.clearRect(0, 0, Wd, Ht); var self = this;
    this.b.forEach(function (b, k) { b.y -= b.v * speed; b.w += .01; b.x += Math.sin(b.w) * .4;
      if (mouse.on && Math.hypot(b.x - mouse.x, b.y - mouse.y) < b.r) { self.b[k] = self.mk(b.i, false); return; }
      if (b.y < -60) { self.b[k] = self.mk(b.i, false); return; }
      ctx.strokeStyle = col(b.i, .55); ctx.lineWidth = 1.5; ctx.beginPath(); ctx.arc(b.x, b.y, b.r, 0, 7); ctx.stroke();
      ctx.fillStyle = col(b.i, .08); ctx.fill(); ctx.fillStyle = "rgba(255,255,255,.35)"; ctx.beginPath(); ctx.arc(b.x - b.r * .35, b.y - b.r * .35, b.r * .15, 0, 7); ctx.fill(); }); } };

S2.Waves = { init: function () { this.t = 0; },
  draw: function () { this.t += .01 * speed; ctx.fillStyle = "#070a14"; ctx.fillRect(0, 0, Wd, Ht); var n = Math.round(3 + dens * 2);
    for (var k = 0; k < n; k++) { var base = Ht * (.45 + k * .1), amp = 18 + k * 8; ctx.fillStyle = col(k, .12 + k * .03); ctx.beginPath(); ctx.moveTo(0, Ht);
      for (var x = 0; x <= Wd; x += 12) { var y = base + Math.sin(x * .006 + this.t * (1 + k * .25) + k) * amp + Math.sin(x * .017 + this.t * 2) * amp * .3;
        if (mouse.on) y -= Math.exp(-Math.pow((x - mouse.x) / 120, 2)) * 30 * (k + 1) / n; ctx.lineTo(x, y); }
      ctx.lineTo(Wd, Ht); ctx.closePath(); ctx.fill(); } } };

S2["Sakura petals"] = { init: function () { this.p = []; var n = Math.floor(90 * dens); for (var i = 0; i < n; i++) this.p.push(this.mk(i, true)); },
  mk: function (i, any) { return { x: rnd(-Wd * .2, Wd), y: any ? rnd(0, Ht) : -20, s: rnd(6, 13), v: rnd(.6, 1.6), r: rnd(0, 6.28), vr: rnd(-.03, .03), w: rnd(0, 6), i: i }; },
  draw: function () { ctx.clearRect(0, 0, Wd, Ht); var self = this;
    this.p.forEach(function (p, k) { p.y += p.v * speed; p.w += .02; p.x += (Math.sin(p.w) + .8) * .7 * speed; p.r += p.vr * speed;
      if (p.y > Ht + 20 || p.x > Wd + 20) { self.p[k] = self.mk(p.i, false); return; }
      ctx.save(); ctx.translate(p.x, p.y); ctx.rotate(p.r); ctx.scale(1, Math.abs(Math.sin(p.w)) * .6 + .4);
      ctx.fillStyle = mode === "Accent" ? "rgba(255," + (170 + p.i % 40) + ",205,.85)" : col(p.i, .85);
      ctx.beginPath(); ctx.ellipse(0, 0, p.s, p.s * .55, 0, 0, 7); ctx.fill(); ctx.restore(); }); } };

S2.Hyperspace = { init: function () { this.l = []; var n = Math.floor(260 * dens); for (var i = 0; i < n; i++) this.l.push({ a: rnd(0, 6.28), d: rnd(0, 1), v: rnd(.004, .015), i: i }); },
  draw: function () { ctx.fillStyle = "rgba(2,3,10,.35)"; ctx.fillRect(0, 0, Wd, Ht); var cx = Wd / 2, cy = Ht / 2, R = Math.hypot(Wd, Ht) / 2;
    this.l.forEach(function (l) { var d0 = l.d; l.d += l.v * speed * (1 + l.d * 3); if (l.d > 1) { l.d = rnd(0, .1); d0 = l.d; }
      ctx.strokeStyle = col(l.i, Math.min(1, l.d * 1.5)); ctx.lineWidth = 1 + l.d * 2; ctx.beginPath();
      ctx.moveTo(cx + Math.cos(l.a) * d0 * d0 * R, cy + Math.sin(l.a) * d0 * d0 * R); ctx.lineTo(cx + Math.cos(l.a) * l.d * l.d * R, cy + Math.sin(l.a) * l.d * l.d * R); ctx.stroke(); }); } };

S2.Nebula = { init: function () { this.b = []; for (var i = 0; i < Math.round(4 + dens * 3); i++)
    this.b.push({ x: rnd(0, Wd), y: rnd(0, Ht), r: rnd(200, 480), vx: rnd(-.25, .25), vy: rnd(-.25, .25), i: i }); this.stars = [];
    for (var k = 0; k < 180; k++) this.stars.push([rnd(0, Wd), rnd(0, Ht), rnd(.3, 1.4)]); },
  draw: function () { ctx.globalCompositeOperation = "source-over"; ctx.fillStyle = "#05040c"; ctx.fillRect(0, 0, Wd, Ht);
    ctx.fillStyle = "rgba(255,255,255,.7)"; this.stars.forEach(function (s) { ctx.fillRect(s[0], s[1], s[2], s[2]); });
    ctx.globalCompositeOperation = "lighter";
    this.b.forEach(function (b) { b.x += b.vx * speed; b.y += b.vy * speed; if (b.x < -b.r || b.x > Wd + b.r) b.vx *= -1; if (b.y < -b.r || b.y > Ht + b.r) b.vy *= -1;
      var g = ctx.createRadialGradient(b.x, b.y, 0, b.x, b.y, b.r); g.addColorStop(0, col(b.i, .22)); g.addColorStop(1, col(b.i, 0));
      ctx.fillStyle = g; ctx.beginPath(); ctx.arc(b.x, b.y, b.r, 0, 7); ctx.fill(); });
    ctx.globalCompositeOperation = "source-over"; } };

S2["Time-of-day sky"] = { init: function () { this.stars = []; for (var k = 0; k < 220; k++) this.stars.push([rnd(0, Wd), rnd(0, Ht * .8), rnd(.3, 1.5), rnd(0, 6)]); },
  draw: function () { var h = new Date().getHours() + new Date().getMinutes() / 60, top, bot, night;
    if (h < 5 || h >= 21) { top = "#03040c"; bot = "#141a33"; night = 1; } else if (h < 7) { top = "#2a2350"; bot = "#f29b6b"; night = .4; }
    else if (h < 17) { top = "#2b6cc4"; bot = "#9ccdf2"; night = 0; } else if (h < 19.5) { top = "#3a2a6b"; bot = "#ff8a5c"; night = .2; } else { top = "#141433"; bot = "#5a3a7a"; night = .7; }
    var g = ctx.createLinearGradient(0, 0, 0, Ht); g.addColorStop(0, top); g.addColorStop(1, bot); ctx.fillStyle = g; ctx.fillRect(0, 0, Wd, Ht);
    if (night) this.stars.forEach(function (s) { s[3] += .02 * speed; ctx.fillStyle = "rgba(255,255,255," + night * (.4 + .6 * Math.abs(Math.sin(s[3]))) + ")"; ctx.fillRect(s[0], s[1], s[2], s[2]); }); } };

S2["Flowing gradient"] = { init: function () { this.t = 0; },
  draw: function () { this.t += .003 * speed; var x1 = Wd * (.5 + .5 * Math.cos(this.t)), y1 = Ht * (.5 + .5 * Math.sin(this.t * 1.3));
    var g = ctx.createRadialGradient(x1, y1, 0, Wd / 2, Ht / 2, Math.hypot(Wd, Ht) * .75);
    g.addColorStop(0, col(0, 1)); g.addColorStop(.5, "rgb(" + C2.join(",") + ")"); g.addColorStop(1, "#0a0b12");
    if (mode === "Accent") { g = ctx.createRadialGradient(x1, y1, 0, Wd / 2, Ht / 2, Math.hypot(Wd, Ht) * .75);
      g.addColorStop(0, "rgb(" + A.join(",") + ")"); g.addColorStop(.45, "rgba(" + A2.join(",") + ",.35)"); g.addColorStop(1, "#0a0b12"); }
    ctx.fillStyle = g; ctx.fillRect(0, 0, Wd, Ht); } };

var fpsCap = P.fps === "30" ? 30 : P.fps === "Unlimited" ? 0 : 60, lastFrame = 0;
function loop(now) { requestAnimationFrame(loop); if (!scene) return; if (fpsCap && now - lastFrame < 1000 / fpsCap - 1) return; lastFrame = now; scene.draw(); }
var type = P.type || "Constellation";
function solidBg() { cv.style.display = "none"; }
if (type === "Solid colour") { solidBg(); document.body.style.background = P.c1 || N.bg; }
else if (type === "Gradient") { solidBg(); document.body.style.background = "linear-gradient(" + (P.angle || 135) + "deg," + (P.c1 || N.accent) + "," + (P.c2 || "#15161b") + ")"; }
else if (type === "Your image" && P.image) { solidBg(); var im = $("wpimg"); im.style.display = "block"; im.style.backgroundImage = "url('" + P.image + "')"; }
else if (type === "Your video" && P.video) { solidBg(); var v = $("wpv"); v.style.display = "block"; v.src = P.video; }
else if (type === "Slideshow" && (P.images || []).length) {
  solidBg(); var a = $("wpimg"), b = $("wpimg2"), idx = Math.floor(Math.random() * P.images.length), front = a;
  a.style.display = b.style.display = "block"; b.style.opacity = 0; a.style.backgroundImage = "url('" + P.images[idx] + "')";
  setInterval(function () { idx = (idx + 1) % P.images.length; var back = front === a ? b : a; back.style.backgroundImage = "url('" + P.images[idx] + "')";
    back.style.opacity = 1; front.style.opacity = 0; front = back; }, Math.max(5, P.interval || 30) * 1000);
}
else if (S2[type]) { resize(); scene = S2[type]; scene.init(); requestAnimationFrame(loop); }
else { solidBg(); }
window.__novaReady = true;
})();
</script>
</body></html>
"""


def _host(u):
    h = (urllib.parse.urlsplit(u).hostname or "").lower()
    return h[4:] if h.startswith("www.") else h


def search_template(s):
    url = SEARCH_ENGINES.get(s.get("search_engine"), "") or s.get("custom_search", "")
    return url if "%s" in url and url.startswith(("http://", "https://")) else "https://duckduckgo.com/?q=%s"


def start_page_config(s, bookmarks, history, read_later, screen_time, weather=None, hub=None):
    """Everything the start page needs, as one dictionary (turned into JSON inside start.html)."""
    accent, light, _ = theme_colors()
    tiles, seen = [], set()

    def add_tile(title, url):
        if url in seen or not url.startswith(("http://", "https://")):
            return
        seen.add(url)
        tiles.append({"t": title or _host(url), "u": url, "h": _host(url)})
    if s["sp_tile_source"] in ("Bookmarks", "Both"):
        for b in bookmarks:
            add_tile(b.get("title", ""), b.get("url", ""))
    if s["sp_tile_source"] in ("Most visited", "Both"):
        counts = {}
        for h in history:
            hh = _host(h.get("url", ""))
            if hh:
                c = counts.setdefault(hh, [0, h.get("url"), h.get("title")])
                c[0] += 1
        for hh, (n, url, title) in sorted(counts.items(), key=lambda kv: -kv[1][0]):
            add_tile(hh, "https://" + hh + "/")
    tiles = tiles[:int(s["sp_tile_count"])]

    widgets = []
    for wid, title, _pos, extra in WIDGETS:
        w = {"id": wid, "type": wid, "pos": s[f"w_{wid}_pos"], "title": s[f"w_{wid}_title"]}
        for k, _l, _kind, _d, _kw in extra:
            w[k] = s[f"w_{wid}_{k}"]
        widgets.append(w)
    for i, cw in enumerate(s.get("custom_widgets") or []):
        if isinstance(cw, dict):
            widgets.append({"id": f"custom-{i}", "type": "custom", "kind": cw.get("kind", "Text"), "title": cw.get("title", ""),
                            "pos": cw.get("pos", "Right"), "content": cw.get("content", ""), "height": cw.get("height", 260)})

    images = []
    folder = s.get("wp_folder") or ""
    if s["wp_type"] == "Slideshow" and folder and os.path.isdir(folder):
        for name in sorted(os.listdir(folder))[:400]:
            if name.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")):
                images.append(Path(folder, name).resolve().as_uri())

    def file_uri(p):
        return Path(p).resolve().as_uri() if p and os.path.isfile(p) else ""

    day = time.strftime("%Y-%m-%d")
    st = sorted((screen_time.get(day) or {}).items(), key=lambda kv: -kv[1])[:8]
    recent, rseen = [], set()
    for h in reversed(history):
        if h.get("url") not in rseen:
            rseen.add(h.get("url"))
            recent.append({"t": h.get("title", ""), "u": h.get("url", "")})
        if len(recent) >= 30:
            break
    return {
        "accent": accent, "accent_light": light, "text": s["sp_text_color"], "dim": pal("dim"), "bg": pal("page"),
        "card": pal("card"), "font": f'"{s["sp_font"]}",sans-serif', "layout": s["sp_layout"], "tip": s["sp_show_tip"],
        "links_new_tab": s["sp_links_new_tab"],
        "logo": {"show": s["sp_show_logo"], "text": s["sp_logo_text"], "size": s["sp_logo_size"],
                 "font": f'"{s["sp_logo_font"]}",sans-serif', "style": s["sp_logo_style"]},
        "greeting": {"show": s["sp_show_greeting"], "mode": s["sp_greeting_mode"], "custom": s["sp_custom_greeting"],
                     "name": s["sp_user_name"]},
        "search": {"show": s["sp_show_search"], "style": s["sp_search_style"], "width": s["sp_search_width"],
                   "placeholder": s["sp_search_placeholder"], "autofocus": s["sp_search_autofocus"], "glow": s["sp_search_glow"],
                   "position": s["sp_search_position"], "url": search_template(s)},
        "tiles": {"show": s["sp_show_tiles"], "size": s["sp_tile_size"], "shape": s["sp_tile_shape"], "style": s["sp_tile_style"],
                  "labels": s["sp_tile_labels"], "items": tiles},
        "wp": {"type": s["wp_type"], "speed": s["wp_speed"], "density": s["wp_density"], "color_mode": s["wp_color_mode"],
               "c1": s["wp_color"], "c2": s["wp_color2"], "angle": s["wp_gradient_angle"], "mouse": s["wp_mouse"],
               "dim": s["wp_dim"], "blur": s["wp_blur"], "vignette": s["wp_vignette"], "fps": s["wp_fps"],
               "image": file_uri(s["wp_image"]), "video": file_uri(s["wp_video"]), "images": images, "interval": s["wp_interval"]},
        "wg": {"style": s["wg_style"], "opacity": s["wg_opacity"], "radius": s["wg_radius"], "blur": s["wg_blur"],
               "scale": s["wg_scale"], "shadow": s["wg_shadow"], "accent_titles": s["wg_accent_titles"],
               "animate": s["wg_animate"], "draggable": s["wg_draggable"]},
        "widgets": widgets,
        "weather": weather or {},
        "hub": hub or {},
        "data": {"history": recent, "readlater": [{"t": r.get("title", ""), "u": r.get("url", "")} for r in read_later],
                 "screentime": [[h, int(v)] for h, v in st]},
    }


def build_start_page(s, bookmarks, history, read_later, screen_time, weather=None, hub=None):
    cfg = start_page_config(s, bookmarks, history, read_later, screen_time, weather, hub)
    blob = json.dumps(cfg, ensure_ascii=False).replace("</", "<\\/")
    page = START_HTML.replace("/*NOVA_CONFIG*/{}", blob, 1).replace(
        "<title>New Tab</title>", f"<title>{html.escape(s['sp_title'] or 'New Tab')}</title>", 1)
    START_FILE.write_text(page, encoding="utf-8")


# ---------- look ----------
DARK_STYLE = """
QMainWindow, QToolBar { background: #1e1f24; border: none; }
QToolBar { padding: 4px; spacing: 4px; }
QToolButton { color: #e6e6e6; background: transparent; padding: 4px 8px;
              border-radius: 6px; font-size: 14px; }
QToolButton:hover { background: #33353d; }
QToolButton::menu-indicator { image: none; }
QLineEdit { background: #2b2d34; color: #e6e6e6; border: 1px solid #3a3d46;
            border-radius: 8px; padding: 5px 10px; font-size: 13px; }
QLineEdit:focus { border: 1px solid #6c8cff; }
QTabWidget::pane { border: none; }
QTabBar::tab { background: #26282e; color: #b8b8b8; padding: 6px 14px;
               border-top-left-radius: 8px; border-top-right-radius: 8px;
               margin-right: 2px; max-width: 220px; }
QTabBar::tab:selected { background: #33353d; color: #ffffff; border-bottom: 2px solid #6c8cff; }
QToolBar#TitleToolbar { background: #17181d; padding: 0px; spacing: 0px; border: none; }
#TitleBar { background: #17181d; }
#TitleBar QTabBar::tab { background: transparent; color: #9a9ca6; }
#TitleBar QTabBar::tab:hover { background: #26282e; color: #e6e6e6; }
#TitleBar QTabBar::tab:selected { background: #1e1f24; color: #ffffff; }
#TitleBar QToolButton#TitlePlus { font-size: 16px; padding: 2px 9px; border-radius: 6px; }
#TitleBar QToolButton#WinBtn, #TitleBar QToolButton#WinClose { border-radius: 0px; padding: 0px;
    min-width: 46px; min-height: 32px; font-size: 12px; color: #c8cad3; }
#TitleBar QToolButton#WinBtn:hover { background: #33353d; }
#TitleBar QToolButton#WinClose:hover { background: #e81123; color: #ffffff; }
QMenu { background: #26282e; color: #e6e6e6; border: 1px solid #3a3d46; padding: 4px; }
QMenu::item { padding: 6px 18px; border-radius: 4px; }
QMenu::item:selected { background: #3a3d46; }
QMenu::item:disabled { color: #777; }
QMenu::separator { height: 1px; background: #3a3d46; margin: 4px 6px; }
QProgressBar { background: transparent; border: none; max-height: 2px; }
QProgressBar::chunk { background: #6c8cff; }
QStatusBar { background: #1e1f24; color: #9a9ca6; }
QStatusBar QLabel { color: #8fa6ff; padding: 0 8px; }
#FindBar { background: #1e1f24; border-top: 1px solid #2c2e36; }
#FindBar QLabel { color: #9a9ca6; }
#FindBar QPushButton, #Palette QPushButton { background: #2b2d34; color: #e6e6e6; border: 1px solid #3a3d46;
                       border-radius: 6px; padding: 3px 10px; }
#FindBar QPushButton:hover { background: #33353d; }
#Palette { background: #1b1c21; border: 1px solid #6c8cff; border-radius: 12px; }
#Palette QLineEdit { font-size: 16px; padding: 10px 14px; }
#Palette QListWidget { background: transparent; border: none; color: #e6e6e6; font-size: 13px; outline: none; }
#Palette QListWidget::item { padding: 7px 10px; border-radius: 6px; }
#Palette QListWidget::item:selected { background: #6c8cff; color: #ffffff; }
QMessageBox, QInputDialog { background: #1e1f24; color: #e6e6e6; }
QMessageBox QLabel, QInputDialog QLabel { color: #e6e6e6; }
QMessageBox QPushButton, QInputDialog QPushButton { background: #2b2d34; color: #e6e6e6;
                       border: 1px solid #3a3d46; border-radius: 6px; padding: 4px 14px; }
"""

DARK_STYLE += """
QToolBar#SideBar { background: #1d1f25; border: none; border-right: 1px solid #2b2d34; padding: 6px 3px; spacing: 6px; }
QToolBar#SideBar QToolButton { font-size: 19px; padding: 6px; border-radius: 10px; min-width: 34px; }
QToolBar#SideBar QToolButton:hover { background: #2b2d34; }
QToolBar#SideBar QToolButton:checked { background: #2c3550; border-left: 3px solid #6c8cff; }
#SideHead { background: #1d1f25; border-bottom: 1px solid #2b2d34; }
#SideHead QToolButton { font-size: 13px; padding: 3px 7px; }
"""
DARK_STYLE += """
#VoiceBubble { background: #1d1f25; border: 1px solid #3a3d46; border-radius: 22px; }
#VoiceBubble[live="true"] { border: 1px solid #ff4d5e; }
#VoiceBubble QLabel { background: transparent; color: #e6e6e6; font-size: 14px; }
#VoiceIcon { font-size: 18px; }
#VoiceMeter { background: #2b2d34; border: none; border-radius: 3px; }
#VoiceMeter::chunk { background: #ff4d5e; border-radius: 3px; }
"""
DARK_STYLE += """
#Toast { background: #26282e; border: 1px solid #6c8cff; border-radius: 12px; }
#Toast QLabel { color: #e6e6e6; background: transparent; }
#Toast QLabel#ToastIcon { font-size: 22px; }
#Toast QToolButton { color: #9a9ca6; font-size: 12px; padding: 2px 6px; }
"""

NOVA_STYLE = """
#NovaPanel { background: #17181d; border-left: 1px solid #2c2e36; }
#NovaTitle { color: #8fa6ff; font-size: 18px; font-weight: 600; letter-spacing: 4px; }
#NovaStatus { color: #8a8d98; font-size: 11px; }
#NovaLog { background: transparent; border: none; color: #e6e6e6; font-size: 13px; }
#NovaStart { background: #6c8cff; color: white; border: none; border-radius: 8px;
             padding: 8px; font-weight: 600; }
#NovaStart:hover { background: #7f9bff; }
#NovaStart:disabled { background: #3a3d46; color: #9a9ca6; }
#NovaSend { background: #2b2d34; color: #8fa6ff; border: 1px solid #3a3d46;
            border-radius: 8px; padding: 5px 10px; }
#NovaSend:hover { background: #33353d; }
#NovaChip { background: #23252c; color: #b8b8b8; border: 1px solid #33353d;
            border-radius: 10px; padding: 3px 9px; font-size: 11px; }
#NovaChip:hover { color: #ffffff; border-color: #6c8cff; }
"""


CURRENT_SEARCH = {"url": "https://duckduckgo.com/?q=%s"}


def to_url(text: str) -> QUrl:
    """Turn whatever was typed into a URL: a real address, or a search."""
    text = text.strip()
    if not text:
        return START_URL
    if text.startswith(("http://", "https://", "file://")):
        return QUrl(text)
    if "." in text and " " not in text:
        return QUrl("https://" + text)
    return QUrl(CURRENT_SEARCH["url"].replace("%s", QUrl.toPercentEncoding(text).data().decode()))


# ---------- ad & tracker blocker ----------
AD_HOSTS = {
    "doubleclick.net", "googlesyndication.com", "googleadservices.com", "adservice.google.com",
    "googletagservices.com", "pagead2.googlesyndication.com", "amazon-adsystem.com", "adnxs.com",
    "taboola.com", "outbrain.com", "criteo.com", "criteo.net", "scorecardresearch.com", "quantserve.com",
    "hotjar.com", "moatads.com", "pubmatic.com", "rubiconproject.com", "openx.net", "adsrvr.org",
    "casalemedia.com", "media.net", "zedo.com", "adform.net", "smartadserver.com", "yieldmo.com",
    "sharethrough.com", "teads.tv", "33across.com", "lijit.com", "sovrn.com", "bidswitch.net",
    "adroll.com", "mathtag.com", "rlcdn.com", "demdex.net", "krxd.net", "bluekai.com", "exelator.com",
    "everesttech.net", "omtrdc.net", "chartbeat.com", "newrelic.com", "nr-data.net", "mixpanel.com",
    "segment.io", "fullstory.com", "mouseflow.com", "crazyegg.com", "inmobi.com", "propellerads.com",
    "popads.net", "popcash.net", "adsterra.com", "exoclick.com", "trafficjunky.net", "revcontent.com",
    "mgid.com", "zergnet.com", "undertone.com", "advertising.com", "serving-sys.com", "adcolony.com",
    "applovin.com", "unityads.unity3d.com", "ads.yahoo.com", "analytics.yahoo.com", "ads.twitter.com",
    "static.ads-twitter.com", "ads.linkedin.com", "px.ads.linkedin.com", "tr.snapchat.com",
    "ads.tiktok.com", "analytics.tiktok.com", "bat.bing.com", "clarity.ms",
}


class AdBlocker(QWebEngineUrlRequestInterceptor):
    """Blocks requests to well-known ad and tracking servers (never the page you asked for)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.enabled = True
        self.blocked = 0
        self.dnt = True
        self.gpc = True

    def interceptRequest(self, info):
        if self.dnt:
            info.setHttpHeader(b"DNT", b"1")
        if self.gpc:
            info.setHttpHeader(b"Sec-GPC", b"1")
        if not self.enabled:
            return
        if info.resourceType() == QWebEngineUrlRequestInfo.ResourceType.ResourceTypeMainFrame:
            return
        h = info.requestUrl().host().lower()
        while h:
            if h in AD_HOSTS:
                info.block(True)
                self.blocked += 1
                return
            dot = h.find(".")
            if dot < 0:
                break
            h = h[dot + 1:]


# ---------- scripts injected into pages ----------
DARK_WEB_JS = r"""(function(){var id='nova-dark';if(document.getElementById(id))return;
if(location.protocol==='file:'||document.querySelector('meta[name="nova-page"]'))return;
var s=document.createElement('style');s.id=id;
s.textContent='html{filter:invert(.92) hue-rotate(180deg)!important;background:#111!important}'+
'img,video,picture,canvas,iframe,embed,object,[style*="background-image"]{filter:invert(1) hue-rotate(180deg)!important}';
(document.head||document.documentElement).appendChild(s);})();"""

# Video speed: runs in every frame (so it also reaches players inside iframes) and listens for a message.
VIDEO_SPEED_JS = r"""(function(){if(window.__novaSpeed)return;window.__novaSpeed=1;
function badge(n){if(!NOVA_BADGE)return;var b=document.getElementById('nova-speed');
 if(!b){b=document.createElement('div');b.id='nova-speed';
  b.style.cssText='position:fixed;top:16px;left:16px;z-index:2147483647;background:rgba(20,22,30,.88);color:#8fa6ff;font:600 18px Segoe UI,sans-serif;padding:8px 14px;border-radius:10px;pointer-events:none;transition:opacity .4s';
  (document.body||document.documentElement).appendChild(b);}
 b.textContent=(Math.round(n*100)/100)+'×';b.style.opacity='1';clearTimeout(b._t);
 b._t=setTimeout(function(){b.style.opacity='0'},1200);}
function apply(m){var vs=document.querySelectorAll('video');
 for(var i=0;i<vs.length;i++){var v=vs[i];
  var n=m.reset?1:Math.min(16,Math.max(0.25,Math.round((v.playbackRate+m.delta)*100)/100));
  v.playbackRate=n;badge(n);}
 for(var j=0;j<window.frames.length;j++){try{window.frames[j].postMessage({novaSpeed:m},'*')}catch(e){}}}
window.addEventListener('message',function(e){if(e.data&&e.data.novaSpeed)apply(e.data.novaSpeed);});
})();"""



def video_speed_js(badge=True):
    return "var NOVA_BADGE=" + ("true" if badge else "false") + ";" + VIDEO_SPEED_JS


# Reader mode: finds the main article and returns clean HTML (no scripts, no styles, no event handlers).
READER_JS = r"""(function(){
var best=null,bestScore=0;
document.querySelectorAll('article, main, div, section').forEach(function(el){
 var t=0;el.querySelectorAll(':scope > p').forEach(function(p){t+=(p.innerText||'').length});
 if(t>bestScore){bestScore=t;best=el}});
if(!best||bestScore<300){best=document.querySelector('article')||document.querySelector('main')||document.body;}
var c=best.cloneNode(true);
c.querySelectorAll('script,style,noscript,iframe,form,nav,aside,footer,header,button,input,select,textarea,svg,object,embed,[aria-hidden="true"]').forEach(function(x){x.remove()});
c.querySelectorAll('*').forEach(function(el){
 if(el.tagName==='IMG'){var ds=el.getAttribute('data-src')||el.getAttribute('data-lazy-src');if(ds&&!el.getAttribute('src'))el.setAttribute('src',ds);}
 Array.from(el.attributes).forEach(function(a){
  var keep=['href','src','alt','title'].indexOf(a.name)>=0;
  if(!keep||/^\s*javascript:/i.test(a.value))el.removeAttribute(a.name);});});
var text=(c.innerText||'');
return JSON.stringify({title:document.title,html:c.innerHTML,site:location.hostname,words:text.split(/\s+/).length});
})()"""

READER_TEMPLATE = """<!doctype html><html><head><meta charset="utf-8"><meta name="nova-page" content="reader"><title>📖 {title}</title>
<style>
 body {{ margin: 0; background: {bg}; color: {fg}; font: {size}px/{line} "{font}", Georgia, serif; }}
 .wrap {{ max-width: {width}px; margin: 0 auto; padding: 56px 24px 120px; }}
 .site {{ color: #6c8cff; font: 600 13px "Segoe UI", sans-serif; letter-spacing: 2px; text-transform: uppercase; }}
 h1.t {{ font: 700 36px/1.25 "Segoe UI", sans-serif; color: {head}; margin: 10px 0 6px; }}
 .meta {{ color: {muted}; font: 14px "Segoe UI", sans-serif; margin-bottom: 36px; }}
 a {{ color: #6c8cff; }}
 img {{ max-width: 100%; height: auto; border-radius: 10px; margin: 12px 0; }}
 h2, h3 {{ font-family: "Segoe UI", sans-serif; color: {head}; }}
 blockquote {{ border-left: 3px solid #6c8cff; margin: 0; padding-left: 18px; opacity: .85; }}
 pre, code {{ background: {code}; border-radius: 6px; padding: 2px 6px; font-size: .8em; white-space: pre-wrap; }}
 table {{ border-collapse: collapse; }} td, th {{ border: 1px solid {code}; padding: 6px; }}
</style></head><body><div class="wrap">
<div class="site">{site}</div><h1 class="t">{title}</h1><div class="meta">{minutes} min read · Reader mode</div>
{content}
</div></body></html>"""
READER_COLORS = {"Dark": ("#17181d", "#dcdde3", "#ffffff", "#8a8d98", "#23252c"),
                 "Sepia": ("#f4ecd8", "#4a3f2f", "#2e2619", "#8a7a62", "#e6dcc3"),
                 "Light": ("#fdfdfd", "#25262b", "#000000", "#6b6e78", "#eef0f4"),
                 "OLED": ("#000001", "#d8d8d8", "#ffffff", "#8b8b93", "#141416")}

FOCUS_TEMPLATE = """<!doctype html><html><head><meta charset="utf-8"><meta name="nova-page" content="focus"><title>🎯 Focus mode</title>
<style>body {{ margin:0; height:100vh; display:flex; flex-direction:column; align-items:center; justify-content:center;
 background: radial-gradient(circle at center, #262a3a, #15161b); color:#e6e6e6; font-family:"Segoe UI",sans-serif; }}
 .icon {{ font-size: 64px; }} h1 {{ color:#8fa6ff; letter-spacing:4px; margin:10px 0; }}
 p {{ color:#9a9ca6; font-size:17px; }} b {{ color:#fff; }}</style></head>
<body><div class="icon">🎯</div><h1>FOCUS MODE</h1>
<p><b>{site}</b> is blocked for <b>{left}</b> more minutes.</p><p>{line}</p></body></html>"""

FOCUS_LINES = ["You've got this. Back to it.", "Future you says thanks.", "Almost there - stay locked in.",
               "One task at a time.", "The scroll can wait. Your goals can't."]


# ---- ❓ Help: every feature, how to use it, and a "Try it" link (nova://… works only on Nova's own pages) ----
HELP_SECTIONS = [
    ("basics", "🧭", "Getting around", "The everyday stuff, plus a few shortcuts that make it fast.", [
        ("Tabs", "Ctrl+T new tab · Ctrl+W close · Ctrl+Shift+T reopen a closed tab · Ctrl+Tab next tab. Right-click a tab to "
                 "float it, sleep it, auto-refresh it, duplicate, mute or close the others.", "", ""),
        ("Search or type an address", "The address bar does both. Ctrl+L jumps to it. Ctrl+Shift+V pastes and goes.", "", ""),
        ("Command palette", "Ctrl+K opens a search box for every command, tab, bookmark, style pack and game. "
                            "If you can't find something, look here.", "Ctrl+K", "palette"),
        ("Bookmarks, history, downloads", "Ctrl+D bookmarks the page · Ctrl+H history · Ctrl+J downloads.", "", ""),
        ("Private tabs", "Ctrl+Shift+N. Nothing is saved: no history, cookies or logins.", "Ctrl+Shift+N", ""),
        ("Split view", "Two pages side by side. Ctrl+\\ turns it on and off.", "Ctrl+\\", "split"),
        ("Float a tab", "Ctrl+Shift+F pops the tab out into a small always-on-top window, great for videos.", "Ctrl+Shift+F", ""),
        ("Reader mode", "F9 shows just the article text, no clutter.", "F9", ""),
        ("Find, zoom, screenshot, PDF", "Ctrl+F find · Ctrl+= / Ctrl+- zoom · Ctrl+Shift+S screenshot · Ctrl+P save as PDF.", "", ""),
        ("Save for later & site notes", "Ctrl+Shift+L keeps a page for later (it shows on the start page). "
                                        "Notes for this site remembers anything you type about a website.", "", ""),
        ("Send to phone", "Shows a QR code of the page so your phone can open it.", "", ""),
    ]),
    ("custom", "🎨", "Make it yours", "Over 260 options. Everything has a switch.", [
        ("Customize", "Ctrl+, or the 🎨 button. Search box at the top finds any option.", "Ctrl+,", "customize"),
        ("Style packs & Surprise me", "One click changes the whole look. 🎲 Surprise me makes a random one. "
                                      "Extra packs unlock as you level up (🎮 Games → 🏆).", "", "customize"),
        ("Live wallpapers", "Constellation, Matrix rain, Aurora, Synthwave, your own picture or video and more: "
                            "Customize → Wallpaper.", "", "customize?cat=Wallpaper"),
        ("Start page widgets", "Clock, weather, to-do, calendar, your teams, anime, game updates and more. "
                               "Press ✎ Layout on the start page to drag them around.", "", "customize?cat=Widgets"),
        ("Export / import your look", "Customize → ⋯ → Export my look. Share the .novatheme file with friends.", "", ""),
        ("Dark websites", "Ctrl+Shift+D makes any website dark.", "Ctrl+Shift+D", ""),
    ]),
    ("speed", "🛡", "Privacy, focus & speed", "Built in, no extensions needed.", [
        ("Ad & tracker blocker", "The 🛡 button shows what was blocked and turns it off for a site.", "", ""),
        ("Tab manager & memory", "Shift+Esc or 🧠 shows every tab, how much memory it uses, and lets you sleep, wake or close it.",
         "Shift+Esc", "tabmanager"),
        ("Memory saver", "Tabs you haven't used for a while go to sleep (💤) and wake up when you click them.", "", ""),
        ("Focus mode", "Blocks distracting sites for a while. Ctrl+K → Focus mode.", "", "focus"),
        ("Screen time", "See which sites you spent time on today.", "", "screentime"),
        ("Clear browsing data", "☰ Menu or Ctrl+K → Clear browsing data.", "", ""),
    ]),
    ("games", "🎮", "Games hub", "Ctrl+Shift+G or the 🎮 button.", [
        ("Play free games", "12 games built in, no download, they even work offline. Your best scores are saved.", "", "games"),
        ("Link games you own", "My games → search, or 🔍 Find games on this PC (Steam & Epic), or ⬇ Import my Steam library "
                               "(needs a free Steam Web API key, Customize → Games & Following). Then ▶ Play starts them "
                               "and you get their patch notes.", "", "games?tab=mine"),
        ("Free games of the week", "What Epic Games Store gives away free right now.", "", "games?tab=free"),
        ("💸 Deals", "Put games on your wishlist. Prices are checked across Steam, Epic, GOG, Humble and more. "
                     "Set a price and get an alert when it drops to it.", "", "games?tab=deals"),
        ("🏆 XP, levels & badges", "Earn XP for playing, browsing, following and more. 32 badges. "
                                    "Levels unlock exclusive style packs.", "", "games?tab=profile"),
    ]),
    ("follow", "📣", "Following hub", "Ctrl+Shift+U or the 📣 button. You choose everything you follow.", [
        ("Teams & leagues", "＋ Follow → pick a league → tap your teams. Live scores, records, next games and alerts.",
         "", "following?tab=manage"),
        ("YouTube, Reddit, websites, topics", "Type @channel, r/subreddit, a website or any topic in ＋ Follow.", "", "following?tab=manage"),
        ("📺 Anime tracker", "Track shows, get an alert for each new episode, see a countdown to the next one, "
                            "and ▶ jump to your next episode on Crunchyroll.", "", "anime"),
        ("Alerts", "Every item has its own Show and 🔔 switch. Turn whole kinds of alerts off in "
                   "Customize → Games & Following.", "", "customize?cat=Games %26 Following"),
    ]),
    ("gamemode", "🕹", "Game Mode", "Your games get the whole PC.", [
        ("What it does", "Sleeps background tabs, mutes and pauses videos, holds alerts until you're done "
                         "(and can minimize the browser).", "", ""),
        ("When it turns on", "By itself when you start a linked game (from the hub, Steam, Epic or the desktop). "
                             "Or press 🕹 / Ctrl+Shift+E. It turns off when the game closes.", "Ctrl+Shift+E", "gamemode"),
        ("Settings", "Customize → Game Mode.", "", "customize?cat=Game Mode"),
    ]),
    ("gestures", "🖱", "Mouse gestures & zapper", "Faster than reaching for buttons.", [
        ("Mouse gestures", "Hold the right mouse button, draw a line, let go. A normal right-click still opens the menu. "
                           "Your gestures are listed below, and every one can be changed.", "", "customize?cat=Gestures %26 Zapper"),
        ("🎯 Zapper", "Alt+Z (or right-click → Zap): click any annoying thing on a site (popups, banners, sidebars) and it stays "
                     "hidden on that site. Ctrl+Z undoes, Esc finishes. Right-click → Un-zap this site brings it all back.",
         "Alt+Z", "zap"),
    ]),
    ("sidebar", "📌", "Sidebar apps", "Chats and music beside your tabs.", [
        ("Open an app", "Click an icon on the side strip (Discord, YouTube Music, Spotify, WhatsApp …). Alt+B shows/hides it. "
                        "They use your normal logins and keep playing while you browse.", "Alt+B", "sidebar"),
        ("Choose apps", "⚙ on the strip, or Customize → Sidebar apps. Add any website as your own app.", "", "customize?cat=Sidebar apps"),
    ]),
    ("voice", "🎤", "Voice control", "Works offline and without Nova. Your voice never leaves this PC.", [
        ("Talk to the browser", "Press 🎤 or Ctrl+Shift+Space and speak. First time: a quick setup downloads the speech model.",
         "Ctrl+Shift+Space", "voice"),
        ("Hands-free", "Customize → Voice control → Always listening. Then say “hey browser, open YouTube”.", "",
         "customize?cat=Voice control"),
        ("What to say", "“open YouTube” · “search for …” · “pause the video” · “skip ahead 30 seconds” · “scroll down” · "
                        "“next tab” · “read this page” · “play tetris” · “what's the Lakers score” · “what can I say”.", "", "voicehelp"),
        ("Accuracy", "Command mode and the Better speech model (Customize → Voice control) keep words from getting mixed up.",
         "", "customize?cat=Voice control"),
    ]),
    ("nova", "✦", "Nova (optional)", "Only if you have Nova (Jarvis.py). Everything else works without her.", [
        ("Nova panel", "Alt+N or ✦ opens her beside your page. She still asks for your unlock code.", "Alt+N", "nova"),
        ("Ask about a page", "Alt+S summarizes the page. Highlight text → right-click → Ask Nova.", "Alt+S", ""),
        ("Turn her off", "Customize → Nova → Nova assistant features.", "", "customize?cat=Nova"),
    ]),
]

HELP_HTML = r"""<!doctype html><html><head><meta charset="utf-8"><meta name="nova-page" content="help"><title>❓ Help</title>
<style>
:root { --a:#6c8cff; --al:#8fa6ff; --bg:#15161b; --card:#23252c; --field:#2b2d34; --line:#3a3d46; --text:#e6e6e6; --dim:#9a9ca6; }
* { box-sizing: border-box; } html { background: var(--bg); scroll-behavior: smooth; }
body { margin: 0; color: var(--text); font: 14px/1.5 "Segoe UI", sans-serif;
       background: radial-gradient(1200px 500px at 50% -200px, color-mix(in srgb, var(--a) 18%, transparent), transparent), var(--bg); }
.wrap { display: grid; grid-template-columns: 230px 1fr; gap: 28px; max-width: 1200px; margin: 0 auto; padding: 26px 28px 80px; }
nav { position: sticky; top: 20px; align-self: start; }
nav a { display: block; color: var(--dim); text-decoration: none; padding: 6px 10px; border-radius: 8px; }
nav a:hover { background: var(--card); color: var(--text); }
h1 { font-size: 28px; margin: 0 0 4px; } .sub { color: var(--dim); margin: 0 0 18px; }
#q { width: 100%; background: var(--field); color: var(--text); border: 1px solid var(--line); border-radius: 12px; padding: 11px 14px;
     font: inherit; font-size: 15px; outline: none; margin-bottom: 8px; } #q:focus { border-color: var(--a); }
.top-actions { display: flex; gap: 8px; flex-wrap: wrap; margin: 6px 0 10px; }
.btn { display: inline-block; background: var(--field); color: var(--text); border: 1px solid var(--line); border-radius: 9px;
       padding: 6px 12px; text-decoration: none; font-size: 13px; white-space: nowrap; }
.btn:hover { border-color: var(--a); } .btn.primary { background: var(--a); border-color: var(--a); color: #fff; }
section { margin-top: 26px; } h2 { font-size: 19px; margin: 0 0 2px; } section > p { color: var(--dim); margin: 0 0 12px; }
.grid { display: grid; gap: 12px; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); }
.card { background: var(--card); border: 1px solid rgba(255,255,255,.06); border-radius: 14px; padding: 14px 16px; display: flex; flex-direction: column; gap: 6px; }
.card b { font-size: 15px; } .card .t { color: #c8cad3; font-size: 13.5px; flex: 1; }
.row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
kbd { background: var(--field); border: 1px solid var(--line); border-bottom-width: 2px; border-radius: 6px; padding: 1px 7px; font: 12px Consolas, monospace; }
table { width: 100%; border-collapse: collapse; background: var(--card); border-radius: 14px; overflow: hidden; }
td { padding: 7px 14px; border-bottom: 1px solid rgba(255,255,255,.05); } td:last-child { text-align: right; }
.cols { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.hide { display: none !important; } .empty { color: var(--dim); padding: 20px; text-align: center; }
@media (max-width: 800px) { .wrap { grid-template-columns: 1fr; } nav { display: none; } .cols { grid-template-columns: 1fr; } }
</style></head><body><div class="wrap"><nav id="nav"></nav><main id="main"></main></div>
<script>
var H = /*HELP*/{};
var r = document.documentElement.style;
Object.keys(H.colors || {}).forEach(function (k) { r.setProperty("--" + k, H.colors[k]); });
function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
var nav = '<a href="#top"><b>❓ Help</b></a>', h = '<a id="top"></a><h1>❓ Nova Browser help</h1><p class="sub">Everything it can do and how to use it. ' +
  'Press <kbd>F1</kbd> any time to come back here.</p><input id="q" placeholder="Search help… (e.g. gestures, anime, voice, dark)" autofocus>' +
  '<div class="top-actions"><a class="btn primary" href="nova://tour">▶ Take the 1-minute tour</a><a class="btn" href="nova://palette">⌘ Command palette</a>' +
  '<a class="btn" href="nova://customize">🎨 Customize</a><a class="btn" href="#keys">⌨ Shortcuts</a></div>';
H.sections.forEach(function (s) {
  nav += '<a href="#' + s.id + '">' + esc(s.emoji) + "  " + esc(s.title) + "</a>";
  h += '<section id="' + s.id + '" data-s><h2>' + esc(s.emoji) + " " + esc(s.title) + "</h2><p>" + esc(s.intro) + '</p><div class="grid">';
  s.items.forEach(function (it) {
    h += '<div class="card" data-text="' + esc((s.title + " " + it.name + " " + it.how).toLowerCase()) + '"><b>' + esc(it.name) + '</b><div class="t">' + esc(it.how) + "</div>" +
         ((it.key || it.act) ? '<div class="row">' + (it.key ? "<kbd>" + esc(it.key) + "</kbd>" : "") + (it.act ? '<a class="btn" href="nova://' + esc(it.act) + '">Try it →</a>' : "") + "</div>" : "") + "</div>";
  });
  h += "</div></section>";
});
nav += '<a href="#keys">⌨  Shortcuts & gestures</a>';
h += '<section id="keys" data-s><h2>⌨ Your shortcuts & gestures</h2><p>These are your current ones. Change any of them in 🎨 Customize.</p><div class="cols"><table>';
H.keys.forEach(function (k) { h += '<tr data-text="' + esc((k[0] + " " + k[1]).toLowerCase()) + '"><td>' + esc(k[0]) + "</td><td>" + (k[1] ? "<kbd>" + esc(k[1]) + "</kbd>" : '<span style="color:var(--dim)">—</span>') + "</td></tr>"; });
h += "</table><table>";
H.gestures.forEach(function (g) { h += '<tr data-text="' + esc(("gesture " + g[1]).toLowerCase()) + '"><td style="font-size:18px">' + esc(g[0]) + "</td><td>" + esc(g[1]) + "</td></tr>"; });
h += '</table></div></section><div id="none" class="empty hide">Nothing found. Try another word, or press Ctrl+K and search the command palette.</div>';
document.getElementById("nav").innerHTML = nav; document.getElementById("main").innerHTML = h;
document.getElementById("q").addEventListener("input", function () {
  var q = this.value.trim().toLowerCase(), any = false;
  document.querySelectorAll("[data-text]").forEach(function (c) { var on = !q || c.dataset.text.indexOf(q) >= 0; c.classList.toggle("hide", !on); if (on && q) any = true; });
  document.querySelectorAll("[data-s]").forEach(function (s) { s.classList.toggle("hide", !!q && !s.querySelector("[data-text]:not(.hide)")); });
  document.getElementById("none").classList.toggle("hide", !q || any);
});
if (location.hash) { var el = document.getElementById(location.hash.slice(1)); if (el) el.scrollIntoView(); }
</script></body></html>"""


def is_help_page(url: QUrl) -> bool:
    return url.isLocalFile() and url.fileName() == HELP_FILE.name


TOUR_PAGES = [
    ("👋", "Welcome to Nova Browser", "Here's a 1-minute tour of what makes it different. You can skip it, and open it again "
                                      "any time from the ❓ button (or F1 → Take the tour).", "", ""),
    ("🔎", "Tabs, search & the command palette", "Type a search or an address at the top. Ctrl+K opens the command palette: "
           "search it for any command, tab, bookmark or game. Right-click a tab for extras like float, sleep and auto-refresh.",
     "⌘ Open the palette", "palette"),
    ("🎨", "Make it yours", "🎨 Customize has 260+ options: style packs, live wallpapers, start page widgets, tab shapes, fonts. "
           "On the start page, press ✎ Layout to drag widgets around.", "🎨 Open Customize", "customize"),
    ("🎮", "Games hub", "12 free games to play right in the browser, updates for games you own, free games of the week, "
           "a deals wishlist with price alerts, and XP & badges that unlock new style packs.", "🎮 Open Games", "games"),
    ("📣", "Following", "Follow teams, leagues, YouTube channels, subreddits, sites and topics: you pick everything. "
           "The 📺 Anime tracker alerts you when new episodes come out.", "📣 Open Following", "following"),
    ("🕹", "Game Mode & the tab manager", "When one of your games starts, Game Mode puts tabs to sleep, mutes them and holds "
           "alerts, then switches off when you're done. Shift+Esc (🧠) shows how much memory each tab uses.",
     "🧠 Open the tab manager", "tabmanager"),
    ("🖱", "Gestures & the zapper", "Hold the right mouse button and draw: ← back, → forward, ↓→ close tab, ↓↑ new tab, ↑↓ reload. "
           "Alt+Z zaps annoying popups and banners off a site for good.", "🖱 See all gestures", "customize?cat=Gestures %26 Zapper"),
    ("📌", "Sidebar apps", "Discord, YouTube Music, WhatsApp and more in a strip beside your tabs, signed in and playing "
           "while you browse. Alt+B shows or hides it.", "📌 Open the sidebar", "sidebar"),
    ("🎤", "Voice control", "Press 🎤 or Ctrl+Shift+Space and say “open YouTube”, “pause the video”, “scroll down” or "
           "“what can I say”. Runs offline on your PC. Turn on hands-free “hey browser” in Customize.", "🎤 Set up voice", "voice"),
    ("❓", "That's it!", "Press F1 or the ❓ button any time for the full help page with every feature and your shortcuts. "
           "Have fun!", "❓ Open the help page", "help"),
]


class TourDialog(QDialog):
    """The welcome tour: one page per big feature, with a button to try each one."""

    def __init__(self, browser):
        super().__init__(browser)
        self.browser = browser
        self.setWindowTitle("Welcome to Nova Browser")
        self.setMinimumSize(560, 380)
        self.i = 0
        lay = QVBoxLayout(self)
        lay.setContentsMargins(30, 26, 30, 20)
        self.icon = QLabel("")
        self.icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon.setStyleSheet("font-size:56px;")
        self.title = QLabel("")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title.setStyleSheet("font-size:22px;font-weight:700;")
        self.text = QLabel("")
        self.text.setWordWrap(True)
        self.text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.text.setStyleSheet(f"font-size:14px;color:{pal('dim')};")
        self.try_btn = QPushButton("")
        self.try_btn.clicked.connect(self.try_it)
        lay.addWidget(self.icon)
        lay.addWidget(self.title)
        lay.addSpacing(6)
        lay.addWidget(self.text, 1)
        lay.addWidget(self.try_btn, 0, Qt.AlignmentFlag.AlignCenter)
        lay.addSpacing(10)
        row = QHBoxLayout()
        self.skip = QPushButton("Skip tour")
        self.skip.clicked.connect(self.close)
        self.dots = QLabel("")
        self.dots.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.back = QPushButton("← Back")
        self.back.clicked.connect(lambda: self.go(-1))
        self.next = QPushButton("Next →")
        self.next.setObjectName("Primary")
        self.next.setDefault(True)
        self.next.clicked.connect(lambda: self.go(1))
        row.addWidget(self.skip)
        row.addStretch()
        row.addWidget(self.dots)
        row.addStretch()
        row.addWidget(self.back)
        row.addWidget(self.next)
        lay.addLayout(row)
        self.show_page()

    def show_page(self):
        icon, title, text, btn, _act = TOUR_PAGES[self.i]
        self.icon.setText(icon)
        self.title.setText(title)
        self.text.setText(text)
        self.try_btn.setText(btn)
        self.try_btn.setVisible(bool(btn))
        self.back.setEnabled(self.i > 0)
        last = self.i == len(TOUR_PAGES) - 1
        self.next.setText("Finish ✓" if last else "Next →")
        self.skip.setVisible(not last)
        self.dots.setText(" ".join("●" if k == self.i else "○" for k in range(len(TOUR_PAGES))))

    def go(self, d):
        if self.i + d >= len(TOUR_PAGES):
            self.close()
            return
        self.i = max(0, self.i + d)
        self.show_page()

    def try_it(self):
        act = TOUR_PAGES[self.i][4]
        if act:
            self.browser.handle_nova_url(QUrl("nova://" + act))

    def closeEvent(self, e):
        self.browser.set_setting("tour_done", True)
        super().closeEvent(e)


def make_script(name, source, all_frames=False, point=QWebEngineScript.InjectionPoint.DocumentReady):
    s = QWebEngineScript()
    s.setName(name)
    s.setSourceCode(source)
    s.setInjectionPoint(point)
    s.setWorldId(QWebEngineScript.ScriptWorldId.ApplicationWorld)
    s.setRunsOnSubFrames(all_frames)
    return s


class NovaPage(QWebEnginePage):
    """A page that knows about Focus mode and full-screen video."""

    def __init__(self, profile, view, browser):
        super().__init__(profile, view)
        self.browser = browser
        self.fullScreenRequested.connect(browser.on_fullscreen_request)
        self.linkHovered.connect(browser.on_link_hovered)

    def javaScriptConsoleMessage(self, level, message, line, source):
        """The zapper (only while you're zapping on this page) reports what you clicked through the console."""
        if getattr(self, "zapping", False) and str(message).startswith("__nova"):
            try:
                self.browser.on_zap_message(self, str(message))
            except Exception as e:
                print("[zapper]", e)

    def acceptNavigationRequest(self, url, nav_type, is_main_frame):
        if url.scheme() == "nova":
            if is_start_page(self.url()) or is_help_page(self.url()):     # only Nova's own pages may use nova:// links
                QTimer.singleShot(0, lambda u=QUrl(url): self.browser.handle_nova_url(u))
            return False
        if (is_main_frame and self.browser.settings.get("https_only") and url.scheme() == "http"
                and url.host() not in ("localhost", "127.0.0.1", "::1") and not url.host().endswith((".localhost", ".test"))):
            secure = QUrl(url)
            secure.setScheme("https")
            QTimer.singleShot(0, lambda: self.setUrl(secure))
            return False
        if is_main_frame and self.browser.focus_blocks(url):
            site, left = host_of(url), self.browser.focus_minutes_left()
            line = FOCUS_LINES[int(time.time()) % len(FOCUS_LINES)]
            page = themed(FOCUS_TEMPLATE.format(site=html.escape(site), left=left, line=line))
            QTimer.singleShot(0, lambda: self.setHtml(page))
            return False
        if is_main_frame:
            self.zapping = False
        if is_main_frame and HUB is not None and getattr(self.browser, "hub", None) is not None:
            try:      # hub pages get a line to the browser; every other page has it removed before it loads
                if HUB.hub_kind_of(url, DATA_DIR):
                    HUB.attach_bridge(self, self.browser.hub)
                else:
                    HUB.detach_bridge(self)
            except Exception as e:
                print("[hubs] bridge:", e)
        return super().acceptNavigationRequest(url, nav_type, is_main_frame)


class GestureFilter(QObject):
    """Mouse gestures: hold the right button, draw, let go. A plain right-click still opens the menu.
    Watches the whole app (web pages sometimes swallow the mouse-up), and also checks the button itself every 15 ms,
    so a gesture always finishes even if the page never tells us you let go."""

    def __init__(self, browser):
        super().__init__(browser)
        self.browser = browser
        self.pts = None
        self.view = None
        self.last_hint = ""
        self.poll = QTimer(self)
        self.poll.setInterval(15)
        self.poll.timeout.connect(self.poll_tick)
        QApplication.instance().installEventFilter(self)

    @staticmethod
    def view_of(obj):
        while obj is not None and not isinstance(obj, WebView):
            try:
                obj = obj.parent()
            except Exception:
                return None
        return obj

    def eventFilter(self, obj, e):
        t = e.type()
        if t not in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease):
            return False
        try:
            if t == QEvent.Type.MouseButtonPress:
                if e.button() == Qt.MouseButton.RightButton:
                    if self.pts is None and self.browser.settings.get("gestures", True) and EX is not None:
                        view = self.view_of(obj)
                        if view is not None:
                            self.begin(view)
                elif self.pts is not None:
                    self.cancel()                         # left click while drawing: forget it
            elif e.button() == Qt.MouseButton.RightButton and self.pts is not None:
                self.finish()
        except Exception:
            self.cancel()
        return False

    def begin(self, view):
        self.view = view
        p = QCursor.pos()
        self.pts = [(p.x(), p.y())]
        self.last_hint = ""
        self.poll.start()

    def poll_tick(self):
        if self.pts is None:
            self.poll.stop()
            return
        p = QCursor.pos()
        if (p.x(), p.y()) != self.pts[-1]:
            self.pts.append((p.x(), p.y()))
            if self.browser.settings.get("gesture_hint", True):
                code = EX.recognize_gesture(self.pts)
                if code and code != self.last_hint:
                    self.last_hint = code
                    self.browser.status(f"🖱  {EX.gesture_arrows(code)}   {self.browser.gesture_label(code)}", 1500)
        if not (QApplication.mouseButtons() & Qt.MouseButton.RightButton):
            self.finish()                                 # you let go (even if the page ate the mouse-up)

    def finish(self):
        """Ends the gesture. Returns the gesture code if it was one (then it runs), else ''."""
        pts, self.pts = self.pts, None
        self.poll.stop()
        if not pts:
            return ""
        p = QCursor.pos()
        pts.append((p.x(), p.y()))
        code = EX.recognize_gesture(pts)
        if code:
            if self.view is not None:
                self.view.gesture_time = time.time()      # so the right-click menu doesn't pop up too
            QTimer.singleShot(0, lambda c=code: self.browser.run_gesture(c))
        return code

    def cancel(self):
        self.pts = None
        self.poll.stop()


class WebView(QWebEngineView):
    """A tab's page view: opens 'new window' links as tabs and adds Nova to the right-click menu."""

    def __init__(self, browser, private=False):
        super().__init__()
        self.browser = browser
        self.private = private
        self.audible = False
        self.setPage(NovaPage(browser.private_profile if private else browser.profile, self, browser))
        self.page().recentlyAudibleChanged.connect(self.on_audible)

    def on_audible(self, audible):
        self.audible = audible
        self.browser.refresh_tab_label(self)

    def createWindow(self, _type):
        return self.browser.new_tab(load=False, private=self.private)

    def contextMenuEvent(self, event):
        g = getattr(self.browser, "gestures", None)
        if g is not None and g.pts is not None and g.finish():
            return                                   # the menu came first, but that right-click was a gesture
        if time.time() - getattr(self, "gesture_time", 0) < 0.8:
            return                                   # that right-click was a gesture
        menu = self.createStandardContextMenu()
        sel = self.selectedText().strip()
        if sel:
            short = sel if len(sel) <= 30 else sel[:28] + "…"
            menu.addSeparator()
            if self.browser.settings.get("nova_selection_menu", True) and self.browser.settings.get("nova_on", True):
                menu.addAction(f"✦  Ask Nova about “{short}”").triggered.connect(
                    lambda: self.browser.ask_nova(f'Explain this: "{sel[:700]}"'))
                menu.addAction("✦  Translate with Nova").triggered.connect(
                    lambda: self.browser.ask_nova(f'Translate this to English: "{sel[:700]}"'))
            menu.addAction(f"🔍  Search for “{short}”").triggered.connect(
                lambda: self.browser.new_tab(to_url(sel[:300]), private=self.private))
        menu.addSeparator()
        menu.addAction("🔖  Save for later   Ctrl+Shift+L").triggered.connect(lambda: self.browser.save_for_later(self))
        if self.browser.tabs.indexOf(self) >= 0:
            menu.addAction("🪟  Float this tab on top   Ctrl+Shift+F").triggered.connect(
                lambda: self.browser.float_tab(self))
        menu.addAction("📖  Reader mode   F9").triggered.connect(self.browser.reader_mode)
        menu.addAction("📸  Screenshot   Ctrl+Shift+S").triggered.connect(self.browser.screenshot)
        if is_web(self.url().toString()):
            if not sel and self.browser.settings.get("nova_selection_menu", True) and self.browser.settings.get("nova_on", True):
                menu.addAction("✦  Nova: summarize this page   Alt+S").triggered.connect(self.browser.summarize_page)
            if self.browser.settings.get("zapper_menu", True) and EX is not None:
                menu.addAction("🎯  Zap something on this page   Alt+Z").triggered.connect(lambda: self.browser.start_zapper(self))
                if EX.zap_host(self.url().host()) in self.browser.zaps:
                    menu.addAction("↩  Un-zap this site").triggered.connect(lambda: self.browser.unzap_site(self))
        menu.aboutToHide.connect(menu.deleteLater)
        menu.popup(event.globalPos())


class BrowserTabs(QObject):
    """Tabs split in two: the tab strip (which can sit in the top row) and the pages (in the window body).
    Offers the same functions the browser used from QTabWidget."""
    currentChanged = pyqtSignal(int)
    tabCloseRequested = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.bar = QTabBar()
        self.bar.setDocumentMode(True)
        self.bar.setExpanding(False)
        self.bar.setDrawBase(False)
        self.bar.setUsesScrollButtons(True)
        self.bar.setElideMode(Qt.TextElideMode.ElideRight)
        self.stack = QStackedWidget()
        self.bar.currentChanged.connect(self._current)
        self.bar.tabCloseRequested.connect(self.tabCloseRequested.emit)
        self.bar.tabMoved.connect(self._moved)

    def _current(self, i):
        if 0 <= i < self.stack.count():
            self.stack.setCurrentIndex(i)
        self.currentChanged.emit(i)

    def _moved(self, a, b):
        w = self.stack.widget(a)
        if w is None:
            return
        self.stack.removeWidget(w)
        self.stack.insertWidget(b, w)
        self.stack.setCurrentIndex(self.bar.currentIndex())

    def addTab(self, widget, text):
        self.stack.addWidget(widget)
        return self.bar.addTab(text)

    def removeTab(self, i):
        w = self.stack.widget(i)
        if w is None:
            return
        self.stack.removeWidget(w)
        self.bar.removeTab(i)
        if self.bar.count():
            self.stack.setCurrentIndex(self.bar.currentIndex())

    def count(self):
        return self.bar.count()

    def widget(self, i):
        return self.stack.widget(i) if 0 <= i < self.stack.count() else None

    def indexOf(self, w):
        return self.stack.indexOf(w)

    def currentIndex(self):
        return self.bar.currentIndex()

    def setCurrentIndex(self, i):
        self.bar.setCurrentIndex(i)
        if 0 <= i < self.stack.count():
            self.stack.setCurrentIndex(i)

    def currentWidget(self):
        return self.stack.currentWidget()

    def tabBar(self):
        return self.bar

    def setTabText(self, i, t):
        self.bar.setTabText(i, t)

    def setTabToolTip(self, i, t):
        self.bar.setTabToolTip(i, t)

    def setTabIcon(self, i, icon):
        self.bar.setTabIcon(i, icon)

    def setTabsClosable(self, on):
        self.bar.setTabsClosable(on)

    def setMovable(self, on):
        self.bar.setMovable(on)


class TitleBar(QWidget):
    """The top row: tabs, a + button, empty space you can drag, and the — ▢ ✕ window buttons."""

    def __init__(self, browser):
        super().__init__()
        self.browser = browser
        self.setObjectName("TitleBar")
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)   # fill the whole row
        row = QHBoxLayout(self)
        row.setContentsMargins(6, 4, 0, 0)
        row.setSpacing(2)
        self.tab_slot = QHBoxLayout()
        self.tab_slot.setContentsMargins(0, 0, 0, 0)
        row.addLayout(self.tab_slot)
        self.plus = QToolButton()
        self.plus.setObjectName("TitlePlus")
        self.plus.setText("+")
        self.plus.setToolTip("New tab")
        self.plus.clicked.connect(lambda: browser.new_tab())
        row.addWidget(self.plus)
        row.addStretch(1)                      # this empty space is where you grab the window
        self.win_buttons = []
        for text, tip, slot, name in (("—", "Minimize", lambda: browser.showMinimized(), "WinBtn"),
                                      ("▢", "Maximize", self.toggle_max, "WinBtn"),
                                      ("✕", "Close", lambda: browser.close(), "WinClose")):
            b = QToolButton()
            b.setObjectName(name)
            b.setText(text)
            b.setToolTip(tip)
            b.clicked.connect(slot)
            row.addWidget(b)
            self.win_buttons.append(b)
        self.max_btn = self.win_buttons[1]
        self.press = None

    def set_window_buttons(self, on):
        for b in self.win_buttons:
            b.setVisible(on)

    def toggle_max(self):
        w = self.browser
        if w.isMaximized():
            w.showNormal()
        else:
            w.showMaximized()

    def update_max_icon(self):
        self.max_btn.setText("❐" if self.browser.isMaximized() else "▢")
        self.max_btn.setToolTip("Restore" if self.browser.isMaximized() else "Maximize")

    # Drag the window by the empty part of the top row (Windows snap still works)
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.press = e.globalPosition().toPoint()
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self.press is not None and e.buttons() & Qt.MouseButton.LeftButton:
            if (e.globalPosition().toPoint() - self.press).manhattanLength() > 4:
                self.press = None
                handle = self.browser.windowHandle()
                if handle is not None:
                    handle.startSystemMove()
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        self.press = None
        super().mouseReleaseEvent(e)

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.toggle_max()
        super().mouseDoubleClickEvent(e)


class EdgeResizer(QObject):
    """Without the Windows frame, this lets you resize the window by dragging its edges."""
    MARGIN = 6

    def __init__(self, win):
        super().__init__(win)
        self.win = win
        self.shape = None

    def set_cursor(self, shape):
        if shape == self.shape:
            return
        if self.shape is not None:
            QApplication.restoreOverrideCursor()
        if shape is not None:
            QApplication.setOverrideCursor(QCursor(shape))
        self.shape = shape

    def eventFilter(self, obj, e):
        t = e.type()
        if t not in (QEvent.Type.MouseMove, QEvent.Type.MouseButtonPress):
            return False
        w = self.win
        if (not (w.windowFlags() & Qt.WindowType.FramelessWindowHint) or w.isMaximized() or w.isFullScreen()
                or not isinstance(obj, QWidget) or obj.window() is not w):
            self.set_cursor(None)
            return False
        p = e.globalPosition().toPoint()
        g = w.frameGeometry()
        m = self.MARGIN
        edges = Qt.Edge(0)
        if p.x() - g.left() < m:
            edges |= Qt.Edge.LeftEdge
        if g.right() - p.x() < m:
            edges |= Qt.Edge.RightEdge
        if p.y() - g.top() < m:
            edges |= Qt.Edge.TopEdge
        if g.bottom() - p.y() < m:
            edges |= Qt.Edge.BottomEdge
        if edges == Qt.Edge(0):
            if t == QEvent.Type.MouseMove and not e.buttons():
                self.set_cursor(None)
            return False
        if t == QEvent.Type.MouseMove and not e.buttons():
            diag1 = (Qt.Edge.LeftEdge | Qt.Edge.TopEdge, Qt.Edge.RightEdge | Qt.Edge.BottomEdge)
            diag2 = (Qt.Edge.RightEdge | Qt.Edge.TopEdge, Qt.Edge.LeftEdge | Qt.Edge.BottomEdge)
            if edges in diag1:
                self.set_cursor(Qt.CursorShape.SizeFDiagCursor)
            elif edges in diag2:
                self.set_cursor(Qt.CursorShape.SizeBDiagCursor)
            elif edges in (Qt.Edge.LeftEdge, Qt.Edge.RightEdge):
                self.set_cursor(Qt.CursorShape.SizeHorCursor)
            else:
                self.set_cursor(Qt.CursorShape.SizeVerCursor)
            return False
        if t == QEvent.Type.MouseButtonPress and e.button() == Qt.MouseButton.LeftButton:
            handle = w.windowHandle()
            if handle is not None:
                handle.startSystemResize(edges)
                return True
        return False


def hide_own_console():
    """Started by double-clicking? Hide the black console window, but never a terminal you opened yourself."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        u32 = ctypes.WinDLL("user32")
        k32.GetConsoleWindow.restype = wintypes.HWND
        k32.OpenProcess.restype = wintypes.HANDLE
        k32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        k32.QueryFullProcessImageNameW.argtypes = (wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                                   ctypes.POINTER(wintypes.DWORD))
        k32.CloseHandle.argtypes = (wintypes.HANDLE,)
        hwnd = k32.GetConsoleWindow()
        if not hwnd:
            return
        pids = (wintypes.DWORD * 32)()
        n = k32.GetConsoleProcessList(pids, 32)
        if n <= 0 or n > 32:
            return
        ours = {"python.exe", "pythonw.exe", "py.exe", "pyw.exe"}
        for pid in pids[:n]:
            h = k32.OpenProcess(0x1000, False, pid)            # PROCESS_QUERY_LIMITED_INFORMATION
            if not h:
                return
            buf = ctypes.create_unicode_buffer(1024)
            size = wintypes.DWORD(1024)
            got = k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size))
            k32.CloseHandle(h)
            if not got or os.path.basename(buf.value).lower() not in ours:
                return                                          # a real terminal (cmd, PowerShell...) is attached: leave it
        u32.ShowWindow(hwnd, 0)                                 # SW_HIDE
    except Exception:
        pass


def round_window_corners(win):
    """Windows 11: rounded corners for the frameless window."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        pref = ctypes.c_int(2)                                  # DWMWCP_ROUND
        ctypes.WinDLL("dwmapi").DwmSetWindowAttribute(ctypes.c_void_p(int(win.winId())), 33,
                                                      ctypes.byref(pref), ctypes.sizeof(pref))
    except Exception:
        pass


class FindBar(QWidget):
    """Ctrl+F: find text on the page."""

    def __init__(self, browser):
        super().__init__()
        self.browser = browser
        self.setObjectName("FindBar")
        row = QHBoxLayout(self)
        row.setContentsMargins(10, 6, 10, 6)
        self.input = QLineEdit()
        self.input.setPlaceholderText("Find on page")
        self.input.textChanged.connect(lambda _: self.find())
        self.input.returnPressed.connect(lambda: self.find())
        self.count = QLabel("")
        prev_btn = QPushButton("▲")
        prev_btn.clicked.connect(lambda: self.find(backward=True))
        next_btn = QPushButton("▼")
        next_btn.clicked.connect(lambda: self.find())
        close_btn = QPushButton("✕")
        close_btn.clicked.connect(self.close_bar)
        row.addWidget(self.input, 1)
        row.addWidget(self.count)
        row.addWidget(prev_btn)
        row.addWidget(next_btn)
        row.addWidget(close_btn)
        esc = QAction(self)
        esc.setShortcut(QKeySequence("Escape"))
        esc.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        esc.triggered.connect(self.close_bar)
        self.addAction(esc)
        self.hide()

    def open_bar(self):
        self.show()
        self.input.setFocus()
        self.input.selectAll()
        if self.input.text():
            self.find()

    def close_bar(self):
        self.browser.current().page().findText("")
        self.count.setText("")
        self.hide()
        self.browser.current().setFocus()

    def find(self, backward=False):
        text = self.input.text()
        flags = QWebEnginePage.FindFlag.FindBackward if backward else QWebEnginePage.FindFlag(0)
        if not text:
            self.browser.current().page().findText("")
            self.count.setText("")
            return

        def done(result):
            try:
                n, i = result.numberOfMatches(), result.activeMatch()
                self.count.setText(f"{i}/{n}" if n else "no matches")
            except Exception:
                pass
        self.browser.current().page().findText(text, flags, done)


class CommandPalette(QDialog):
    """Ctrl+K: type to find any feature, open tab, bookmark or page from history."""

    def __init__(self, browser):
        super().__init__(browser, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.browser = browser
        self.setObjectName("Palette")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.resize(620, 440)
        box = QVBoxLayout(self)
        box.setContentsMargins(12, 12, 12, 12)
        self.input = QLineEdit()
        self.input.setPlaceholderText("Type a command, tab, bookmark or page…  (Enter = go)")
        self.input.textChanged.connect(self.refill)
        self.input.returnPressed.connect(self.run_selected)
        self.input.installEventFilter(self)
        self.list = QListWidget()
        self.list.itemActivated.connect(lambda _: self.run_selected())
        box.addWidget(self.input)
        box.addWidget(self.list, 1)
        self.entries = []
        self.fns = []

    def open_palette(self):
        self.entries = self.browser.palette_entries()
        self.input.clear()
        self.refill("")
        g = self.browser.geometry()
        self.move(g.x() + (g.width() - self.width()) // 2, g.y() + 90)
        self.show()
        self.input.setFocus()

    def refill(self, text):
        words = text.lower().split()
        self.list.clear()
        self.fns = []
        for label, hint, fn in self.entries:
            hay = (label + " " + hint).lower()
            if all(w in hay for w in words):
                self.add_item(f"{label}      {hint}" if hint else label, fn, hint)
                if len(self.fns) >= 60:
                    break
        if text.strip():
            self.add_item(f"↵  Go to / search “{text.strip()}”",
                          lambda t=text.strip(): self.browser.current().setUrl(to_url(t)))
        if self.list.count():
            self.list.setCurrentRow(0)

    def add_item(self, label, fn, tip=""):
        item = QListWidgetItem(label)
        item.setData(Qt.ItemDataRole.UserRole, len(self.fns))
        if tip:
            item.setToolTip(tip)
        self.fns.append(fn)
        self.list.addItem(item)

    def eventFilter(self, obj, event):
        if obj is self.input and event.type() == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Down, Qt.Key.Key_Up):
                row = self.list.currentRow() + (1 if event.key() == Qt.Key.Key_Down else -1)
                self.list.setCurrentRow(max(0, min(self.list.count() - 1, row)))
                return True
            if event.key() == Qt.Key.Key_Escape:
                self.hide()
                return True
        return super().eventFilter(obj, event)

    def run_selected(self):
        item = self.list.currentItem()
        self.hide()
        if item is not None:
            idx = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(idx, int) and 0 <= idx < len(self.fns):
                self.fns[idx]()


# ---------- round two: extra storage ----------
WORKSPACES_FILE = DATA_DIR / "workspaces.json"
READ_LATER_FILE = DATA_DIR / "read_later.json"
NOTES_FILE = DATA_DIR / "site_notes.json"
SCREEN_TIME_FILE = DATA_DIR / "screen_time.json"

# "Video only" in a floating window: the biggest video (or video iframe) fills the window. Run again to undo.
VIDEO_FILL_JS = r"""(function(){
var on=document.getElementById('nova-fill-style');
if(on){on.remove();document.querySelectorAll('[data-nova-fill]').forEach(function(e){e.removeAttribute('data-nova-fill')});return 'off';}
var best=null,area=0;
document.querySelectorAll('video, iframe').forEach(function(e){var r=e.getBoundingClientRect();var a=r.width*r.height;if(a>area){area=a;best=e}});
if(!best||area<20000)return 'none';
best.setAttribute('data-nova-fill','1');
var s=document.createElement('style');s.id='nova-fill-style';
s.textContent='[data-nova-fill]{position:fixed!important;inset:0!important;width:100vw!important;height:100vh!important;'+
 'max-width:none!important;max-height:none!important;z-index:2147483647!important;background:#000!important;object-fit:contain!important;margin:0!important}'+
 'html,body{overflow:hidden!important}';
document.documentElement.appendChild(s);return 'on';})()"""

# Chameleon toolbar: the site's own brand colour (theme-color), if it has one.
THEME_COLOR_JS = r"""(function(){var m=document.querySelector('meta[name="theme-color"]');
return m?(m.getAttribute('content')||''):'';})()"""

QR_TEMPLATE = """<!doctype html><html><head><meta charset="utf-8">
<script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"></script>
<style>body{{margin:0;background:#17181d;color:#e6e6e6;font-family:"Segoe UI",sans-serif;text-align:center;padding:18px}}
#q{{display:inline-block;background:#fff;padding:14px;border-radius:12px}}
p{{color:#9a9ca6;font-size:12px;word-break:break-all}} h3{{color:#8fa6ff;letter-spacing:2px;margin:4px 0 14px}}</style></head>
<body><h3>SCAN WITH YOUR PHONE</h3><div id="q"></div><p id="u"></p>
<script>var u={url};document.getElementById('u').textContent=u;
try{{new QRCode(document.getElementById('q'),{{text:u,width:220,height:220}});}}
catch(e){{document.getElementById('q').textContent='Needs internet to draw the code.';}}</script></body></html>"""


class FloatWindow(QWidget):
    """A tab popped out into a small always-on-top window (picture-in-picture for ANY site)."""

    def __init__(self, browser, view):
        super().__init__(None, Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)
        self.browser = browser
        self.view = view
        self.docking = False
        self.setWindowTitle("✦ " + (getattr(view, "base_title", "") or "Floating tab"))
        self.setStyleSheet(themed("QWidget#FloatBar { background: #1e1f24; } QPushButton { background: #2b2d34; "
                                  "color: #e6e6e6; border: 1px solid #3a3d46; border-radius: 6px; padding: 3px 9px; }"
                                  "QPushButton:hover { border-color: #6c8cff; }"))
        col = QVBoxLayout(self)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)
        bar = QWidget()
        bar.setObjectName("FloatBar")
        row = QHBoxLayout(bar)
        row.setContentsMargins(6, 4, 6, 4)
        fill = QPushButton("🎬 Video only")
        fill.setToolTip("Make the video fill this window (click again to undo)")
        fill.clicked.connect(lambda: self.view.page().runJavaScript(VIDEO_FILL_JS))
        dock = QPushButton("⤓ Back to tabs")
        dock.clicked.connect(self.close)
        row.addWidget(fill)
        row.addStretch()
        row.addWidget(dock)
        col.addWidget(bar)
        col.addWidget(view, 1)
        view.show()
        self.resize(560, 360)
        scr = QApplication.primaryScreen().availableGeometry()
        self.move(scr.right() - self.width() - 24, scr.bottom() - self.height() - 48)

    def closeEvent(self, event):
        if not self.docking:
            self.docking = True
            self.browser.dock_float(self)
        super().closeEvent(event)


class SplitPane(QWidget):
    """Split view: a second page side by side with your tabs."""

    def __init__(self, browser):
        super().__init__()
        self.browser = browser
        col = QVBoxLayout(self)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)
        top = QWidget()
        top.setObjectName("FindBar")
        row = QHBoxLayout(top)
        row.setContentsMargins(6, 4, 6, 4)
        self.address = QLineEdit()
        self.address.setPlaceholderText("Split view: search or type an address")
        self.address.returnPressed.connect(lambda: self.view.setUrl(to_url(self.address.text())))
        swap = QPushButton("⇄")
        swap.setToolTip("Open this page as a normal tab")
        swap.clicked.connect(lambda: browser.new_tab(self.view.url()))
        close = QPushButton("✕")
        close.setToolTip("Close split view (Ctrl+\\)")
        close.clicked.connect(browser.toggle_split)
        row.addWidget(self.address, 1)
        row.addWidget(swap)
        row.addWidget(close)
        col.addWidget(top)
        self.view = WebView(browser)
        self.view.base_title = "Split view"
        self.view.urlChanged.connect(
            lambda u: self.address.setText("" if is_start_page(u) else u.toString()))
        col.addWidget(self.view, 1)


class ScreenTimeDialog(QDialog):
    def __init__(self, browser, data):
        super().__init__(browser)
        self.setWindowTitle("Screen time")
        self.resize(520, 560)
        box = QVBoxLayout(self)
        view = QTextBrowser()
        view.setStyleSheet("QTextBrowser { background: #17181d; border: none; color: #e6e6e6; }")
        box.addWidget(view)
        today = time.strftime("%Y-%m-%d")
        week_days = [time.strftime("%Y-%m-%d", time.localtime(time.time() - d * 86400)) for d in range(7)]

        def fmt(sec):
            sec = int(sec)
            return f"{sec // 3600}h {sec % 3600 // 60:02d}m" if sec >= 3600 else f"{sec // 60}m {sec % 60:02d}s"

        def block(title, totals):
            items = sorted(totals.items(), key=lambda kv: -kv[1])[:10]
            total = sum(totals.values())
            top = items[0][1] if items else 1
            rows = "".join(
                f'<tr><td style="padding:4px 10px 4px 0;color:#c8cad3;">{html.escape(h)}</td>'
                f'<td width="55%"><div style="background:#6c8cff;height:10px;width:{max(2, int(100 * s / top))}%;'
                f'border-radius:5px;"></div></td><td style="padding-left:10px;color:#9a9ca6;">{fmt(s)}</td></tr>'
                for h, s in items) or '<tr><td style="color:#777;">Nothing yet.</td></tr>'
            return (f'<h3 style="color:#8fa6ff;letter-spacing:2px;margin:18px 0 4px;">{title}</h3>'
                    f'<div style="color:#fff;font-size:22px;margin-bottom:8px;">{fmt(total)}</div>'
                    f'<table width="100%">{rows}</table>')

        week = {}
        for d in week_days:
            for h, s in data.get(d, {}).items():
                week[h] = week.get(h, 0) + s
        view.setHtml(themed(block("TODAY", data.get(today, {})) + block("LAST 7 DAYS", week) +
                            '<p style="color:#6b6e78;font-size:11px;margin-top:20px;">Counted only while Nova Browser '
                            'is the window you are using. Private tabs are never counted. Saved only on this PC.</p>'))


class QRDialog(QDialog):
    def __init__(self, browser, url):
        super().__init__(browser)
        self.setWindowTitle("Send to phone")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.resize(320, 400)
        box = QVBoxLayout(self)
        box.setContentsMargins(0, 0, 0, 0)
        self.view = QWebEngineView()
        self.view.setPage(QWebEnginePage(browser.private_profile, self.view))
        self.view.setHtml(themed(QR_TEMPLATE.format(url=json.dumps(url))))
        box.addWidget(self.view)


CUSTOMIZE_STYLE = """
#Customize { background: #17181d; }
#Customize QListWidget { background: #1e1f24; border: none; color: #c8cad3; font-size: 13px; outline: none; padding: 6px; }
#Customize QListWidget::item { padding: 8px 10px; border-radius: 6px; }
#Customize QListWidget::item:selected { background: #6c8cff; color: #ffffff; }
#Customize QScrollArea, #Customize #Rows { background: #17181d; border: none; }
#Customize QLabel { color: #e6e6e6; }
#Customize QLabel#Section { color: #8fa6ff; font-size: 16px; font-weight: 600; letter-spacing: 1px; padding: 10px 0 2px; }
#Customize QLabel#Hint { color: #8a8d98; font-size: 11px; }
#Customize QComboBox, #Customize QSpinBox, #Customize QKeySequenceEdit, #Customize QLineEdit {
    background: #2b2d34; color: #e6e6e6; border: 1px solid #3a3d46; border-radius: 6px; padding: 4px 8px; min-height: 22px; }
#Customize QComboBox QAbstractItemView { background: #26282e; color: #e6e6e6; selection-background-color: #6c8cff; }
#Customize QPushButton { background: #2b2d34; color: #e6e6e6; border: 1px solid #3a3d46; border-radius: 6px; padding: 5px 12px; }
#Customize QPushButton:hover { border-color: #6c8cff; }
#Customize QPushButton#Primary { background: #6c8cff; color: #ffffff; border: none; font-weight: 600; }
#Customize QPushButton#Reset { background: transparent; border: none; color: #8a8d98; padding: 2px 6px; }
#Customize QPushButton#Reset:hover { color: #ffffff; }
#Customize QCheckBox { color: #e6e6e6; spacing: 8px; }
#Customize QCheckBox::indicator { width: 34px; height: 18px; border-radius: 9px; background: #3a3d46; }
#Customize QCheckBox::indicator:checked { background: #6c8cff; }
#Customize #Row { border-bottom: 1px solid #23252c; }
"""


class Toast(QFrame):
    """A small alert in the bottom-right corner of the browser. Click it to open what it's about."""

    def __init__(self, browser, icon, title, body, url, hub):
        super().__init__(browser)
        self.browser, self.url, self.hub = browser, url, hub
        self.setObjectName("Toast")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 10, 6, 10)
        lay.setSpacing(10)
        ic = QLabel(icon)
        ic.setObjectName("ToastIcon")
        txt = QLabel(f"<b>{html.escape(title)}</b><br><span style='color:{pal('dim')}'>{html.escape(body)}</span>")
        txt.setTextFormat(Qt.TextFormat.RichText)
        txt.setWordWrap(True)
        x = QToolButton()
        x.setText("✕")
        x.clicked.connect(self.dismiss)
        lay.addWidget(ic, 0, Qt.AlignmentFlag.AlignTop)
        lay.addWidget(txt, 1)
        lay.addWidget(x, 0, Qt.AlignmentFlag.AlignTop)
        self.setFixedWidth(370)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        QTimer.singleShot(9000, self.dismiss)

    def mousePressEvent(self, e):
        if self.url:
            self.browser.new_tab(QUrl(self.url), private=False)
        else:
            kind, _, tab = str(self.hub).partition(":")
            self.browser.open_hub(kind, tab or None)
        self.dismiss()

    def dismiss(self):
        if self in self.browser.toasts:
            self.browser.toasts.remove(self)
            self.hide()
            self.deleteLater()
            self.browser.place_toasts()


class VoiceBubble(QFrame):
    """The little 🎤 bar at the bottom of the window: shows what the browser heard and what it did."""

    def __init__(self, browser):
        super().__init__(browser)
        self.browser = browser
        self.setObjectName("VoiceBubble")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 8, 16, 8)
        lay.setSpacing(10)
        self.icon = QLabel("🎤")
        self.icon.setObjectName("VoiceIcon")
        self.text = QLabel("")
        self.text.setObjectName("VoiceText")
        self.meter = QProgressBar()
        self.meter.setObjectName("VoiceMeter")
        self.meter.setTextVisible(False)
        self.meter.setRange(0, 100)
        self.meter.setFixedSize(46, 6)
        lay.addWidget(self.icon)
        lay.addWidget(self.text, 1)
        lay.addWidget(self.meter)
        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.hide)
        self.hide()

    def show_msg(self, icon, text, listening=False, ms=0):
        if not self.browser.settings.get("voice_bubble", True) and not listening:
            self.hide()
            return
        self.icon.setText(icon)
        self.text.setText(text if len(text) <= 110 else text[:108] + "…")
        self.meter.setVisible(listening)
        self.setProperty("live", listening)
        self.style().unpolish(self)
        self.style().polish(self)
        self.adjustSize()
        self.setFixedWidth(min(max(320, self.sizeHint().width()), max(320, self.browser.width() - 80)))
        self.place()
        self.show()
        self.raise_()
        if ms:
            self.hide_timer.start(ms)
        else:
            self.hide_timer.stop()

    def set_level(self, v):
        self.meter.setValue(int(max(0.0, min(1.0, v)) * 100))

    def place(self):
        b = self.browser
        bottom = b.height() - (b.statusBar().height() if b.statusBar().isVisible() else 0) - 18
        self.move((b.width() - self.width()) // 2, bottom - self.height())


class VoiceSetup(QDialog):
    """One-time setup for the browser's own voice control (two free add-ons + a 40 MB speech model)."""

    def __init__(self, browser):
        super().__init__(browser)
        self.browser = browser
        self.setWindowTitle("🎤 Set up voice control")
        self.setMinimumWidth(560)
        self.proc = None
        self.reply = None
        lay = QVBoxLayout(self)
        intro = QLabel("<b style='font-size:15px'>Talk to Nova Browser</b><br>"
                       "Voice control runs completely on this PC: your voice is never sent anywhere, and it works "
                       "without Nova and without internet (after this setup).")
        intro.setWordWrap(True)
        lay.addWidget(intro)
        self.step1 = QLabel("")
        self.step1.setWordWrap(True)
        self.btn1 = QPushButton("Install the voice add-ons")
        self.btn1.clicked.connect(self.install_addons)
        self.step2 = QLabel("")
        self.step2.setWordWrap(True)
        name, mb = EX.VOSK_MODELS.get(browser.settings.get("voice_model"), EX.VOSK_MODELS["Small (40 MB, fastest)"])
        self.model_name = name
        self.btn2 = QPushButton(f"Download the speech model ({mb} MB)")
        self.btn2.clicked.connect(self.download_model)
        self.bar = QProgressBar()
        self.bar.hide()
        self.done = QLabel("")
        self.done.setWordWrap(True)
        for w in (self.step1, self.btn1, self.step2, self.btn2, self.bar, self.done):
            lay.addWidget(w)
        row = QHBoxLayout()
        self.test_btn = QPushButton("🎤 Try it now")
        self.test_btn.setObjectName("Primary")
        self.test_btn.clicked.connect(lambda: (self.close(), browser.start_listening()))
        close = QPushButton("Close")
        close.clicked.connect(self.close)
        row.addStretch()
        row.addWidget(self.test_btn)
        row.addWidget(close)
        lay.addLayout(row)
        self.timer = QTimer(self)
        self.timer.setInterval(800)
        self.timer.timeout.connect(self.check_install)
        self.refresh()

    def refresh(self):
        missing = EX.voice_addons_missing()
        model = EX.find_model(VOICE_DIR, self.model_name)
        exact = bool(model) and os.path.basename(model) == self.model_name
        if missing:
            if FROZEN:
                self.step1.setText("❌ <b>1.</b> The voice add-ons aren't in this copy of the app. Run the new "
                                   "<b>build_app.bat</b> again to rebuild it with them.")
                self.btn1.hide()
            else:
                self.step1.setText(f"❌ <b>1.</b> Two free add-ons are needed: <code>{', '.join(missing)}</code> "
                                   "(speech recognition + microphone).")
                self.btn1.setVisible(self.proc is None)
        else:
            self.step1.setText("✅ <b>1.</b> Voice add-ons installed.")
            self.btn1.hide()
        if model and exact:
            self.step2.setText("✅ <b>2.</b> Speech model ready.")
            self.btn2.hide()
        elif model:
            self.step2.setText("✅ <b>2.</b> A speech model is ready. The one you picked in Customize (more accurate) "
                               "isn't downloaded yet, so the other one is used until you get it:")
            self.btn2.setVisible(self.reply is None)
        else:
            self.step2.setText("❌ <b>2.</b> The English speech model (free, from alphacephei.com) needs downloading once.")
            self.btn2.setVisible(self.reply is None)
        ready = not missing and bool(model)
        self.test_btn.setEnabled(ready)
        self.done.setText("<b>All set!</b> Press 🎤 (or Ctrl+Shift+Space) and say something like “open YouTube” or "
                          "“what can I say”. Want hands-free? 🎨 Customize → Voice control → always listening."
                          if ready else "")

    def install_addons(self):
        py = Path(sys.executable)
        if py.name.lower() == "pythonw.exe" and py.with_name("python.exe").exists():
            py = py.with_name("python.exe")
        try:
            self.proc = subprocess.Popen([str(py), "-m", "pip", "install", "--disable-pip-version-check", "vosk", "sounddevice"],
                                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except OSError as e:
            self.step1.setText(f"❌ Couldn't run pip: {e}. Open a terminal and run: pip install vosk sounddevice")
            return
        self.btn1.hide()
        self.step1.setText("⏳ <b>1.</b> Installing the voice add-ons… (about a minute)")
        self.timer.start()

    def check_install(self):
        if self.proc is None or self.proc.poll() is None:
            return
        code = self.proc.returncode
        self.proc = None
        self.timer.stop()
        import importlib
        importlib.invalidate_caches()
        self.refresh()
        if code != 0 and EX.voice_addons_missing():
            self.step1.setText("❌ The install didn't work. Open a terminal and run:  pip install vosk sounddevice")

    def download_model(self):
        self.btn2.hide()
        self.bar.show()
        self.bar.setValue(0)
        self.step2.setText("⏳ <b>2.</b> Downloading the speech model…")
        req = QNetworkRequest(QUrl(EX.model_url(self.model_name)))
        req.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute,
                         QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy)
        self.reply = self.browser.net.get(req)
        self.reply.downloadProgress.connect(lambda got, total: self.bar.setValue(int(got * 100 / total)) if total > 0 else None)
        self.reply.finished.connect(self.model_downloaded)

    def model_downloaded(self):
        r, self.reply = self.reply, None
        self.bar.hide()
        if r.error() != QNetworkReply.NetworkError.NoError:
            self.step2.setText(f"❌ Download failed: {r.errorString()}. Check your internet and try again.")
            self.btn2.show()
            r.deleteLater()
            return
        data = bytes(r.readAll())
        r.deleteLater()
        VOICE_DIR.mkdir(parents=True, exist_ok=True)
        zpath = VOICE_DIR / "model.zip"
        try:
            zpath.write_bytes(data)
            self.step2.setText("⏳ <b>2.</b> Unpacking…")
            QApplication.processEvents()
            EX.unpack_model(str(zpath), str(VOICE_DIR))
        except Exception as e:
            self.step2.setText(f"❌ Couldn't unpack the model: {e}")
            self.btn2.show()
            return
        finally:
            try:
                zpath.unlink()
            except OSError:
                pass
        self.refresh()
        self.browser.apply_voice()

    def closeEvent(self, e):
        self.timer.stop()
        super().closeEvent(e)


class TabManager(QDialog):
    """🧠 Every tab, what it's doing and how much memory it uses. Sleep, wake or close from here."""

    def __init__(self, browser):
        super().__init__(browser)
        self.browser = browser
        self.setWindowTitle("🧠 Tab manager")
        self.resize(820, 520)
        lay = QVBoxLayout(self)
        self.head = QLabel("")
        self.head.setTextFormat(Qt.TextFormat.RichText)
        self.head.setWordWrap(True)
        lay.addWidget(self.head)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Tab", "Status", "Memory", ""])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for c in (1, 2, 3):
            hh.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        lay.addWidget(self.table, 1)
        row = QHBoxLayout()
        sleep_all = QPushButton("💤 Sleep all background tabs")
        sleep_all.clicked.connect(self.sleep_all)
        self.gm_btn = QPushButton("")
        self.gm_btn.clicked.connect(lambda: (browser.toggle_game_mode(), self.refresh()))
        close = QPushButton("Close")
        close.clicked.connect(self.close)
        row.addWidget(sleep_all)
        row.addWidget(self.gm_btn)
        row.addStretch()
        row.addWidget(close)
        lay.addLayout(row)
        self.timer = QTimer(self)
        self.timer.setInterval(2500)
        self.timer.timeout.connect(self.refresh)
        self.timer.start()
        self.refresh()

    def sleep_all(self):
        n = sum(1 for v in self.browser.views() if not getattr(v, "asleep", False) and self.browser.sleep_tab(v, quiet=True))
        self.browser.status(f"💤 Put {n} tab{'s' if n != 1 else ''} to sleep.")
        self.refresh()

    def refresh(self):
        b = self.browser
        total, per = EX.browser_memory() if EX else (None, {})
        views = b.views()
        pids = {}
        for v in views:
            try:
                pid = int(v.page().renderProcessPid())
            except Exception:
                pid = 0
            pids[id(v)] = pid
        shared = {}
        for p in pids.values():
            shared[p] = shared.get(p, 0) + 1
        asleep = sum(1 for v in views if getattr(v, "asleep", False))
        self.head.setText(f"<b style='font-size:15px'>Nova Browser is using {EX.fmt_bytes(total) if EX else '–'}</b>"
                          f"<span style='color:{pal('dim')}'>  ·  {len(views)} tabs, {asleep} asleep  ·  "
                          f"{len(per)} processes  ·  the browser itself: {EX.fmt_bytes(per.get(os.getpid())) if EX else '–'}</span>")
        self.gm_btn.setText("🕹 Turn Game Mode off" if b.game_mode else "🕹 Game Mode")
        self.table.setRowCount(len(views))
        for r, v in enumerate(views):
            title = (getattr(v, "base_title", "") or v.url().toString() or "New Tab")[:90]
            item = QTableWidgetItem(("🕶 " if v.private else "") + title)
            item.setToolTip(v.url().toString())
            self.table.setItem(r, 0, item)
            if getattr(v, "asleep", False):
                st = "💤 Asleep"
            elif v is b.current():
                st = "👁 Open now"
            elif v.page().isAudioMuted():
                st = "🔇 Muted"
            elif v.audible:
                st = "🔊 Playing"
            else:
                st = "Awake"
            self.table.setItem(r, 1, QTableWidgetItem(st))
            pid = pids[id(v)]
            if getattr(v, "asleep", False) or not pid:
                mem = "–"
            else:
                mem = EX.fmt_bytes(per.get(pid)) if EX else "–"
                if shared.get(pid, 0) > 1:
                    mem += f"  (shared by {shared[pid]} tabs)"
            self.table.setItem(r, 2, QTableWidgetItem(mem))
            cell = QWidget()
            cl = QHBoxLayout(cell)
            cl.setContentsMargins(4, 0, 4, 0)
            go = QPushButton("Open")
            go.clicked.connect(lambda _=False, view=v: (b.tabs.setCurrentWidget(view) if hasattr(b.tabs, "setCurrentWidget")
                                                        else b.tabs.setCurrentIndex(b.tabs.indexOf(view)), self.refresh()))
            zz = QPushButton("Sleep")
            zz.setEnabled(not getattr(v, "asleep", False) and v is not b.current())
            zz.clicked.connect(lambda _=False, view=v: (b.sleep_tab(view), self.refresh()))
            x = QPushButton("✕")
            x.setFixedWidth(30)
            x.clicked.connect(lambda _=False, view=v: (b.close_tab(b.tabs.indexOf(view)), self.refresh()))
            for w in (go, zz, x):
                cl.addWidget(w)
            self.table.setCellWidget(r, 3, cell)

    def closeEvent(self, e):
        self.timer.stop()
        super().closeEvent(e)


class SideView(QWebEngineView):
    """A sidebar app's page. Links that open new windows go to normal tabs."""

    def __init__(self, browser):
        super().__init__()
        self.browser = browser
        self.setPage(QWebEnginePage(browser.profile, self))     # same logins as your normal tabs

    def createWindow(self, _type):
        return self.browser.new_tab(load=False, private=False)


class SidePanel(QWidget):
    def __init__(self, browser, app):
        super().__init__()
        self.app = app
        aid, name, icon, url = app
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        head = QWidget()
        head.setObjectName("SideHead")
        hl = QHBoxLayout(head)
        hl.setContentsMargins(10, 4, 4, 4)
        title = QLabel(f"{icon}  {name}")
        title.setStyleSheet("font-weight:600;")
        hl.addWidget(title)
        hl.addStretch()
        self.view = SideView(browser)
        for text, tip, fn in (("←", "Back", lambda: self.view.back()), ("⟳", "Reload", lambda: self.view.reload()),
                              ("⌂", "Go to the app's home", lambda: self.view.setUrl(QUrl(url))),
                              ("↗", "Open in a tab", lambda: browser.new_tab(QUrl(self.view.url()), private=False)),
                              ("✕", "Hide", browser.hide_sidebar)):
            bt = QToolButton()
            bt.setText(text)
            bt.setToolTip(tip)
            bt.setAutoRaise(True)
            bt.clicked.connect(fn)
            hl.addWidget(bt)
        lay.addWidget(head)
        lay.addWidget(self.view, 1)
        self.view.setUrl(QUrl(url))


class CustomizeDialog(QDialog):
    """⚙ Customize: every option, searchable, applied live."""

    def __init__(self, browser):
        super().__init__(browser)
        self.browser = browser
        self.setObjectName("Customize")
        self.setWindowTitle("Customize Nova Browser")
        self.resize(980, 720)
        self.setStyleSheet(themed(CUSTOMIZE_STYLE))
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        top = QWidget()
        tr = QHBoxLayout(top)
        tr.setContentsMargins(14, 12, 14, 10)
        title = QLabel(f"🎨  Customize   <span style='color:{pal('dim2')};font-size:12px;'>{len(OPTIONS)} options</span>")
        title.setObjectName("Section")
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search all options…  (e.g. tab, wallpaper, clock, font)")
        self.search.textChanged.connect(self.show_rows)
        packs = QPushButton("✨ Style packs")
        pmenu = QMenu(packs)
        for name in STYLE_PACKS:
            pmenu.addAction(name).triggered.connect(lambda _=False, n=name: self.apply_pack(n))
        pmenu.aboutToShow.connect(lambda m=pmenu: browser.add_reward_packs(m, self.apply_pack))
        packs.setMenu(pmenu)
        surprise = QPushButton("🎲 Surprise me")
        surprise.setObjectName("Primary")
        surprise.clicked.connect(lambda: (browser.surprise_me(), self.refresh()))
        more = QPushButton("⋯")
        mmenu = QMenu(more)
        mmenu.addAction("💾  Export my look (.novatheme)…").triggered.connect(self.export_theme)
        mmenu.addAction("📂  Import a look…").triggered.connect(self.import_theme)
        mmenu.addSeparator()
        mmenu.addAction("↺  Reset this section").triggered.connect(self.reset_section)
        mmenu.addAction("↺  Reset everything").triggered.connect(self.reset_all)
        more.setMenu(mmenu)
        tr.addWidget(title)
        tr.addWidget(self.search, 1)
        tr.addWidget(packs)
        tr.addWidget(surprise)
        tr.addWidget(more)
        outer.addWidget(top)

        body = QSplitter(Qt.Orientation.Horizontal)
        self.cats = QListWidget()
        self.cats.setFixedWidth(210)
        for c in CATEGORIES + ["Custom widgets", "Site styles (CSS)"]:
            self.cats.addItem(c)
        self.cats.currentRowChanged.connect(lambda _: (self.search.clear() if self.search.text() else None, self.refresh()))
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        body.addWidget(self.cats)
        body.addWidget(self.scroll)
        body.setStretchFactor(1, 1)
        outer.addWidget(body, 1)
        self.cats.setCurrentRow(0)

    def refresh(self):
        QTimer.singleShot(0, self.show_rows)   # rebuild after the click that asked for it has finished

    # ---------- building rows ----------
    def show_rows(self, *_):
        q = self.search.text().strip().lower()
        cat = self.cats.currentItem().text() if self.cats.currentItem() else CATEGORIES[0]
        host = QWidget()
        host.setObjectName("Rows")
        col = QVBoxLayout(host)
        col.setContentsMargins(22, 10, 22, 22)
        col.setSpacing(0)
        if not q and cat == "Custom widgets":
            self.custom_widgets_page(col)
        elif not q and cat == "Site styles (CSS)":
            self.site_css_page(col)
        else:
            shown = [o for o in OPTIONS if (q and (q in o["label"].lower() or q in o["cat"].lower() or q in o["key"]))
                     or (not q and o["cat"] == cat)]
            head = QLabel(f"Results for “{self.search.text()}” ({len(shown)})" if q else cat)
            head.setObjectName("Section")
            col.addWidget(head)
            if cat == "Keyboard shortcuts" and not q:
                hint = QLabel("Click a box and press the new keys. Clear it to remove a shortcut.")
                hint.setObjectName("Hint")
                col.addWidget(hint)
            last_cat = None
            for o in shown:
                if q and o["cat"] != last_cat:
                    sub = QLabel(o["cat"])
                    sub.setObjectName("Hint")
                    col.addWidget(sub)
                    last_cat = o["cat"]
                col.addWidget(self.make_row(o))
            if not shown:
                col.addWidget(QLabel("No options match that."))
        col.addStretch(1)
        self.scroll.setWidget(host)

    def make_row(self, o):
        row = QWidget()
        row.setObjectName("Row")
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 8, 0, 8)
        key, kind, val = o["key"], o["kind"], self.browser.settings.get(o["key"], o["default"])
        label = QLabel(o["label"])
        label.setWordWrap(True)
        h.addWidget(label, 1)
        set_ = lambda v, k=key: self.browser.set_option(k, v)

        if kind == "bool":
            w = QCheckBox()
            w.setChecked(bool(val))
            w.toggled.connect(lambda c: set_(bool(c)))
        elif kind == "choice":
            w = QComboBox()
            w.addItems(o["choices"])
            w.setCurrentText(str(val))
            w.setMinimumWidth(200)
            w.currentTextChanged.connect(lambda t: set_(t))
        elif kind == "int":
            w = QSpinBox()
            w.setRange(o.get("min", 0), o.get("max", 100))
            w.setSuffix(o.get("suffix", ""))
            w.setValue(int(val))
            w.setMinimumWidth(130)
            w.setKeyboardTracking(False)
            w.valueChanged.connect(lambda v: set_(int(v)))
        elif kind == "color":
            w = QPushButton(str(val))
            self.paint_swatch(w, str(val))
            w.clicked.connect(lambda _=False, b=w, k=key: self.pick_color(b, k))
        elif kind == "text":
            w = QLineEdit(str(val))
            w.setMinimumWidth(280)
            w.editingFinished.connect(lambda e=w: set_(e.text()))
        elif kind == "multiline":
            w = QPushButton("Edit…" + ("  ✓" if val else ""))
            w.clicked.connect(lambda _=False, k=key, l=o["label"]: self.edit_multiline(k, l))
        elif kind in ("file", "folder"):
            w = QWidget()
            hl = QHBoxLayout(w)
            hl.setContentsMargins(0, 0, 0, 0)
            e = QLineEdit(str(val))
            e.setMinimumWidth(240)
            e.setPlaceholderText("No file chosen" if kind == "file" else "No folder chosen")
            e.editingFinished.connect(lambda e=e: set_(e.text().strip()))
            b = QPushButton("Browse…")
            b.clicked.connect(lambda _=False, e=e, k=key, kd=kind, f=o.get("filter", ""): self.browse(e, k, kd, f))
            hl.addWidget(e)
            hl.addWidget(b)
        elif kind == "key":
            w = QWidget()
            hl = QHBoxLayout(w)
            hl.setContentsMargins(0, 0, 0, 0)
            e = QKeySequenceEdit(QKeySequence(str(val)))
            e.setMinimumWidth(170)
            e.editingFinished.connect(lambda e=e: set_(e.keySequence().toString()))
            clear = QPushButton("✕")
            clear.setToolTip("Remove this shortcut")
            clear.clicked.connect(lambda _=False, e=e: (e.clear(), set_("")))
            hl.addWidget(e)
            hl.addWidget(clear)
        else:
            w = QLabel(str(val))
        h.addWidget(w)
        reset = QPushButton("↺")
        reset.setObjectName("Reset")
        reset.setToolTip(f"Back to default ({o['default'] if o['default'] != '' else 'empty'})")
        reset.clicked.connect(lambda _=False, k=key: (self.browser.set_option(k, OPTION_BY_KEY[k]["default"]), self.refresh()))
        h.addWidget(reset)
        return row

    def paint_swatch(self, btn, color):
        btn.setText(color)
        btn.setStyleSheet(f"background: {color}; color: {'#000' if QColor(color).lightness() > 150 else '#fff'};"
                          f" border: 1px solid {pal('border')}; border-radius: 6px; padding: 5px 14px;")

    def pick_color(self, btn, key):
        c = QColorDialog.getColor(QColor(self.browser.settings.get(key, "#6c8cff")), self, "Pick a colour")
        if c.isValid():
            self.browser.set_option(key, c.name())
            self.paint_swatch(btn, c.name())
            if key in ("custom_accent",) or OPTION_BY_KEY[key]["apply"] == "chrome":
                self.setStyleSheet(themed(CUSTOMIZE_STYLE))

    def browse(self, edit, key, kind, flt):
        if kind == "folder":
            path = QFileDialog.getExistingDirectory(self, "Choose a folder", edit.text() or str(Path.home()))
        else:
            path, _ = QFileDialog.getOpenFileName(self, "Choose a file", edit.text() or str(Path.home()), flt or "All files (*)")
        if path:
            edit.setText(path)
            self.browser.set_option(key, path)

    def edit_multiline(self, key, label):
        text, ok = QInputDialog.getMultiLineText(self, "Edit", label, self.browser.settings.get(key, ""))
        if ok:
            self.browser.set_option(key, text)
            self.refresh()

    # ---------- custom widgets ----------
    def custom_widgets_page(self, col):
        head = QLabel("Custom widgets")
        head.setObjectName("Section")
        col.addWidget(head)
        hint = QLabel("Make your own start page widgets: a text card, a group of links, a live website, or your own HTML.")
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        col.addWidget(hint)
        items = self.browser.settings.get("custom_widgets") or []
        for i, cw in enumerate(items):
            row = QWidget()
            row.setObjectName("Row")
            h = QHBoxLayout(row)
            h.setContentsMargins(0, 8, 0, 8)
            h.addWidget(QLabel(f"{cw.get('title') or '(no title)'}   ·   {cw.get('kind', 'Text')}   ·   {cw.get('pos', 'Right')}"), 1)
            e = QPushButton("Edit")
            e.clicked.connect(lambda _=False, n=i: self.edit_custom_widget(n))
            d = QPushButton("Delete")
            d.clicked.connect(lambda _=False, n=i: self.delete_custom_widget(n))
            h.addWidget(e)
            h.addWidget(d)
            col.addWidget(row)
        if not items:
            col.addWidget(QLabel("No custom widgets yet."))
        add = QPushButton("＋  Add a widget")
        add.setObjectName("Primary")
        add.clicked.connect(lambda: self.edit_custom_widget(None))
        col.addSpacing(12)
        col.addWidget(add, 0, Qt.AlignmentFlag.AlignLeft)

    def edit_custom_widget(self, index):
        items = list(self.browser.settings.get("custom_widgets") or [])
        cw = dict(items[index]) if index is not None else {"kind": "Text", "title": "", "pos": "Right", "content": "", "height": 260}
        dlg = QDialog(self)
        dlg.setWindowTitle("Custom widget")
        dlg.setObjectName("Customize")
        dlg.setStyleSheet(themed(CUSTOMIZE_STYLE))
        dlg.resize(520, 420)
        f = QVBoxLayout(dlg)
        kind = QComboBox()
        kind.addItems(["Text", "Links", "Web embed", "HTML"])
        kind.setCurrentText(cw.get("kind", "Text"))
        title = QLineEdit(cw.get("title", ""))
        title.setPlaceholderText("Title (optional)")
        pos = QComboBox()
        pos.addItems(["Left", "Center", "Right"])
        pos.setCurrentText(cw.get("pos", "Right"))
        height = QSpinBox()
        height.setRange(80, 900)
        height.setSuffix(" px tall (embeds & HTML)")
        height.setValue(int(cw.get("height", 260)))
        help_ = QLabel("")
        help_.setObjectName("Hint")
        help_.setWordWrap(True)
        content = QTextEdit()
        content.setPlainText(cw.get("content", ""))
        content.setStyleSheet(f"background: {pal('field')}; color: {pal('text')}; border: 1px solid {pal('border')}; border-radius: 6px;")
        tips = {"Text": "Anything you want on your start page: a reminder, a quote, a goal.",
                "Links": "One link per line, like:   YouTube | youtube.com",
                "Web embed": "A web address to show live inside the widget (some sites don't allow being embedded).",
                "HTML": "Your own HTML/CSS/JS. It runs in a sealed box, so it can't touch your files or the browser."}
        kind.currentTextChanged.connect(lambda k: help_.setText(tips[k]))
        help_.setText(tips[kind.currentText()])
        for w in (QLabel("Type"), kind, QLabel("Title"), title, QLabel("Where"), pos, height, help_, content):
            f.addWidget(w)
        ok = QPushButton("Save widget")
        ok.setObjectName("Primary")
        ok.clicked.connect(dlg.accept)
        f.addWidget(ok)
        if dlg.exec():
            cw = {"kind": kind.currentText(), "title": title.text(), "pos": pos.currentText(),
                  "content": content.toPlainText(), "height": height.value()}
            if index is None:
                items.append(cw)
            else:
                items[index] = cw
            self.browser.set_option("custom_widgets", items)
            self.refresh()

    def delete_custom_widget(self, index):
        items = list(self.browser.settings.get("custom_widgets") or [])
        if 0 <= index < len(items):
            items.pop(index)
            self.browser.set_option("custom_widgets", items)
            self.refresh()

    # ---------- site styles ----------
    def site_css_page(self, col):
        head = QLabel("Site styles (CSS)")
        head.setObjectName("Section")
        col.addWidget(head)
        hint = QLabel("Restyle any website with your own CSS, e.g. hide YouTube Shorts or change a site's font. "
                      "It applies to that site and its subdomains.")
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        col.addWidget(hint)
        css = self.browser.settings.get("site_css") or {}
        for site in sorted(css):
            row = QWidget()
            row.setObjectName("Row")
            h = QHBoxLayout(row)
            h.setContentsMargins(0, 8, 0, 8)
            h.addWidget(QLabel(f"{site}   ·   {len(css[site].splitlines())} lines"), 1)
            e = QPushButton("Edit")
            e.clicked.connect(lambda _=False, s=site: self.edit_site_css(s))
            d = QPushButton("Delete")
            d.clicked.connect(lambda _=False, s=site: self.delete_site_css(s))
            h.addWidget(e)
            h.addWidget(d)
            col.addWidget(row)
        if not css:
            col.addWidget(QLabel("No site styles yet."))
        add = QPushButton("＋  Add a site style")
        add.setObjectName("Primary")
        cur = host_of(self.browser.current().url()) if self.browser.current() else ""
        add.clicked.connect(lambda: self.edit_site_css(None, cur))
        col.addSpacing(12)
        col.addWidget(add, 0, Qt.AlignmentFlag.AlignLeft)

    def edit_site_css(self, site, suggested=""):
        css = dict(self.browser.settings.get("site_css") or {})
        if site is None:
            site, ok = QInputDialog.getText(self, "Site style", "Website (e.g. youtube.com):", text=suggested)
            site = _host("https://" + site.strip().split("://")[-1]) if ok and site.strip() else ""
            if not site:
                return
        text, ok = QInputDialog.getMultiLineText(self, f"CSS for {site}", f"CSS applied on {site}:", css.get(site, ""))
        if ok:
            if text.strip():
                css[site] = text
            else:
                css.pop(site, None)
            self.browser.set_option("site_css", css)
            self.refresh()

    def delete_site_css(self, site):
        css = dict(self.browser.settings.get("site_css") or {})
        css.pop(site, None)
        self.browser.set_option("site_css", css)
        self.refresh()

    # ---------- packs, import / export, reset ----------
    def apply_pack(self, name):
        self.browser.apply_pack(name)
        self.setStyleSheet(themed(CUSTOMIZE_STYLE))
        self.refresh()

    def export_theme(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export your look", str(Path.home() / "my-look.novatheme"),
                                              "Nova themes (*.novatheme)")
        if not path:
            return
        data = {k: self.browser.settings[k] for k in OPTION_BY_KEY if not k.startswith("key_")
                and OPTION_BY_KEY[k]["kind"] not in ("file", "folder")}
        data["custom_widgets"] = self.browser.settings.get("custom_widgets", [])
        data["site_css"] = self.browser.settings.get("site_css", {})
        Path(path).write_text(json.dumps({"nova_theme": 1, "settings": data}, indent=1), encoding="utf-8")
        self.browser.status("💾 Look exported. Share the file with friends!")

    def import_theme(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import a look", str(Path.home()), "Nova themes (*.novatheme *.json)")
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8")).get("settings", {})
        except (OSError, ValueError, AttributeError):
            QMessageBox.warning(self, "Import", "That file isn't a Nova theme.")
            return
        changes = {k: v for k, v in data.items() if k in OPTION_BY_KEY and valid_value(OPTION_BY_KEY[k], v)
                   and OPTION_BY_KEY[k]["kind"] not in ("file", "folder") and not k.startswith("key_")}
        if isinstance(data.get("custom_widgets"), list):
            changes["custom_widgets"] = [w for w in data["custom_widgets"] if isinstance(w, dict)][:40]
        if isinstance(data.get("site_css"), dict):
            changes["site_css"] = {str(k): str(v) for k, v in data["site_css"].items()}
        self.browser.set_options(changes)
        self.setStyleSheet(themed(CUSTOMIZE_STYLE))
        self.refresh()
        self.browser.status(f"📂 Imported {len(changes)} settings.")

    def reset_section(self):
        cat = self.cats.currentItem().text()
        if cat not in CATEGORIES:
            return
        self.browser.set_options({o["key"]: o["default"] for o in OPTIONS if o["cat"] == cat})
        self.setStyleSheet(themed(CUSTOMIZE_STYLE))
        self.refresh()

    def reset_all(self):
        if QMessageBox.question(self, "Reset everything", "Put every option back to its default?") != QMessageBox.StandardButton.Yes:
            return
        self.browser.set_options({o["key"]: o["default"] for o in OPTIONS})
        self.setStyleSheet(themed(CUSTOMIZE_STYLE))
        self.refresh()


class NovaPanel(QWidget):
    """Side panel that talks to Nova (Jarvis.py) through her private browser link."""

    def __init__(self, browser):
        super().__init__()
        self.browser = browser
        self.setObjectName("NovaPanel")
        self.setStyleSheet(themed(NOVA_STYLE))
        self.setMinimumWidth(320)

        self.net = QNetworkAccessManager(self)
        self.net.setProxy(QNetworkProxy(QNetworkProxy.ProxyType.NoProxy))   # Nova is on this PC
        self.messages = []          # list of (who, text)
        self.online = False
        self.locked = False
        self.waiting = False
        self.start_tries = 0
        self.started_nova = False    # True only when THIS browser started Nova (then closing the browser shuts her down)
        self.nova_pid = 0
        self.speak = bool(browser.settings.get("nova_speaks", True))

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        # Header: title, status, voice toggle, full HUD, close
        head = QHBoxLayout()
        title = QLabel("✦ NOVA")
        title.setObjectName("NovaTitle")
        self.status = QLabel("● checking…")
        self.status.setObjectName("NovaStatus")
        self.voice_btn = self.small_button("", "Nova speaks her answers out loud", self.toggle_voice)
        self.hud_btn = self.small_button("⛶", "Open Nova's full HUD", self.open_hud)
        close = self.small_button("✕", "Close panel (Alt+N)", browser.toggle_nova)
        head.addWidget(title)
        head.addStretch()
        head.addWidget(self.status)
        head.addWidget(self.voice_btn)
        head.addWidget(self.hud_btn)
        head.addWidget(close)
        root.addLayout(head)
        self.update_voice_button()

        # Start button (only while Nova is offline)
        self.start_btn = QPushButton("Start Nova")
        self.start_btn.setObjectName("NovaStart")
        self.start_btn.clicked.connect(lambda: self.start_nova(auto=False))
        self.start_btn.hide()
        root.addWidget(self.start_btn)

        # Unlock row (only while Nova is locked)
        self.unlock_row = QWidget()
        ur = QHBoxLayout(self.unlock_row)
        ur.setContentsMargins(0, 0, 0, 0)
        self.code_input = QLineEdit()
        self.code_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.code_input.setPlaceholderText("Nova is locked: unlock code")
        self.code_input.returnPressed.connect(self.unlock)
        unlock_btn = QPushButton("Unlock")
        unlock_btn.setObjectName("NovaStart")
        unlock_btn.clicked.connect(self.unlock)
        ur.addWidget(self.code_input, 1)
        ur.addWidget(unlock_btn)
        self.unlock_row.hide()
        root.addWidget(self.unlock_row)

        # Chat log
        self.log = QTextBrowser()
        self.log.setObjectName("NovaLog")
        self.log.setOpenLinks(False)
        self.log.anchorClicked.connect(lambda url: browser.new_tab(url))
        root.addWidget(self.log, 1)

        # Quick-action chips
        chips = QHBoxLayout()
        self.chips, self.chip_prompts = [], ["", "", ""]
        for i in range(3):
            chip = QPushButton("")
            chip.setObjectName("NovaChip")
            chip.clicked.connect(lambda _=False, n=i: self.send(self.chip_prompts[n]))
            chips.addWidget(chip)
            self.chips.append(chip)
        chips.addStretch()
        self.set_chips()
        root.addLayout(chips)

        # Input row
        row = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("Ask Nova anything…")
        self.input.returnPressed.connect(lambda: self.send(self.input.text()))
        send = QPushButton("➤")
        send.setObjectName("NovaSend")
        send.clicked.connect(lambda: self.send(self.input.text()))
        row.addWidget(self.input, 1)
        row.addWidget(send)
        root.addLayout(row)

        # While Nova is starting up, keep checking until she answers
        self.poll = QTimer(self)
        self.poll.setInterval(2000)
        self.poll.timeout.connect(self.poll_tick)

        self.add("nova", "Hey! Ask me about this page, or tell me to open something.")

    def small_button(self, text, tip, slot):
        b = QPushButton(text)
        b.setObjectName("NovaSend")
        b.setToolTip(tip)
        b.setFixedWidth(34)
        b.clicked.connect(slot)
        return b

    # ---------- chat log ----------
    def add(self, who, text):
        self.messages.append((who, text))
        self.render()

    def render(self):
        parts = []
        for who, text in self.messages[-60:]:
            body = html.escape(text).replace("\n", "<br>")
            if who == "you":
                parts.append(
                    '<table width="100%"><tr><td width="22%"></td>'
                    '<td style="background:#2c3550;border-radius:10px;padding:8px 10px;">'
                    f'{body}</td></tr></table>')
            elif who == "system":
                parts.append(f'<p style="color:#8a8d98;font-size:11px;'
                             f'text-align:center;">{body}</p>')
            else:
                parts.append(
                    '<p style="color:#8fa6ff;font-size:11px;margin:6px 0 2px;">NOVA</p>'
                    '<table width="100%"><tr>'
                    '<td style="background:#23252c;border-radius:10px;padding:8px 10px;">'
                    f'{body}</td><td width="12%"></td></tr></table>')
        if self.waiting:
            parts.append('<p style="color:#8a8d98;font-style:italic;">Nova is thinking…</p>')
        self.log.setHtml(themed("".join(parts)))
        bar = self.log.verticalScrollBar()
        bar.setValue(bar.maximum())

    def set_state(self, status):
        """status = Nova's /ping answer, or None when she can't be reached."""
        was_online = self.online
        self.online = status is not None
        self.locked = bool(status and status.get("locked"))
        if not self.online:
            self.status.setText('<span style="color:#e06c75;">●</span> offline')
            self.unlock_row.hide()
            if not self.poll.isActive():
                self.start_btn.setEnabled(True)
                self.start_btn.setText("Start Nova")
            self.start_btn.show()
            return
        self.poll.stop()
        self.start_btn.hide()
        if self.locked:
            self.status.setText('<span style="color:#e5c07b;">●</span> locked')
            self.unlock_row.show()
            self.code_input.setFocus()
        else:
            self.status.setText('<span style="color:#5fd38d;">●</span> online')
            self.unlock_row.hide()
        if not was_online and self.start_tries:
            self.start_tries = 0
            self.add("system", "Nova is online." + (" Enter your unlock code to start." if self.locked else ""))
            if self.locked and self.started_nova:
                self.browser.show_nova()          # so you can type the passcode

    # ---------- talking to Nova ----------
    def request(self, path):
        """Request to Nova's link, or None when she isn't running (no link file)."""
        info = load_json(BRIDGE_FILE, {})
        if not isinstance(info, dict) or not info.get("token"):
            return None
        req = QNetworkRequest(QUrl(f"http://127.0.0.1:{int(info.get('port', 8766))}{path}"))
        req.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, "application/json")
        req.setRawHeader(b"X-Nova-Token", str(info["token"]).encode("utf-8"))
        req.setTransferTimeout(120000)
        return req

    def post_json(self, path, data, done):
        req = self.request(path)
        if req is None:
            self.set_state(None)
            done(None, {})
            return
        body = QByteArray(json.dumps(data).encode("utf-8"))
        reply = self.net.post(req, body)
        reply.finished.connect(lambda r=reply: done(*self.read_reply(r)))

    @staticmethod
    def read_reply(reply):
        """(http status or None if unreachable, json dict)."""
        code = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
        try:
            data = json.loads(bytes(reply.readAll()).decode("utf-8"))
        except ValueError:
            data = {}
        reply.deleteLater()
        return (int(code) if code else None), (data if isinstance(data, dict) else {})

    def ping(self):
        req = self.request("/ping")
        if req is None:
            self.set_state(None)
            return
        reply = self.net.get(req)
        reply.finished.connect(lambda r=reply: self.on_ping(*self.read_reply(r)))

    def on_ping(self, code, data):
        self.set_state(data if code == 200 else None)

    def send(self, text):
        text = text.strip()
        if not text or self.waiting:
            return
        self.input.clear()
        self.add("you", text)
        if not self.online:
            if self.poll.isActive():
                self.add("system", "Nova is still starting up. Give her a moment, then ask again.")
            else:
                self.add("system", "Nova isn't running. Press Start Nova first.")
                self.ping()
            return
        if self.locked:
            self.add("system", "Nova is locked. Type your unlock code in the box above.")
            return
        self.waiting = True
        self.render()
        view = self.browser.current()
        if is_start_page(view.url()):
            self.ask(text, {"url": "", "title": "Start page"}, "")
        else:
            page = {"url": view.url().toString(), "title": view.title()}
            view.page().toPlainText(lambda t: self.ask(text, page, t or ""))

    def ask(self, text, page, page_text):
        page["text"] = page_text[:PAGE_TEXT_LIMIT]
        self.post_json("/ask", {"text": text, "source": "browser", "speak": self.speak, "page": page},
                       self.on_answer)

    def on_answer(self, code, data):
        self.waiting = False
        if code is None:
            self.render()
            self.set_state(None)
            self.add("system", "Couldn't reach Nova. Is she still running?")
            return
        if data.get("locked"):
            self.render()
            self.set_state({"locked": True})
            self.add("system", "Nova is locked. Type your unlock code in the box above.")
            return
        if data.get("reply"):
            self.add("nova", data["reply"])
        else:
            self.add("system", data.get("error") or "Nova didn't answer that one.")
        for action in data.get("actions", []):
            self.browser.run_nova_action(action)

    def unlock(self):
        code = self.code_input.text()
        self.code_input.clear()
        if not code:
            return
        self.post_json("/unlock", {"code": code}, self.on_unlock)

    def on_unlock(self, code, data):
        if code == 200 and data.get("ok"):
            self.add("system", "Unlocked.")
            self.input.setFocus()
        elif code is not None:
            self.add("system", data.get("error") or "That didn't work.")
        self.ping()

    def open_hud(self):
        if not self.online:
            self.add("system", "Nova isn't running yet.")
            return
        if self.locked:
            self.add("system", "Unlock Nova first.")
            return
        self.post_json("/hud", {}, lambda code, data: None)

    def toggle_voice(self):
        self.browser.set_option("nova_speaks", not self.speak)

    def set_chips(self):
        """Quick buttons come from Customize → Nova ("Label | what to ask")."""
        for i, chip in enumerate(self.chips):
            raw = str(self.browser.settings.get(f"nova_chip{i + 1}", "") or "").strip()
            label, _, prompt = raw.partition("|")
            label, prompt = label.strip(), (prompt.strip() or label.strip())
            self.chip_prompts[i] = prompt
            chip.setText(label)
            chip.setVisible(bool(label))

    def update_voice_button(self):
        self.voice_btn.setText("🔊" if self.speak else "🔇")
        self.voice_btn.setToolTip("Nova speaks out loud (click to mute her voice)" if self.speak
                                  else "Nova's voice is muted in the browser (click to unmute)")

    # ---------- starting Nova ----------
    def nova_path(self, ask=True):
        settings = load_json(SETTINGS_FILE, {})
        path = settings.get("nova_path", "")
        if path and Path(path).exists():
            return path
        if not ask:
            return ""                                   # starting up: never pop up questions
        path, _ = QFileDialog.getOpenFileName(
            self, "Where is Jarvis.py?", str(Path.home()), "Python files (*.py *.pyw)")
        if path:
            settings["nova_path"] = path
            save_json(SETTINGS_FILE, settings)
        return path

    def auto_start(self):
        """Called when the browser opens: connect to Nova if she's running, otherwise start her in the background."""
        if nova_running_pid():
            # You started Nova yourself (or she's still booting): just connect, never start a second copy,
            # and never shut her down when the browser closes.
            self.add("system", "Nova is already running. Connecting…")
            self.wait_for_link()
            return
        self.start_nova(auto=True)

    def wait_for_link(self):
        self.start_tries = 1
        self.poll.start()
        self.ping()

    def python_for_nova(self, ask=True):
        """The Python that runs Jarvis.py. As a script: the same one. As the .exe: your installed Python."""
        if not FROZEN:
            exe = Path(sys.executable)
            if exe.name.lower() == "pythonw.exe" and exe.with_name("python.exe").exists():
                exe = exe.with_name("python.exe")
            return exe
        saved = self.browser.settings.get("python_path", "")
        if saved and Path(saved).exists():
            return Path(saved)
        found = ""
        for name in ("python", "python3"):
            p = shutil.which(name) or ""
            if p and "windowsapps" not in p.lower():          # skip the Microsoft Store placeholder
                found = p
                break
        if not found and ask:
            found, _ = QFileDialog.getOpenFileName(self, "Where is python.exe (the one that runs Nova)?",
                                                   str(Path.home()), "python.exe (python.exe)")
        if found and Path(found).exists():
            self.browser.set_setting("python_path", found)
            return Path(found)
        return None

    def start_nova(self, auto=False):
        if nova_running_pid():
            self.add("system", "Nova is already running.")
            self.wait_for_link()
            return
        path = self.nova_path(ask=not auto)
        if not path:
            if auto:
                self.add("system", "Nova isn't set up on this PC, and that's fine: the whole browser works without her. "
                                   "If you have Jarvis.py, press Start Nova once and I'll remember where she is.")
            return
        # Use python.exe (not pythonw) with a HIDDEN console: Nova's helper programs (ffmpeg, GPU checks,
        # game detection...) share that hidden console, so no cmd windows flash on screen.
        exe = self.python_for_nova(ask=not auto)
        if exe is None:
            self.add("system", "I need to know where python.exe is to start Nova.")
            return
        flags = 0
        if sys.platform == "win32":
            flags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")   # her emoji prints can't crash the log
        try:
            log = open(NOVA_LOG, "w", encoding="utf-8", errors="replace")
            # --browser: no HUD windows (Section 13ZC). She still starts LOCKED and needs your passcode.
            proc = subprocess.Popen([str(exe), "-u", path, "--browser"], cwd=str(Path(path).parent),
                                    stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                    creationflags=flags, env=env, close_fds=True)
            log.close()
        except OSError as e:
            self.add("system", f"Couldn't start Jarvis.py: {e}")
            return
        self.started_nova = True
        self.nova_pid = proc.pid
        self.start_btn.setEnabled(False)
        self.start_btn.setText("Starting Nova…")
        self.start_btn.show()
        self.add("system", "Starting Nova in the background… (loading her models can take a bit)")
        self.wait_for_link()

    def shutdown_if_ours(self):
        """Browser is closing: shut Nova down ONLY if this browser started her."""
        if not self.started_nova:
            return
        self.poll.stop()
        stopped = False
        info = load_json(BRIDGE_FILE, {})
        if isinstance(info, dict) and info.get("token"):
            try:
                req = urllib.request.Request(
                    f"http://127.0.0.1:{int(info.get('port', 8766))}/shutdown", data=b"{}", method="POST",
                    headers={"X-Nova-Token": str(info["token"]), "Content-Type": "application/json"})
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                with opener.open(req, timeout=3) as r:
                    stopped = r.status == 200
            except Exception:
                stopped = False
        if not stopped and self.nova_pid and pid_alive(self.nova_pid):
            # Her link wasn't up yet (still booting): stop the process this browser started
            try:
                os.kill(self.nova_pid, signal.SIGTERM)
            except OSError:
                pass

    def poll_tick(self):
        self.start_tries += 1
        # If the Nova this browser started has stopped, say so instead of waiting forever
        if self.started_nova and self.nova_pid and not pid_alive(self.nova_pid):
            self.poll.stop()
            self.start_tries = 0
            self.started_nova = False
            self.set_state(None)
            self.add("system", f"Nova stopped while starting up. Her log is at {NOVA_LOG} "
                               "(the last lines show what went wrong).")
            return
        if self.start_tries == 45:
            self.add("system", "Still loading her models… hang tight.")
        # Keep waiting as long as Nova is still running (big models can take a few minutes);
        # only give up if nothing is running at all.
        if self.start_tries > 90 and not nova_running_pid():
            self.poll.stop()
            self.start_tries = 0
            self.set_state(None)
            self.add("system", "Nova didn't come online. Try starting Jarvis.py normally "
                               "to see if it shows an error.")
            return
        self.ping()


class Browser(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Nova Browser")
        self.resize(1280, 820)

        self.settings = load_settings()
        self.bookmarks = load_json(BOOKMARKS_FILE, [])
        self.history = load_json(HISTORY_FILE, [])
        self.closed = []                 # recently closed tab addresses (Ctrl+Shift+T)
        self.downloads = []
        self.video_fullscreen = False
        self.floats = []                 # tabs popped out into floating windows
        self.split = None                # split view pane
        self.workspaces = load_json(WORKSPACES_FILE, {})
        self.workspaces = self.workspaces if isinstance(self.workspaces, dict) else {}
        self.read_later = load_json(READ_LATER_FILE, [])
        self.read_later = self.read_later if isinstance(self.read_later, list) else []
        self.notes = load_json(NOTES_FILE, {})
        self.notes = self.notes if isinstance(self.notes, dict) else {}
        self.screen_time = load_json(SCREEN_TIME_FILE, {})
        self.screen_time = self.screen_time if isinstance(self.screen_time, dict) else {}
        self.last_active = {}            # id(tab) -> when you last looked at it (memory saver)
        self.ticks = 0
        self.customize = None
        self.net = QNetworkAccessManager(self)        # the browser's own requests (weather)
        self.weather = {}
        set_theme_from(self.settings)
        self.start_timer = QTimer(self)                  # rebuilds the start page shortly after options change
        self.start_timer.setSingleShot(True)
        self.start_timer.setInterval(350)
        self.start_timer.timeout.connect(self.rebuild_start)

        self.setup_profiles()

        # 🎮 Games + 📣 Following hubs
        self.hub = None
        self._hub_colors = None
        self.toasts = []
        self.tray = None
        self._tray_url = ""

        # Game Mode, tab manager, gestures, zapper, sidebar apps, voice
        self.game_mode = None
        self.gm_held = []
        self._gm_dismissed = ""
        self.gm_timer = QTimer(self)
        self.gm_timer.setInterval(15000)
        self.gm_timer.timeout.connect(self.gm_check)
        self.gm_timer.start()
        self.tab_manager = None
        self.gestures = GestureFilter(self)
        self.zaps = EX.clean_zaps(load_json(ZAPS_FILE, {})) if EX else {}
        self.zap_save_timer = QTimer(self)
        self.zap_save_timer.setSingleShot(True)
        self.zap_save_timer.setInterval(600)
        self.zap_save_timer.timeout.connect(self.save_zaps)
        self.side_panels = {}
        self.side_apps = []
        self.side_current = ""
        self.side_bar = None
        self.side_dock = None
        self.ram_timer = QTimer(self)
        self.ram_timer.setInterval(5000)
        self.ram_timer.timeout.connect(self.update_ram_button)
        self.voice = None
        self.listener = None             # the browser's own 🎤 listener (offline)
        self.wake_listener = None
        self.voice_armed_until = 0.0
        self.voice_setup = None
        self.speaker = EX.Speaker(self) if EX is not None else None
        self.voice_bubble = VoiceBubble(self)
        self._voice_push_at = 0.0
        self.voice_push_timer = QTimer(self)
        self.voice_push_timer.setSingleShot(True)
        self.voice_push_timer.setInterval(2500)
        self.voice_push_timer.timeout.connect(self.push_voice_state)
        if EX is not None:
            self.voice = EX.VoiceLink(str(BRIDGE_FILE), lambda: bool(self.settings.get("nova_voice_control", True))
                                      and bool(self.settings.get("nova_on", True)), self)
            self.voice.action.connect(self.on_voice_action)
            self.voice.status.connect(lambda st: self.voice_push_timer.start() if st == "connected" else None)
        if HUB is not None:
            try:
                self.hub = HUB.HubService(DATA_DIR, lambda: self.settings, parent=self)
                self.hub.changed.connect(self.on_hub_changed)
                self.hub.notify.connect(self.on_hub_notify)
                self.hub.open_requested.connect(lambda u: self.new_tab(QUrl(u), private=False))
                self.hub.option_requested.connect(self.set_option)
                self.hub.customize_requested.connect(self.open_customize_hubs)
                self.hub.game_launched.connect(self.on_game_launched)
                self.hub.pack_requested.connect(self.apply_pack)
            except Exception as e:
                print("[hubs] couldn't start:", e)
                self.hub = None

        # Tabs + find bar
        self.tabs = BrowserTabs(self)
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.on_tab_changed)
        self.tabs.tabBar().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tabs.tabBar().customContextMenuRequested.connect(self.tab_menu)
        self.findbar = FindBar(self)
        left = QWidget()
        col = QVBoxLayout(left)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)
        col.addWidget(self.tabs.stack, 1)
        self.body_layout = col                        # the tab strip moves here when "Tab bar position" is Bottom
        col.addWidget(self.findbar)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setHandleWidth(3)
        self.splitter.addWidget(left)
        self.setCentralWidget(self.splitter)

        # Top row: tabs + window buttons (replaces the Windows title bar)
        self.titlebar = TitleBar(self)
        self.titlebar.tab_slot.addWidget(self.tabs.bar)
        self.title_tb = QToolBar("Tabs")
        self.title_tb.setObjectName("TitleToolbar")
        self.title_tb.setMovable(False)
        self.title_tb.setFloatable(False)
        self.title_tb.toggleViewAction().setVisible(False)
        self.title_tb.addWidget(self.titlebar)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.title_tb)
        self.addToolBarBreak(Qt.ToolBarArea.TopToolBarArea)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.resizer = EdgeResizer(self)
        QApplication.instance().installEventFilter(self.resizer)

        # Toolbar (its keyboard shortcuts live in Customize → Keyboard shortcuts)
        bar = QToolBar("Navigation")
        bar.setMovable(False)
        self.toolbar = bar
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, bar)
        self.tb = {}
        self.tb["back"] = self.add_button(bar, "◀", "Back", None, lambda: self.current().back())
        self.tb["forward"] = self.add_button(bar, "▶", "Forward", None, lambda: self.current().forward())
        self.tb["reload"] = self.add_button(bar, "⟳", "Reload", None, lambda: self.current().reload())
        self.tb["home"] = self.add_button(bar, "⌂", "Home", None, self.go_home)

        self.address = QLineEdit()
        self.address.setPlaceholderText("Search or type a web address   (Ctrl+K for everything)")
        self.address.returnPressed.connect(self.navigate)
        bar.addWidget(self.address)

        self.star_act = self.add_button(bar, "☆", "Bookmark this page", None, self.toggle_bookmark)
        self.tb["star"] = self.star_act

        self.bookmarks_menu = QMenu(self)
        self.bookmarks_menu.aboutToShow.connect(self.fill_bookmarks_menu)
        self.tb["bookmarks"] = self.add_menu_button(bar, "📑", "Bookmarks", self.bookmarks_menu).bar_action

        self.history_menu = QMenu(self)
        self.history_menu.aboutToShow.connect(self.fill_history_menu)
        self.history_btn = self.add_menu_button(bar, "🕘", "History", self.history_menu)
        self.tb["history"] = self.history_btn.bar_action

        self.downloads_menu = QMenu(self)
        self.downloads_menu.aboutToShow.connect(self.fill_downloads_menu)
        self.dl_btn = self.add_menu_button(bar, "📥", "Downloads", self.downloads_menu)
        self.tb["downloads"] = self.dl_btn.bar_action

        self.shield_menu = QMenu(self)
        self.shield_menu.aboutToShow.connect(self.fill_shield_menu)
        self.shield_btn = self.add_menu_button(bar, "🛡", "Ad & tracker blocker", self.shield_menu)
        self.tb["shield"] = self.shield_btn.bar_action

        self.tb["mic"] = self.add_button(bar, "🎤", "Talk to the browser (Ctrl+Shift+Space)", None, lambda: self.start_listening())
        self.tb["ram"] = self.add_button(bar, "🧠", "Tab manager & memory (Shift+Esc)", None, self.open_tab_manager)
        self.tb["gamemode"] = self.add_button(bar, "🕹", "Game Mode (Ctrl+Shift+E)", None, self.toggle_game_mode)
        self.tb["games"] = self.add_button(bar, "🎮", "Games", None, lambda: self.open_hub("games"))
        self.tb["follow"] = self.add_button(bar, "📣", "Following", None, lambda: self.open_hub("follow"))
        self.tb["newtab"] = self.add_button(bar, "+", "New tab", None, lambda: self.new_tab())
        self.tb["nova"] = self.add_button(bar, "✦", "Nova", None, self.toggle_nova)
        self.tb["customize"] = self.add_button(bar, "🎨", "Customize", None, self.open_customize)

        self.help_menu = QMenu(self)
        self.help_menu.aboutToShow.connect(self.fill_help_menu)
        self.tb["help"] = self.add_menu_button(bar, "❓", "Help & tour (F1)", self.help_menu).bar_action

        self.main_menu = QMenu(self)
        self.main_menu.aboutToShow.connect(self.fill_main_menu)
        self.tb["menu"] = self.add_menu_button(bar, "☰", "Menu", self.main_menu).bar_action

        # Nova side panel (hidden until you press ✦)
        self.nova_panel = None
        self.nova_dock = None

        # Status bar: messages, focus timer, loading bar
        self.focus_label = QLabel("")
        self.focus_label.hide()
        self.statusBar().addPermanentWidget(self.focus_label)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedWidth(160)
        self.progress.hide()
        self.statusBar().addPermanentWidget(self.progress)

        # Command palette + every command it can run
        self.palette = CommandPalette(self)
        icons = {"palette": "⌘", "customize": "🎨", "new_tab": "➕", "private_tab": "🕶", "reopen": "↺", "close_tab": "✖",
                 "find": "🔍", "reader": "📖", "screenshot": "📸", "dark": "🌙", "adblock": "🛡", "faster": "⏩", "slower": "⏪",
                 "normal_speed": "▶", "float": "🪟", "split": "◫", "paste_go": "📋", "later": "🔖", "notes": "📝", "nova": "✦",
                 "screen_time": "⏱", "focus": "🎯", "workspace_save": "🗂", "qr": "📱", "surprise": "🎲", "mute": "🔇",
                 "print": "🖨", "downloads": "📥", "history": "🕘", "bookmark": "📑", "fullscreen": "⛶",
                 "games": "🎮", "following": "📣", "game_mode": "🕹", "tab_manager": "🧠", "zap": "🎯",
                 "unzap": "↩", "sidebar": "📌", "summarize": "✦", "scroll_top": "⤒", "scroll_bottom": "⤓",
                 "voice": "🎤", "read_aloud": "🔊", "help": "❓", "tour": "👋"}
        self.commands = [
            ("🎯  Focus mode 50 min", "", lambda: self.start_focus(50)),
            ("🎯  End focus mode", "", self.stop_focus),
            ("🎯  Edit focus blocked sites", "", self.edit_focus_sites),
            ("📂  Open Downloads folder", "", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(DOWNLOAD_DIR)))),
            ("✦  Nova: key points of this page", "", lambda: self.summarize_page("Give me the key points of this page.")),
            ("✦  Nova: what are people saying in the comments?", "", lambda: self.summarize_page(
                "What are people saying in the comments on this page? Give me the main opinions.")),
            ("🧹  Clear browsing data", "", self.clear_data),
            ("⌨  Keyboard shortcuts", "", self.show_shortcuts),
            ("💤  Memory saver on/off", "", lambda: self.set_option("memory_saver", not self.settings["memory_saver"])),
            ("🦎  Chameleon toolbar on/off", "", lambda: self.set_option("chameleon", not self.settings["chameleon"])),
            ("⟳  Auto-refresh this tab every minute", "", lambda: self.set_auto_refresh(self.current(), 60)),
            ("⟳  Stop auto-refresh", "", lambda: self.set_auto_refresh(self.current(), 0)),
        ] + [(f"🎨  Accent: {name}", "", lambda n=name: self.set_option("theme", n)) for name in THEMES] \
          + [(f"🖼  Wallpaper: {name}", "", lambda n=name: self.set_option("wp_type", n)) for name in WALLPAPERS] \
          + [(f"✨  Style pack: {name}", "", lambda n=name: self.apply_pack(n)) for name in STYLE_PACKS] \
          + [(f"🌈  Palette: {name}", "", lambda n=name: self.set_option("base_palette", n)) for name in PALETTES]
        self.command_icons = icons

        # Rebindable keyboard shortcuts (Customize → Keyboard shortcuts)
        self.key_fns = {
            "palette": self.open_palette, "customize": self.open_customize, "new_tab": lambda: self.new_tab(),
            "private_tab": lambda: self.new_tab(private=True), "reopen": self.reopen_closed,
            "close_tab": lambda: self.close_tab(self.tabs.currentIndex()), "next_tab": lambda: self.cycle_tab(1),
            "prev_tab": lambda: self.cycle_tab(-1), "address": self.focus_address,
            "back": lambda: self.current().back(), "forward": lambda: self.current().forward(),
            "reload": lambda: self.current().reload(), "home": self.go_home, "bookmark": self.toggle_bookmark,
            "history": lambda: self.history_btn.showMenu(), "downloads": lambda: self.dl_btn.showMenu(),
            "find": self.findbar.open_bar, "reader": self.reader_mode, "screenshot": self.screenshot,
            "dark": lambda: self.set_option("dark_web", not self.settings["dark_web"]),
            "adblock": lambda: self.set_option("adblock", not self.settings["adblock"]),
            "faster": lambda: self.video_speed(1), "slower": lambda: self.video_speed(-1),
            "normal_speed": lambda: self.video_speed(0, reset=True), "zoom_in": lambda: self.zoom(0.1),
            "zoom_in2": lambda: self.zoom(0.1), "zoom_out": lambda: self.zoom(-0.1), "zoom_reset": lambda: self.zoom(reset=True),
            "float": lambda: self.float_tab(), "split": self.toggle_split, "paste_go": self.paste_and_go,
            "later": lambda: self.save_for_later(), "notes": self.edit_site_note, "nova": self.toggle_nova,
            "fullscreen": self.toggle_window_fullscreen, "screen_time": self.show_screen_time,
            "focus": lambda: self.start_focus(int(self.settings["focus_default"])), "workspace_save": self.save_workspace,
            "qr": self.send_to_phone, "surprise": self.surprise_me, "mute": lambda: self.toggle_mute(self.current()),
            "print": self.print_page,
            "games": lambda: self.open_hub("games"), "following": lambda: self.open_hub("follow"),
            "game_mode": self.toggle_game_mode, "tab_manager": self.open_tab_manager,
            "zap": lambda: self.start_zapper(), "unzap": lambda: self.unzap_site(), "sidebar": self.toggle_sidebar,
            "summarize": self.summarize_page, "voice": lambda: self.start_listening(), "read_aloud": self.read_aloud,
            "help": self.open_help, "tour": self.show_tour,
            "scroll_top": lambda: self.current().page().runJavaScript("window.scrollTo({top:0,behavior:'smooth'})"),
            "scroll_bottom": lambda: self.current().page().runJavaScript(
                "window.scrollTo({top:document.documentElement.scrollHeight,behavior:'smooth'})"),
        }
        self.key_actions = {}
        for cid, _label, _default in KEY_COMMANDS:
            self.key_actions[cid] = self.add_shortcut("", self.key_fns[cid])
        self.exit_fs_act = self.add_shortcut("Escape", self.exit_video_fullscreen)
        self.exit_fs_act.setEnabled(False)          # only while a video is full screen

        # Once a second: focus timer + ad counter
        self.ticker = QTimer(self)
        self.ticker.setInterval(1000)
        self.ticker.timeout.connect(self.tick)
        self.ticker.start()

        # Start Nova in the background (or connect to her if she's already running)
        self.setup_nova()
        self.setup_sidebar()
        self.apply_all()
        self.apply_extras()
        if self.voice is not None:
            self.voice.start()
        self.restore_session()
        if self.settings["nova_autostart"] and self.settings.get("nova_on", True):
            QTimer.singleShot(300, self.nova_panel.auto_start)
        if self.settings["nova_open_on_start"] and self.settings.get("nova_on", True):
            QTimer.singleShot(400, self.show_nova)
        if not self.settings.get("tour_done", False):
            QTimer.singleShot(1500, self.show_tour)            # first time: the welcome tour

    # ---------- profiles (logins, ad blocker, scripts, downloads) ----------
    def setup_profiles(self):
        app = QApplication.instance()
        PROFILE_DIR.mkdir(exist_ok=True)
        self.profile = QWebEngineProfile("NovaBrowser", app)            # saved: you stay signed in to sites
        self.profile.setPersistentStoragePath(str(PROFILE_DIR))
        self.profile.setCachePath(str(PROFILE_DIR / "cache"))
        self.profile.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)
        self.private_profile = QWebEngineProfile(app)                   # no name = private, nothing saved to disk

        self.adblock = AdBlocker(app)
        self.adblock.enabled = bool(self.settings["adblock"])
        self.default_ua = {}
        for p in (self.profile, self.private_profile):
            self.default_ua[id(p)] = p.httpUserAgent()
            p.setUrlRequestInterceptor(self.adblock)
            p.downloadRequested.connect(self.on_download)
            p.settings().setAttribute(QWebEngineSettings.WebAttribute.FullScreenSupportEnabled, True)
            try:
                p.cookieStore().setCookieFilter(self.cookie_filter)
            except Exception:
                pass

    def profiles(self):
        return (self.profile, self.private_profile)

    def set_setting(self, key, value):
        """Update one setting without overwriting ones the Nova panel saved."""
        self.settings[key] = value
        s = load_json(SETTINGS_FILE, {})
        s = s if isinstance(s, dict) else {}
        s[key] = value
        save_json(SETTINGS_FILE, s)

    def status(self, text, ms=4000):
        self.statusBar().showMessage(text, ms)

    # ---------- helpers ----------
    def add_button(self, bar, text, tip, shortcut, slot):
        act = QAction(text, self)
        act.setToolTip(tip)
        if shortcut:
            act.setShortcut(QKeySequence(shortcut))
        act.triggered.connect(slot)
        bar.addAction(act)
        return act

    def add_menu_button(self, bar, text, tip, menu):
        btn = QToolButton()
        btn.setText(text)
        btn.setToolTip(tip)
        btn.setMenu(menu)
        btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        btn.bar_action = bar.addWidget(btn)
        return btn

    def add_shortcut(self, keys, slot):
        act = QAction(self)
        if keys:
            act.setShortcut(QKeySequence(keys))
        act.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
        act.triggered.connect(slot)
        self.addAction(act)
        return act

    def current(self) -> QWebEngineView:
        return self.tabs.currentWidget()

    def views(self):
        return [self.tabs.widget(i) for i in range(self.tabs.count())]

    def focus_address(self):
        self.address.setFocus()
        self.address.selectAll()

    def open_in_current(self, url: str):
        self.current().setUrl(QUrl(url))

    # ---------- tabs ----------
    def new_tab(self, url: QUrl = None, load: bool = True, private=None):
        if private is None:
            private = bool(self.settings.get("private_by_default"))
        view = WebView(self, private=private)
        view.base_title = "Private Tab" if private else "New Tab"
        if load:
            view.setUrl(url or self.default_new_tab_url())

        index = self.tabs.addTab(view, "")
        self.refresh_tab_label(view)
        self.tabs.setCurrentIndex(index)

        view.titleChanged.connect(lambda title, v=view: self.update_title(v, title))
        view.urlChanged.connect(lambda u, v=view: self.update_address(v, u))
        view.loadProgress.connect(lambda p, v=view: self.update_progress(v, p))
        view.loadFinished.connect(lambda ok, v=view: self.on_load_finished(v, ok))
        view.iconChanged.connect(lambda icon, v=view: self.tabs.setTabIcon(self.tabs.indexOf(v), icon))
        return view

    def close_tab(self, index):
        if index < 0:
            return
        if self.tabs.count() <= 1:
            self.close()
            return
        widget = self.tabs.widget(index)
        url = widget.url().toString()
        if not widget.private and is_web(url) and not widget.title().startswith(("📖", "🎯")):
            self.closed.append(url)
            del self.closed[:-25]
        self.tabs.removeTab(index)
        widget.deleteLater()

    def reopen_closed(self):
        if not self.closed:
            self.status("No recently closed tabs.")
            return
        self.new_tab(QUrl(self.closed.pop()))

    def close_others(self, keep):
        for v in self.views():
            if v is not keep:
                self.close_tab(self.tabs.indexOf(v))

    def toggle_mute(self, view):
        page = view.page()
        page.setAudioMuted(not page.isAudioMuted())
        self.refresh_tab_label(view)
        self.status("🔇 Tab muted" if page.isAudioMuted() else "🔊 Tab unmuted")

    def tab_menu(self, pos):
        i = self.tabs.tabBar().tabAt(pos)
        if i < 0:
            return
        v = self.tabs.widget(i)
        menu = QMenu(self)
        menu.addAction("⟳  Reload").triggered.connect(v.reload)
        menu.addAction("⧉  Duplicate").triggered.connect(lambda: self.new_tab(v.url(), private=v.private))
        menu.addAction("🔊  Unmute tab" if v.page().isAudioMuted() else "🔇  Mute tab").triggered.connect(
            lambda: self.toggle_mute(v))
        menu.addAction("🪟  Float on top").triggered.connect(lambda: self.float_tab(v))
        menu.addAction("🔖  Save for later").triggered.connect(lambda: self.save_for_later(v))
        if v is not self.current():
            menu.addAction("💤  Put to sleep").triggered.connect(lambda: self.sleep_tab(v))
        auto = menu.addMenu("⟳  Auto-refresh")
        for label, secs in (("Off", 0), ("Every 30 seconds", 30), ("Every minute", 60),
                            ("Every 5 minutes", 300), ("Every 15 minutes", 900)):
            auto.addAction(label).triggered.connect(lambda _=False, n=secs: self.set_auto_refresh(v, n))
        menu.addSeparator()
        menu.addAction("Close other tabs").triggered.connect(lambda: self.close_others(v))
        menu.addAction("Close tab").triggered.connect(lambda: self.close_tab(self.tabs.indexOf(v)))
        menu.exec(self.tabs.tabBar().mapToGlobal(pos))

    def refresh_tab_label(self, view):
        i = self.tabs.indexOf(view)
        if i == -1:
            return
        title = getattr(view, "base_title", "") or "New Tab"
        n = int(self.settings.get("tab_title_length", 24))
        short = title if len(title) <= n else title[:max(1, n - 2)] + "…"
        prefix = "🕶 " if view.private else ""
        if getattr(view, "asleep", False):
            prefix += "💤 "
        if getattr(view, "refresh_timer", None):
            prefix += "⟳ "
        if view.page().isAudioMuted():
            prefix += "🔇 "
        elif view.audible:
            prefix += "🔊 "
        self.tabs.setTabText(i, prefix + short)
        self.tabs.setTabToolTip(i, title)

    def on_tab_changed(self, index):
        view = self.tabs.widget(index)
        if view:
            self.wake(view)
            now = time.time()
            for v in self.views():
                self.last_active.setdefault(id(v), now)
            self.last_active[id(view)] = now
            self.update_address(view, view.url())
            self.update_window_title(view)
            self.apply_chameleon(view)
            if self.findbar.isVisible():
                self.findbar.find()

    def update_window_title(self, view):
        t = getattr(view, "base_title", "") or "New Tab"
        self.setWindowTitle(f"{t} - Nova Browser" + ("  (Private)" if view.private else ""))

    def save_session(self):
        tabs = [v.url().toString() for v in self.views()
                if not v.private and is_web(v.url().toString()) and not v.title().startswith(("📖", "🎯"))]
        save_json(SESSION_FILE, {"tabs": tabs})

    def restore_session(self):
        urls = load_json(SESSION_FILE, {}).get("tabs", []) if self.settings["restore_session"] else []
        urls = [u for u in urls if isinstance(u, str) and is_web(u)][:30]
        if not urls:
            self.new_tab()
            return
        for u in urls:
            self.new_tab(QUrl(u))
        self.status(f"Restored {len(urls)} tab{'s' if len(urls) != 1 else ''} from last time.")

    # ---------- page updates ----------
    def navigate(self):
        self.current().setUrl(to_url(self.address.text()))
        self.current().setFocus()

    def update_title(self, view, title):
        view.base_title = title or "New Tab"
        self.refresh_tab_label(view)
        if view is self.current():
            self.update_window_title(view)

    def update_address(self, view, url):
        if view is not self.current():
            return
        s = url.toString()
        self.address.setText("" if is_start_page(url) or s.startswith(("data:", "about:")) else s)
        self.address.setCursorPosition(0)
        self.address.setPlaceholderText("🕶 Private tab: nothing is saved" if view.private
                                        else "Search or type a web address   (Ctrl+K for everything)")
        self.update_star()

    def update_progress(self, view, percent):
        if view is not self.current():
            return
        if percent >= 100:
            self.progress.hide()
        else:
            self.progress.show()
            self.progress.setValue(percent)

    def on_load_finished(self, view, ok):
        self.apply_zoom(view)
        self.record_history(view, ok)
        self.apply_chameleon(view)
        if ok and view is self.current() and host_of(view.url()) in self.notes:
            self.status("📝 You have a note for this site (Ctrl+Shift+M)", 6000)

    # ---------- zoom (remembered per site) ----------
    def apply_zoom(self, view):
        h = host_of(view.url())
        if h:
            view.setZoomFactor(float(self.settings["zoom"].get(h, int(self.settings["default_zoom"]) / 100)))

    def zoom(self, step=0.0, reset=False):
        v = self.current()
        z = 1.0 if reset else round(min(3.0, max(0.3, v.zoomFactor() + step)), 2)
        v.setZoomFactor(z)
        h = host_of(v.url())
        if h and not v.private:
            zooms = self.settings["zoom"]
            if abs(z - 1.0) < 0.01:
                zooms.pop(h, None)
            else:
                zooms[h] = z
            self.set_setting("zoom", zooms)
        self.status(f"🔎 Zoom {int(round(z * 100))}%" + (f" for {h}" if h else ""))

    # ---------- dark websites ----------
    def apply_dark_web(self):
        on = bool(self.settings["dark_web"])
        attr = getattr(QWebEngineSettings.WebAttribute, "ForceDarkMode", None)     # Qt 6.7+: Chrome's own dark mode
        for p in self.profiles():
            for old in p.scripts().find("nova-dark"):
                p.scripts().remove(old)
            if attr is not None:
                p.settings().setAttribute(attr, on)
            elif on:
                p.scripts().insert(make_script("nova-dark", DARK_WEB_JS))

    def set_dark_web(self, on):
        self.set_option("dark_web", bool(on))
        for v in self.views():
            if is_web(v.url().toString()):
                v.reload()
        self.status("🌙 Dark websites on" if on else "☀ Dark websites off")

    # ---------- ad blocker ----------
    def set_adblock(self, on):
        self.set_option("adblock", bool(on))
        self.status("🛡 Ad & tracker blocker on" if on else "🛡 Ad & tracker blocker off")
        self.tick()

    def fill_shield_menu(self):
        m = self.shield_menu
        m.clear()
        act = m.addAction("Block ads & trackers")
        act.setCheckable(True)
        act.setChecked(self.adblock.enabled)
        act.triggered.connect(lambda checked: self.set_adblock(checked))
        m.addAction(f"{self.adblock.blocked} blocked this session").setEnabled(False)
        m.addAction(f"{len(AD_HOSTS)} known ad & tracker servers").setEnabled(False)

    # ---------- downloads ----------
    def on_download(self, req):
        DOWNLOAD_DIR.mkdir(exist_ok=True)
        req.setDownloadDirectory(str(DOWNLOAD_DIR))
        req.accept()
        self.downloads.insert(0, req)
        del self.downloads[25:]
        req.isFinishedChanged.connect(lambda r=req: self.on_download_finished(r))
        self.dl_btn.setText("📥•")
        self.status(f"⬇ Downloading {req.downloadFileName()}…")

    def on_download_finished(self, req):
        if not any(r.state() == QWebEngineDownloadRequest.DownloadState.DownloadInProgress for r in self.downloads):
            self.dl_btn.setText("📥")
        if req.state() == QWebEngineDownloadRequest.DownloadState.DownloadCompleted:
            self.status(f"✓ Downloaded {req.downloadFileName()} (click 📥 to open)", 6000)
        else:
            self.status(f"✗ Download stopped: {req.downloadFileName()}", 6000)

    def fill_downloads_menu(self):
        m = self.downloads_menu
        m.clear()
        S = QWebEngineDownloadRequest.DownloadState
        if not self.downloads:
            m.addAction("No downloads yet").setEnabled(False)
        for r in self.downloads:
            name = r.downloadFileName()
            st = r.state()
            if st == S.DownloadCompleted:
                path = os.path.join(r.downloadDirectory(), name)
                m.addAction(f"✓  {name}").triggered.connect(
                    lambda _=False, p=path: QDesktopServices.openUrl(QUrl.fromLocalFile(p)))
            elif st == S.DownloadInProgress:
                total = r.totalBytes()
                pct = f"{r.receivedBytes() * 100 // total}%" if total > 0 else f"{r.receivedBytes() // 1048576} MB"
                m.addAction(f"⬇  {name}   {pct}   (click to cancel)").triggered.connect(
                    lambda _=False, d=r: d.cancel())
            else:
                m.addAction(f"✗  {name}").setEnabled(False)
        m.addSeparator()
        m.addAction("📂  Open Downloads folder").triggered.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(DOWNLOAD_DIR))))

    # ---------- reader mode ----------
    def reader_mode(self):
        v = self.current()
        url = v.url()
        if not is_web(url.toString()):
            self.status("📖 Reader mode works on web articles.")
            return
        private = v.private

        def got(result):
            try:
                data = json.loads(result or "{}")
            except (TypeError, ValueError):
                data = {}
            words = int(data.get("words") or 0)
            if words < 80 or not data.get("html"):
                self.status("📖 Couldn't find an article on this page.")
                return
            s = self.settings
            bg, fg, head, muted, code = READER_COLORS.get(s["reader_bg"], READER_COLORS["Dark"])
            page = READER_TEMPLATE.format(
                title=html.escape(data.get("title") or "Article"), site=html.escape(data.get("site") or ""),
                minutes=max(1, round(words / 230)), content=data["html"][:1_500_000], bg=bg, fg=fg, head=head,
                muted=muted, code=code, font=s["reader_font"], size=int(s["reader_size"]), width=int(s["reader_width"]),
                line=s["reader_line"])
            nv = self.new_tab(load=False, private=private)
            nv.setHtml(themed(page), url)
        v.page().runJavaScript(READER_JS, got)

    # ---------- video speed (any site, any player) ----------
    def video_speed(self, direction, reset=False):
        delta = float(direction) * float(self.settings.get("video_step", "0.25"))
        js = "window.postMessage({novaSpeed:{delta:%s,reset:%s}},'*')" % (delta, "true" if reset else "false")
        self.current().page().runJavaScript(js)

    # ---------- full-screen video ----------
    def on_fullscreen_request(self, request):
        request.accept()
        if request.toggleOn():
            self.video_fullscreen = True
            self._was_max = self.isMaximized()
            self._nova_was_open = self.nova_dock is not None and self.nova_dock.isVisible()
            self.toolbar.hide()
            self.title_tb.hide()
            self.tabs.tabBar().hide()
            self.statusBar().hide()
            self.findbar.hide()
            if self.nova_dock is not None:
                self.nova_dock.hide()
            self._side_was_open = self.side_dock is not None and self.side_dock.isVisible()
            for w in (self.side_dock, self.side_bar):
                if w is not None:
                    w.hide()
            self.exit_fs_act.setEnabled(True)
            self.showFullScreen()
        else:
            self.video_fullscreen = False
            self.exit_fs_act.setEnabled(False)
            self.toolbar.show()
            self.title_tb.show()
            self.tabs.tabBar().show()
            self.statusBar().setVisible(bool(self.settings["show_status_bar"]))
            if getattr(self, "_nova_was_open", False):
                self.nova_dock.show()
            if self.side_bar is not None and self.side_apps and self.settings.get("sidebar_on", True):
                self.side_bar.show()
                if getattr(self, "_side_was_open", False):
                    self.side_dock.show()
            if getattr(self, "_was_max", False):
                self.showMaximized()
            else:
                self.showNormal()

    def exit_video_fullscreen(self):
        if self.video_fullscreen:
            self.current().triggerPageAction(QWebEnginePage.WebAction.ExitFullScreen)

    # ---------- screenshot ----------
    def screenshot(self):
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        pix = self.current().grab()
        name = time.strftime("Nova %Y-%m-%d %H-%M-%S.png")
        if pix.save(str(SCREENSHOT_DIR / name)):
            QApplication.clipboard().setPixmap(pix)
            self.status(f"📸 Saved {name} to Pictures\\Nova Browser (also copied)", 6000)
        else:
            self.status("📸 Couldn't save the screenshot.")

    # ---------- focus mode ----------
    def focus_active(self):
        return time.time() < float(self.settings.get("focus_until") or 0)

    def focus_minutes_left(self):
        return max(1, int((float(self.settings["focus_until"]) - time.time() + 59) // 60))

    def focus_blocks(self, url):
        if not self.focus_active():
            return False
        h = host_of(url)
        return bool(h) and any(h == s or h.endswith("." + s) for s in self.settings["focus_sites"])

    def start_focus(self, minutes):
        self.set_setting("focus_until", time.time() + minutes * 60)
        self.status(f"🎯 Focus mode on for {minutes} minutes. Distracting sites are blocked.", 6000)
        for v in self.views():
            if self.focus_blocks(v.url()):
                v.setUrl(v.url())          # the block page takes over
        self.tick()

    def stop_focus(self):
        if not self.focus_active():
            self.status("🎯 Focus mode isn't on.")
            return
        ans = QMessageBox.question(self, "End focus mode", "End your focus session early?")
        if ans == QMessageBox.StandardButton.Yes:
            self.set_setting("focus_until", 0)
            self.status("🎯 Focus mode ended.")
            self.tick()

    def edit_focus_sites(self):
        text, ok = QInputDialog.getMultiLineText(
            self, "Focus mode", "Sites blocked during focus mode (one per line):",
            "\n".join(self.settings["focus_sites"]))
        if ok:
            sites = []
            for line in text.splitlines():
                s = host_of(line.strip() if "://" in line else "https://" + line.strip())
                if s and s not in sites:
                    sites.append(s)
            self.set_setting("focus_sites", sites)
            self.status(f"🎯 {len(sites)} sites on the focus list.")

    def tick(self):
        self.ticks += 1
        self.count_screen_time()
        if self.ticks % 300 == 0:
            self.refresh_weather()                   # only refetches when the data is 20+ minutes old
        if self.ticks % 30 == 0:
            self.save_screen_time()
            self.memory_saver_check()
        if self.focus_active():
            left = int(float(self.settings["focus_until"]) - time.time())
            self.focus_label.setText(f"🎯 Focus {left // 60:02d}:{left % 60:02d}")
            self.focus_label.setVisible(bool(self.settings["focus_show_timer"]))
        elif self.settings.get("focus_until"):
            self.focus_label.hide()
            if True:
                self.set_setting("focus_until", 0)
                self.status("🎉 Focus session complete! Nice work.", 8000)
        n = self.adblock.blocked
        self.shield_btn.setText("🛡" if not self.adblock.enabled or not n else f"🛡 {n if n < 1000 else '999+'}")
        self.shield_btn.setToolTip(f"Ad & tracker blocker: {'on' if self.adblock.enabled else 'off'}, "
                                   f"{n} blocked this session")

    # ---------- themes ----------
    def apply_theme(self, name):
        self.set_option("theme", name)
        self.status(f"🎨 Accent: {name}")

    # ---------- float a tab (picture-in-picture for any site) ----------
    def float_tab(self, view=None):
        v = view or self.current()
        if v is None:
            return
        if self.tabs.count() <= 1:
            self.new_tab()                      # keep a tab in the main window
        self.tabs.removeTab(self.tabs.indexOf(v))
        fw = FloatWindow(self, v)
        self.floats.append(fw)
        fw.show()
        self.status("🪟 Tab floating on top. Press 🎬 Video only to make a video fill it.", 6000)

    def dock_float(self, fw):
        v = fw.view
        if fw in self.floats:
            self.floats.remove(fw)
        if v is None:
            return
        fw.view = None
        idx = self.tabs.addTab(v, "")
        self.refresh_tab_label(v)
        self.tabs.setCurrentIndex(idx)

    # ---------- split view ----------
    def toggle_split(self):
        if self.split is None:
            self.split = SplitPane(self)
            self.splitter.addWidget(self.split)
            cur = self.current().url() if self.current() else START_URL
            self.split.view.setUrl(cur if is_web(cur.toString()) else START_URL)
            w = self.splitter.width()
            self.splitter.setSizes([w // 2, w // 2])
            self.split.address.setFocus()
            self.status("◫ Split view on. Ctrl+\\ closes it.")
            return
        if self.split.isVisible():
            self.split.hide()
        else:
            self.split.show()
            w = self.splitter.width()
            self.splitter.setSizes([w // 2, w // 2])

    # ---------- memory saver ----------
    def wake(self, view):
        page = view.page()
        try:
            if page.lifecycleState() != QWebEnginePage.LifecycleState.Active:
                page.setLifecycleState(QWebEnginePage.LifecycleState.Active)
        except Exception:
            pass
        if getattr(view, "asleep", False):
            view.asleep = False
            self.refresh_tab_label(view)

    def sleep_tab(self, view, quiet=False):
        if view is self.current() or view.audible or getattr(view, "refresh_timer", None):
            return False
        try:
            view.page().setLifecycleState(QWebEnginePage.LifecycleState.Discarded)
        except Exception:
            return False
        view.asleep = True
        self.refresh_tab_label(view)
        if not quiet:
            self.status("💤 Tab is asleep. It wakes up when you open it.")
        return True

    def memory_saver_check(self):
        if not self.settings.get("memory_saver"):
            return
        limit = float(self.settings.get("sleep_minutes", 30)) * 60
        now = time.time()
        slept = 0
        for v in self.views():
            if getattr(v, "asleep", False) or v is self.current():
                continue
            if now - self.last_active.get(id(v), now) > limit and is_web(v.url().toString()):
                slept += self.sleep_tab(v, quiet=True)
        if slept:
            self.status(f"💤 Put {slept} unused tab{'s' if slept > 1 else ''} to sleep to save memory.", 5000)

    # ---------- auto-refresh ----------
    def set_auto_refresh(self, view, seconds):
        old = getattr(view, "refresh_timer", None)
        if old is not None:
            old.stop()
            old.deleteLater()
            view.refresh_timer = None
        if seconds:
            t = QTimer(view)
            t.setInterval(seconds * 1000)
            t.timeout.connect(view.reload)
            t.start()
            view.refresh_timer = t
            self.status(f"⟳ Auto-refreshing this tab every {seconds // 60} min" if seconds >= 60
                        else f"⟳ Auto-refreshing this tab every {seconds} s")
        else:
            self.status("⟳ Auto-refresh off")
        self.refresh_tab_label(view)

    # ---------- workspaces ----------
    def save_workspace(self):
        name, ok = QInputDialog.getText(self, "Save workspace", "Name this set of tabs (e.g. Anime, Coding):")
        name = (name or "").strip()
        if not ok or not name:
            return
        urls = [v.url().toString() for v in self.views() if not v.private and is_web(v.url().toString())]
        if not urls:
            self.status("🗂 No web tabs to save.")
            return
        self.workspaces[name] = urls
        save_json(WORKSPACES_FILE, self.workspaces)
        self.status(f"🗂 Saved workspace “{name}” ({len(urls)} tabs).")

    def open_workspace(self, name, replace=False):
        urls = self.workspaces.get(name, [])
        if not urls:
            return
        old = self.views() if replace else []
        for u in urls:
            self.new_tab(QUrl(u))
        for v in old:
            self.close_tab(self.tabs.indexOf(v))
        self.status(f"🗂 Opened workspace “{name}”.")

    def delete_workspace(self, name):
        self.workspaces.pop(name, None)
        save_json(WORKSPACES_FILE, self.workspaces)
        self.status(f"🗂 Deleted workspace “{name}”.")

    # ---------- read later ----------
    def save_for_later(self, view=None):
        v = view or self.current()
        url = v.url().toString()
        if not is_web(url):
            self.status("🔖 Only web pages can be saved for later.")
            return
        if not any(r["url"] == url for r in self.read_later):
            self.read_later.append({"title": getattr(v, "base_title", "") or url, "url": url,
                                    "saved": time.strftime("%Y-%m-%d")})
            save_json(READ_LATER_FILE, self.read_later)
        self.status(f"🔖 Saved for later ({len(self.read_later)} in your list).")

    def open_read_later(self, url):
        self.read_later = [r for r in self.read_later if r["url"] != url]
        save_json(READ_LATER_FILE, self.read_later)
        self.new_tab(QUrl(url))

    # ---------- site notes ----------
    def edit_site_note(self):
        h = host_of(self.current().url())
        if not h:
            self.status("📝 Notes work on websites.")
            return
        text, ok = QInputDialog.getMultiLineText(self, f"Notes for {h}", f"Your private notes for {h}:",
                                                 self.notes.get(h, ""))
        if not ok:
            return
        if text.strip():
            self.notes[h] = text
        else:
            self.notes.pop(h, None)
        save_json(NOTES_FILE, self.notes)
        self.status(f"📝 Note saved for {h}." if text.strip() else f"📝 Note removed for {h}.")

    # ---------- screen time ----------
    def count_screen_time(self):
        v = self.current()
        if v is None or v.private or not self.isActiveWindow() or not self.settings["screen_time_enabled"]:
            return
        h = host_of(v.url())
        if not h:
            return
        day = self.screen_time.setdefault(time.strftime("%Y-%m-%d"), {})
        day[h] = day.get(h, 0) + 1

    def save_screen_time(self):
        keep = {time.strftime("%Y-%m-%d", time.localtime(time.time() - d * 86400)) for d in range(14)}
        self.screen_time = {d: v for d, v in self.screen_time.items() if d in keep}
        save_json(SCREEN_TIME_FILE, self.screen_time)

    def show_screen_time(self):
        self.save_screen_time()
        ScreenTimeDialog(self, self.screen_time).exec()

    # ---------- paste & go, QR, chameleon ----------
    def paste_and_go(self):
        text = QApplication.clipboard().text().strip()
        if not text:
            self.status("📋 The clipboard is empty.")
            return
        self.new_tab(to_url(text.splitlines()[0][:2000]))

    def send_to_phone(self):
        url = self.current().url().toString()
        if not is_web(url):
            self.status("📱 Open a web page first.")
            return
        safe = url.replace("<", "%3C").replace(">", "%3E")
        QRDialog(self, safe).show()

    def apply_chameleon(self, view):
        if view is not self.current():
            return
        if not self.settings.get("chameleon"):
            self.toolbar.setStyleSheet("")
            return

        def got(color):
            from PyQt6.QtGui import QColor
            c = QColor(str(color or "").strip())
            if not c.isValid():
                self.toolbar.setStyleSheet("")
                return
            self.toolbar.setStyleSheet(f"QToolBar {{ border-bottom: 3px solid {c.name()}; }}")
        view.page().runJavaScript(THEME_COLOR_JS, got)

    def set_chameleon(self, on):
        self.set_option("chameleon", bool(on))
        self.status("🦎 Chameleon toolbar on: it takes each site's colour." if on else "🦎 Chameleon toolbar off")

    def on_link_hovered(self, url):
        if self.settings.get("link_hover_status", True):
            if url:
                self.statusBar().showMessage(url)
            else:
                self.statusBar().clearMessage()

    # ---------- customization: change options and apply them live ----------
    def set_option(self, key, value):
        self.set_options({key: value})

    def set_options(self, changes):
        groups = set()
        for key, value in changes.items():
            o = OPTION_BY_KEY.get(key)
            if o is not None and not valid_value(o, value):
                continue
            self.set_setting(key, value)
            groups.add(o["apply"] if o else ("start" if key == "custom_widgets" else "web" if key == "site_css" else "use"))
            if key in ("theme", "custom_accent", "base_palette", "sp_font"):
                groups.add("start")
        if "chrome" in groups:
            self.apply_chrome()
            groups.add("start")
        if "web" in groups:
            self.apply_web()
        if "keys" in groups:
            self.apply_keys()
        if "hub" in groups:
            self.apply_hub()
        if "extras" in groups:
            self.apply_extras()
        if "nova" in groups or "chrome" in groups:
            self.apply_nova_ui()
        if "start" in groups:
            self.start_timer.start()            # rebuild the start page a moment after the last change
        if "chameleon" in changes and self.current():
            self.apply_chameleon(self.current())

    def apply_all(self):
        self.apply_chrome()
        self.apply_web()
        self.apply_keys()
        self.apply_nova_ui()
        self.rebuild_start(reload=False)

    def rebuild_start(self, reload=True):
        try:
            build_start_page(self.settings, self.bookmarks, self.history, self.read_later, self.screen_time,
                             self.weather_for_page(), self.hub_start_data())
        except Exception as e:
            self.status(f"Couldn't build the start page: {e}")
            return
        if reload:
            for v in self.views():
                if is_start_page(v.url()):
                    v.reload()
        self.refresh_weather()

    # ---------- weather for the start page widget ----------
    def weather_for_page(self):
        w = self.weather
        return {"city": w.get("city", ""), "units": w.get("units", ""), "data": w.get("data"), "error": w.get("error", "")}

    def refresh_weather(self):
        s = self.settings
        city = (s.get("w_weather_city") or "").strip()
        if s.get("w_weather_pos") == "Hidden" or not city:
            return
        key = (city.lower(), s["w_weather_units"])
        w = self.weather
        if w.get("busy") or (w.get("key") == key and time.time() - w.get("t", 0) < 1200):
            return
        w.update(busy=True, key=key)
        unit = "celsius" if s["w_weather_units"] == "°C" else "fahrenheit"
        geo = QUrl("https://geocoding-api.open-meteo.com/v1/search?count=1&name=" + urllib.parse.quote(city))
        self.get_json(geo, lambda d, err: self.weather_got_place(d, err, key, city, s["w_weather_units"], unit))

    def get_json(self, url, done):
        req = QNetworkRequest(url)
        req.setTransferTimeout(15000)
        reply = self.net.get(req)

        def finished():
            err = "" if reply.error() == QNetworkReply.NetworkError.NoError else (reply.errorString() or "offline")
            data = None
            if not err:
                try:
                    data = json.loads(bytes(reply.readAll()).decode("utf-8"))
                except ValueError:
                    err = "bad answer from the weather service"
            reply.deleteLater()
            done(data, err)
        reply.finished.connect(finished)

    def weather_got_place(self, d, err, key, city, units, unit):
        places = (d or {}).get("results") or []
        if err or not places:
            self.weather_done(key, city, units, None, err or "city not found")
            return
        p = places[0]
        url = QUrl(f"https://api.open-meteo.com/v1/forecast?latitude={p['latitude']}&longitude={p['longitude']}"
                   "&current=temperature_2m,weather_code,wind_speed_10m"
                   "&daily=weather_code,temperature_2m_max,temperature_2m_min&timezone=auto"
                   f"&temperature_unit={unit}")
        self.get_json(url, lambda d2, e2: self.weather_done(
            key, city, units, dict(d2, place=p.get("name", city)) if isinstance(d2, dict) and not e2 else None, e2))

    def weather_done(self, key, city, units, data, err):
        # On failure, try again in about 2 minutes instead of 20
        self.weather.update(busy=False, key=key, city=city, units=units, data=data,
                            error="" if data else (err or "unavailable"),
                            t=time.time() if data else time.time() - 1200 + 120)
        payload = json.dumps(self.weather_for_page()).replace("</", "<\\/")
        try:
            build_start_page(self.settings, self.bookmarks, self.history, self.read_later, self.screen_time,
                             self.weather_for_page(), self.hub_start_data())
        except Exception:
            pass
        for v in self.views():                    # update open start pages without reloading them
            if is_start_page(v.url()):
                v.page().runJavaScript(f"window.novaWeather && window.novaWeather({payload})")

    def set_window_flag(self, flag, on):
        """Changing a window flag hides the window; put it back the way it was."""
        was_visible, was_max = self.isVisible(), self.isMaximized()
        self.setWindowFlag(flag, on)
        if was_visible:
            self.showMaximized() if was_max else self.show()
            round_window_corners(self)

    def changeEvent(self, e):
        if e.type() == QEvent.Type.WindowStateChange and hasattr(self, "titlebar"):
            self.titlebar.update_max_icon()
        super().changeEvent(e)

    def showEvent(self, e):
        super().showEvent(e)
        if self.windowFlags() & Qt.WindowType.FramelessWindowHint:
            round_window_corners(self)

    def apply_chrome(self):
        s = self.settings
        set_theme_from(s)
        CURRENT_SEARCH["url"] = search_template(s)
        QApplication.instance().setStyleSheet(themed(DARK_STYLE) + chrome_extra_style(s))
        bar = self.tabs.bar
        if s["tab_position"] == "Bottom":
            if bar.parent() is not self.body_layout.parentWidget():
                self.body_layout.insertWidget(1, bar)
            bar.setShape(QTabBar.Shape.RoundedSouth)
        else:
            if bar.parent() is not self.titlebar:
                self.titlebar.tab_slot.addWidget(bar)
            bar.setShape(QTabBar.Shape.RoundedNorth)
        frameless = bool(s["custom_titlebar"])
        if frameless != bool(self.windowFlags() & Qt.WindowType.FramelessWindowHint):
            self.set_window_flag(Qt.WindowType.FramelessWindowHint, frameless)
        self.titlebar.set_window_buttons(frameless)
        self.tabs.setTabsClosable(bool(s["tab_close_buttons"]))
        self.tabs.setMovable(bool(s["tabs_movable"]))
        area = Qt.ToolBarArea.BottomToolBarArea if s["toolbar_position"] == "Bottom" else Qt.ToolBarArea.TopToolBarArea
        if self.toolBarArea(self.toolbar) != area:
            self.removeToolBar(self.toolbar)
            if area == Qt.ToolBarArea.TopToolBarArea:
                self.addToolBarBreak(Qt.ToolBarArea.TopToolBarArea)
            self.addToolBar(area, self.toolbar)
            self.toolbar.show()
        if not self.video_fullscreen:
            self.statusBar().setVisible(bool(s["show_status_bar"]))
        self.setWindowOpacity(int(s["window_opacity"]) / 100)
        on_top = bool(self.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
        if on_top != bool(s["always_on_top"]):
            self.set_window_flag(Qt.WindowType.WindowStaysOnTopHint, bool(s["always_on_top"]))
        self.address.setAlignment(Qt.AlignmentFlag.AlignCenter if s["address_centered"]
                                  else Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        for name, act in self.tb.items():
            act.setVisible(bool(s.get(f"show_btn_{name}", True)) and self.hub_button_ok(name))
        self.build_hub_pages()
        for v in self.views():
            self.refresh_tab_label(v)
        if self.customize is not None:
            self.customize.setStyleSheet(themed(CUSTOMIZE_STYLE))

    def apply_web(self):
        s = self.settings
        CURRENT_SEARCH["url"] = search_template(s)
        A = QWebEngineSettings.WebAttribute
        attrs = {"smooth_scroll": "ScrollAnimatorEnabled", "show_scrollbars": "ShowScrollBars", "javascript": "JavascriptEnabled",
                 "images": "AutoLoadImages", "popups": "JavascriptCanOpenWindows", "autoplay_gesture": "PlaybackRequiresUserGesture",
                 "pdf_viewer": "PdfViewerEnabled", "webgl": "WebGLEnabled", "canvas_accel": "Accelerated2dCanvasEnabled",
                 "local_storage": "LocalStorageEnabled", "dns_prefetch": "DnsPrefetchEnabled", "spatial_nav": "SpatialNavigationEnabled",
                 "print_backgrounds": "PrintElementBackgrounds", "error_pages": "ErrorPageEnabled",
                 "focus_on_load": "FocusOnNavigationEnabled"}
        F, FS = QWebEngineSettings.FontFamily, QWebEngineSettings.FontSize
        for p in self.profiles():
            ps = p.settings()
            for key, name in attrs.items():
                a = getattr(A, name, None)
                if a is not None:
                    ps.setAttribute(a, bool(s[key]))
            ps.setFontFamily(F.StandardFont, s["page_font"])
            ps.setFontFamily(F.SansSerifFont, s["page_font"])
            ps.setFontFamily(F.FixedFont, s["page_fixed_font"])
            ps.setFontSize(FS.DefaultFontSize, int(s["page_font_size"]))
            ps.setFontSize(FS.DefaultFixedFontSize, max(9, int(s["page_font_size"]) - 3))
            ps.setFontSize(FS.MinimumFontSize, int(s["min_font_size"]))
            p.setHttpUserAgent(USER_AGENTS.get(s["user_agent"]) or self.default_ua[id(p)])
            if s["accept_language"].strip():
                p.setHttpAcceptLanguage(s["accept_language"].strip())
            p.setHttpCacheMaximumSize(int(s["cache_size_mb"]) * 1024 * 1024)
        self.adblock.enabled = bool(s["adblock"])
        self.adblock.dnt = bool(s["dnt"])
        self.adblock.gpc = bool(s["gpc"])
        self.apply_dark_web()
        self.install_page_scripts()

    def cookie_filter(self, request):
        try:
            return not (self.settings.get("block_3p_cookies") and request.thirdParty)
        except Exception:
            return True

    def install_page_scripts(self):
        """Scripts every page gets: the video speed control and your own CSS."""
        s = self.settings
        user_css = s.get("site_css") or {}
        css_js = (r"""(function(){if(location.protocol==='file:')return;var M=%s,G=%s,h=location.hostname.replace(/^www\./,''),css=G;
for(var k in M){if(h===k||h.slice(-k.length-1)==='.'+k)css+='\n'+M[k];}if(!css.trim())return;
var s=document.getElementById('nova-user-css')||document.createElement('style');s.id='nova-user-css';s.textContent=css;
(document.head||document.documentElement).appendChild(s);})();""" % (json.dumps(user_css), json.dumps(s.get("global_css") or "")))
        for p in self.profiles():
            for name in ("nova-speed", "nova-user-css"):
                for old in p.scripts().find(name):
                    p.scripts().remove(old)
            p.scripts().insert(make_script("nova-speed", video_speed_js(bool(s["speed_badge"])), all_frames=True))
            for old in p.scripts().find("nova-zaps"):
                p.scripts().remove(old)
            if EX is not None and getattr(self, "zaps", None):
                p.scripts().insert(make_script("nova-zaps", EX.zap_css_script(self.zaps),
                                               point=QWebEngineScript.InjectionPoint.DocumentCreation))
            if user_css or (s.get("global_css") or "").strip():
                p.scripts().insert(make_script("nova-user-css", css_js))

    def apply_keys(self):
        used = {}
        for cid, act in self.key_actions.items():
            seq = self.settings.get(f"key_{cid}", "")
            act.setShortcut(QKeySequence(seq) if seq else QKeySequence())
            if seq:
                used.setdefault(seq, []).append(cid)
        clashes = [k for k, ids in used.items() if len(ids) > 1]
        if clashes:
            self.status(f"⌨ These keys are used twice and won't work until you change one: {', '.join(clashes)}", 8000)
        labels = {cid: label for cid, label, _d in KEY_COMMANDS}
        for name, cid in (("back", "back"), ("forward", "forward"), ("reload", "reload"), ("home", "home"),
                          ("star", "bookmark"), ("newtab", "new_tab"), ("nova", "nova"), ("customize", "customize")):
            key = self.settings.get(f"key_{cid}", "")
            self.tb[name].setToolTip(labels[cid] + (f" ({key})" if key else ""))

    def apply_nova_ui(self):
        if self.nova_panel is None:
            return
        s = self.settings
        self.nova_panel.setStyleSheet(themed(NOVA_STYLE))
        self.nova_panel.speak = bool(s["nova_speaks"])
        self.nova_panel.update_voice_button()
        self.nova_panel.set_chips()
        self.nova_panel.render()
        area = Qt.DockWidgetArea.LeftDockWidgetArea if s["nova_side"] == "Left" else Qt.DockWidgetArea.RightDockWidgetArea
        if self.dockWidgetArea(self.nova_dock) != area:
            visible = self.nova_dock.isVisible()
            self.removeDockWidget(self.nova_dock)
            self.addDockWidget(area, self.nova_dock)
            self.nova_dock.setVisible(visible)
        if self.nova_dock.isVisible():
            self.resizeDocks([self.nova_dock], [int(s["nova_width"])], Qt.Orientation.Horizontal)

    def open_customize(self):
        if self.customize is None:
            self.customize = CustomizeDialog(self)
        self.customize.setStyleSheet(themed(CUSTOMIZE_STYLE))
        self.customize.refresh()
        self.customize.show()
        self.customize.raise_()
        self.customize.activateWindow()

    def add_reward_packs(self, menu, apply):
        """Adds the style packs you unlock with XP to a packs menu (locked ones show what level they need)."""
        for a in [a for a in menu.actions() if a.property("reward")]:
            menu.removeAction(a)
        if HUB is None or self.hub is None or not self.settings.get("xp_on", True):
            return
        sep = menu.addSeparator()
        sep.setProperty("reward", True)
        lv = self.hub.level()
        for name, (need, desc, _s) in HUB.REWARD_PACKS.items():
            ok = lv >= need
            act = menu.addAction(("🏆 " if ok else "🔒 ") + name + ("" if ok else f"   (reach level {need})"))
            act.setProperty("reward", True)
            act.setToolTip(desc)
            act.setEnabled(ok)
            act.triggered.connect(lambda _=False, n=name: apply(n))

    def apply_pack(self, name):
        if name not in STYLE_PACKS and HUB is not None and name in HUB.REWARD_PACKS:
            if self.hub is None or not self.hub.reward_unlocked(name):
                self.status(f"🔒 {name} unlocks at level {HUB.REWARD_PACKS[name][0]}. Earn XP in 🎮 Games → 🏆.")
                return
            self.set_options(dict(HUB.REWARD_PACKS[name][2]))
            self.status(f"🏆 Reward style pack: {name}")
            return
        changes = dict(STYLE_PACKS.get(name, {}))
        if name == "Nova Classic":
            changes = {k: o["default"] for k, o in OPTION_BY_KEY.items()
                       if o["cat"] in ("Appearance", "Wallpaper", "Widget style")}
            changes.update({"sp_logo_style": "Glow", "sp_logo_font": "Segoe UI", "sp_font": "Segoe UI", "w_clock_style": "Digital"})
        self.set_options(changes)
        self.status(f"✨ Style pack: {name}")

    def surprise_me(self):
        import random
        hue = random.random()
        r, g, b = colorsys.hls_to_rgb(hue, random.uniform(.58, .68), random.uniform(.75, .95))
        accent = "#%02x%02x%02x" % (int(r * 255), int(g * 255), int(b * 255))
        animated = [w for w in WALLPAPERS if w not in ("Gradient", "Solid colour", "Your image", "Your video", "Slideshow")]
        pick = lambda key: random.choice(OPTION_BY_KEY[key]["choices"])
        self.set_options({
            "theme": "Custom", "custom_accent": accent, "base_palette": pick("base_palette"),
            "wp_type": random.choice(animated), "wp_color_mode": random.choice(["Accent", "Accent", "Rainbow"]),
            "wp_speed": random.randint(3, 7), "wp_density": random.randint(3, 8),
            "wg_style": pick("wg_style"), "tab_shape": pick("tab_shape"), "sp_logo_style": pick("sp_logo_style"),
            "sp_logo_font": random.choice(["Segoe UI", "Bahnschrift", "Georgia", "Cascadia Code", "Impact", "Trebuchet MS"]),
            "w_clock_style": pick("w_clock_style"), "sp_search_style": pick("sp_search_style"),
            "sp_tile_shape": pick("sp_tile_shape"), "sp_tile_style": pick("sp_tile_style"), "address_style": pick("address_style"),
        })
        self.status("🎲 Surprise! Press 🎲 again for another look, or ⚙ Customize → ⋯ → Reset to go back.", 7000)

    # ---------- 🎮 Games + 📣 Following hubs ----------
    def hub_button_ok(self, name):
        if name == "nova":
            return bool(self.settings.get("nova_on", True))
        if name == "mic":
            return EX is not None and bool(self.settings.get("voice_on", True))
        if name == "ram":
            return EX is not None and bool(self.settings.get("ram_meter", True))
        if name == "gamemode":
            return EX is not None
        if name == "games":
            return self.hub is not None and bool(self.settings.get("hub_games", True))
        if name == "follow":
            return self.hub is not None and bool(self.settings.get("hub_follow", True))
        return True

    def hub_start_data(self):
        if self.hub is None:
            return {}
        try:
            return self.hub.start_data()
        except Exception:
            return {}

    def hub_colors(self):
        a, light, _ = theme_colors()
        return {"accent": a, "accent_light": light, "bg": pal("page"), "card": pal("card"), "field": pal("field"),
                "line": pal("border"), "text": pal("text"), "dim": pal("dim")}

    def build_hub_pages(self):
        """(Re)writes the hub + game pages when the colours change; open ones reload."""
        if self.hub is None:
            return
        colors = self.hub_colors()
        if colors == self._hub_colors and HUB.hub_file(DATA_DIR, "games").exists():
            return
        try:
            HUB.build_pages(DATA_DIR, colors)
        except Exception as e:
            print("[hubs] couldn't write pages:", e)
            return
        had = self._hub_colors is not None
        self._hub_colors = colors
        if had:
            play_dir = os.path.normcase(str(HUB.hub_dir(DATA_DIR)))
            for v in self.views():
                u = v.url()
                if u.isLocalFile() and os.path.normcase(os.path.abspath(u.toLocalFile())).startswith(play_dir):
                    v.reload()

    def open_hub(self, kind, tab=None):
        if self.hub is None:
            self.status("The 🎮 Games and 📣 Following hubs need nova_hub.py in the same folder as the browser.", 8000)
            return
        tab = tab if tab and re.fullmatch(r"[a-z]{2,12}", str(tab)) else None
        self.build_hub_pages()
        for i, v in enumerate(self.views()):
            if HUB.hub_kind_of(v.url(), DATA_DIR) == kind:
                self.tabs.setCurrentIndex(i)
                if tab:
                    v.page().runJavaScript(f"location.hash = '{tab}';")
                return
        url = QUrl.fromLocalFile(str(HUB.hub_file(DATA_DIR, kind)))
        if tab:
            url.setFragment(tab)
        cur = self.current()
        if cur is not None and is_start_page(cur.url()) and not cur.private:
            cur.setUrl(url)
        else:
            self.new_tab(url, private=False)

    def open_game(self, gid):
        if self.hub is None:
            return
        self.build_hub_pages()
        self.new_tab(QUrl.fromLocalFile(str(HUB.hub_dir(DATA_DIR) / "play" / f"{gid}.html")), private=False)

    def open_customize_hubs(self):
        self.open_customize()
        try:
            items = self.customize.cats.findItems("Games & Following", Qt.MatchFlag.MatchExactly)
            if items:
                self.customize.cats.setCurrentItem(items[0])
        except Exception:
            pass

    def apply_hub(self):
        for name in ("games", "follow"):
            if name in self.tb:
                self.tb[name].setVisible(bool(self.settings.get(f"show_btn_{name}", True)) and self.hub_button_ok(name))
        if not self.settings.get("hub_windows_notify") and self.tray is not None:
            self.tray.hide()
            self.tray.deleteLater()
            self.tray = None
        if self.hub is not None:
            self.hub.changed.emit()
            QTimer.singleShot(600, self.hub.refresh)
        self.update_hub_badges()
        self.start_timer.start()

    def on_hub_changed(self):
        self.update_hub_badges()
        if self.voice is not None and self.voice.state == "connected":
            self.voice_push_timer.start()
        data = self.hub_start_data()
        try:      # keep the start page file current without reloading open start pages
            build_start_page(self.settings, self.bookmarks, self.history, self.read_later, self.screen_time,
                             self.weather_for_page(), data)
        except Exception:
            pass
        payload = json.dumps(data).replace("</", "<\\/")
        for v in self.views():
            if is_start_page(v.url()):
                v.page().runJavaScript(f"window.novaHubData && window.novaHubData({payload})")

    def update_hub_badges(self):
        if self.hub is None:
            return
        show = bool(self.settings.get("hub_badges", True))
        for name, kind, icon in (("games", "games", "🎮"), ("follow", "follow", "📣")):
            if name not in self.tb:
                continue
            n = self.hub.unread(kind) if show else 0
            self.tb[name].setText(icon if not n else f"{icon} {n if n < 100 else '99+'}")

    def on_hub_notify(self, icon, title, body, url):
        hub = {"🎮": "games", "🎁": "games:free", "💸": "games:deals", "🏆": "games:profile", "⭐": "games:profile",
               "📺": "follow:anime"}.get(icon, "follow")
        if self.game_mode and self.settings.get("game_mode_hold_alerts", True):
            self.gm_held.append((icon, title, body, url, hub))        # shown when you're done playing
            return
        self.show_toast(icon, title, body, url, hub)
        if self.settings.get("hub_windows_notify") and (not self.isActiveWindow() or self.isMinimized()):
            tray = self.ensure_tray()
            if tray is not None:
                self._tray_url = url
                tray.showMessage(f"{icon} {title}", body, QSystemTrayIcon.MessageIcon.Information, 8000)

    def show_toast(self, icon, title, body, url, hub):
        while len(self.toasts) >= 4:
            self.toasts[0].dismiss()
        t = Toast(self, icon, title, body, url, hub)
        self.toasts.append(t)
        t.adjustSize()
        t.show()
        self.place_toasts()

    def place_toasts(self):
        bottom = self.height() - (self.statusBar().height() if self.statusBar().isVisible() else 0) - 16
        for t in reversed(self.toasts):
            t.adjustSize()
            bottom -= t.height()
            t.move(self.width() - t.width() - 18, bottom)
            t.raise_()
            bottom -= 10

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if getattr(self, "toasts", None):
            self.place_toasts()
        if getattr(self, "voice_bubble", None) is not None and self.voice_bubble.isVisible():
            self.voice_bubble.place()

    def ensure_tray(self):
        if self.tray is None and QSystemTrayIcon.isSystemTrayAvailable():
            icon = QApplication.instance().windowIcon()
            if icon.isNull():
                icon = self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
            self.tray = QSystemTrayIcon(icon, self)
            self.tray.setToolTip("Nova Browser")
            self.tray.messageClicked.connect(self.on_tray_clicked)
            self.tray.activated.connect(lambda reason: self.bring_to_front())
            self.tray.show()
        return self.tray

    def on_tray_clicked(self):
        self.bring_to_front()
        if self._tray_url:
            self.new_tab(QUrl(self._tray_url), private=False)

    def bring_to_front(self):
        if self.isMinimized():
            self.showNormal()
        self.raise_()
        self.activateWindow()

    # ---------- ✦ Nova page helpers ----------
    def summarize_page(self, question=None):
        v = self.current()
        if not is_web(v.url().toString()):
            self.status("✦ Open a web page first, then Nova can summarize it.")
            return
        if not self.settings.get("nova_on", True) or (self.nova_panel is not None and not self.nova_panel.online):
            self.reader_mode()
            self.status("✦ Summaries need Nova running, so here's reader mode instead (or say “read this page”).", 6000)
            return
        if self.hub is not None:
            self.hub.xp_event("summarize")
        self.ask_nova(question or "Summarize this page for me in a few short bullet points.")

    def push_voice_state(self):
        if self.voice is None or self.hub is None:
            return
        if time.time() - self._voice_push_at < 15:
            self.voice_push_timer.start(int((15 - (time.time() - self._voice_push_at)) * 1000) + 100)
            return
        self._voice_push_at = time.time()
        try:
            data = self.hub.voice_summary()
        except Exception:
            return
        data["games"] = [{"id": g["id"], "name": g["name"]} for g in HUB.GAMES] if HUB else []
        data["sidebar"] = [a[1] for a in self.side_apps]
        self.voice.push("/hubstate", data)

    # ---------- 🕹 Game Mode ----------
    def toggle_game_mode(self):
        if self.game_mode:
            running = (self.game_mode.get("game") or {}).get("id", "")
            self.exit_game_mode()
            self._gm_dismissed = running or "manual"
        else:
            self.enter_game_mode(None, manual=True)

    def on_game_launched(self, game):
        if self.settings.get("game_mode_auto", True) and not self.game_mode and EX is not None:
            self.enter_game_mode(game, manual=False)

    def enter_game_mode(self, game=None, manual=False):
        if self.game_mode or EX is None:
            return
        s = self.settings
        cur = self.current()
        muted, slept = [], 0
        views = self.views() + ([self.split.view] if self.split is not None else [])
        for v in views:
            page = v.page()
            if s.get("game_mode_pause", True):
                page.runJavaScript("document.querySelectorAll('video,audio').forEach(function(m){try{m.pause()}catch(e){}});")
            if s.get("game_mode_mute", True) and not page.isAudioMuted():
                page.setAudioMuted(True)
                muted.append(v)
        if s.get("game_mode_sleep", True):
            for v in self.views():
                if v is cur or getattr(v, "asleep", False) or getattr(v, "refresh_timer", None):
                    continue
                try:
                    v.page().setLifecycleState(QWebEnginePage.LifecycleState.Discarded)
                    v.asleep = True
                    slept += 1
                except Exception:
                    pass
        for v in self.views():
            self.refresh_tab_label(v)
        self.game_mode = {"since": time.time(), "game": dict(game or {}), "manual": manual, "muted": muted,
                          "seen": False, "misses": 0}
        QTimer.singleShot(0, self.apply_voice)
        self.gm_held = []
        self.tb["gamemode"].setText("🕹 ON")
        self.tb["gamemode"].setToolTip("Game Mode is on (click to turn it off)")
        name = (game or {}).get("name") or ""
        bits = []
        if slept:
            bits.append(f"{slept} tab{'s' if slept != 1 else ''} asleep")
        if s.get("game_mode_mute", True):
            bits.append("sound off")
        if s.get("game_mode_hold_alerts", True):
            bits.append("alerts on hold")
        self.show_toast("🕹", "Game Mode on" + (f" · {name}" if name else ""), (", ".join(bits) or "Ready") + ". Have fun!", "", "games")
        if self.hub is not None:
            self.hub.xp_event("game_mode")
        if s.get("game_mode_minimize", False):
            QTimer.singleShot(1500, self.showMinimized)

    def exit_game_mode(self):
        gm = self.game_mode
        if not gm:
            return
        self.game_mode = None
        QTimer.singleShot(0, self.apply_voice)
        alive = set(id(v) for v in self.views() + ([self.split.view] if self.split is not None else []))
        for v in gm.get("muted", []):
            if id(v) in alive:
                try:
                    v.page().setAudioMuted(False)
                except RuntimeError:
                    pass
        for v in self.views():
            self.refresh_tab_label(v)
        self.tb["gamemode"].setText("🕹")
        self.tb["gamemode"].setToolTip("Game Mode (Ctrl+Shift+E)")
        mins = max(1, int((time.time() - gm["since"]) / 60))
        held, self.gm_held = self.gm_held, []
        body = f"Welcome back! That was {mins} min." + (f" {len(held)} alert{'s' if len(held) != 1 else ''} waited for you." if held else "")
        self.show_toast("🕹", "Game Mode off", body, "", "games")
        for icon, title, b, url, hub in held[-3:]:
            self.show_toast(icon, title, b, url, hub)

    def gm_check(self):
        """Every 15 s: is one of your linked games running? (Only looks at program paths, nothing else.)"""
        if EX is None or self.hub is None:
            return
        s = self.settings
        if not self.game_mode and not s.get("game_mode_detect", True):
            return
        games = list(self.hub.games)
        if not games:
            return
        try:
            appid = EX.steam_running_appid()
            paths = EX.running_paths() if any(g.get("dir") for g in games) else set()
            running = EX.detect_running_game(games, appid, paths)
        except Exception as e:
            print("[game mode]", e)
            return
        if self.game_mode:
            gm = self.game_mode
            if running:
                gm["seen"], gm["misses"] = True, 0
                return
            if gm["manual"] or not s.get("game_mode_exit", True):
                return
            if gm["seen"]:
                gm["misses"] += 1
                if gm["misses"] >= 2:
                    self.exit_game_mode()
            elif time.time() - gm["since"] > 600:
                gm["manual"] = True                     # never spotted the game: you turn it off yourself
            return
        if not running:
            self._gm_dismissed = ""
            return
        if running.get("id") != self._gm_dismissed and self._gm_dismissed != "manual":
            self.enter_game_mode(running)
            if self.game_mode:
                self.game_mode["seen"] = True

    # ---------- 🧠 tab manager + memory meter ----------
    def open_tab_manager(self):
        if EX is None:
            self.status("The tab manager needs nova_extras.py next to the browser.")
            return
        if self.tab_manager is None or not self.tab_manager.isVisible():
            self.tab_manager = TabManager(self)
            self.tab_manager.show()
        else:
            self.tab_manager.raise_()
            self.tab_manager.activateWindow()

    def update_ram_button(self):
        act = self.tb.get("ram")
        if act is None or EX is None or not act.isVisible() or self.isMinimized():
            return
        try:
            total, _per = EX.browser_memory()
        except Exception:
            return
        act.setText(f"🧠 {EX.fmt_bytes(total)}")
        act.setToolTip(f"Nova Browser is using {EX.fmt_bytes(total)} of memory. Click for the tab manager (Shift+Esc).")

    # ---------- 🖱 gestures ----------
    def gesture_label(self, code):
        label = self.settings.get(f"gesture_{code}", "Nothing")
        return label if label in GESTURE_ID else "Nothing"

    def run_gesture(self, code):
        label = self.gesture_label(code)
        cid = GESTURE_ID.get(label)
        if not cid or cid not in self.key_fns:
            self.status(f"🖱  {EX.gesture_arrows(code)}  isn't set to anything (🎨 Customize → Gestures & Zapper).", 2500)
            return
        self.status(f"🖱  {EX.gesture_arrows(code)}   {label}", 1500)
        try:
            self.key_fns[cid]()
        except Exception as e:
            self.status(f"🖱  {label} didn't work: {e}", 5000)
            return
        if self.hub is not None:
            self.hub.xp_event("gesture")

    # ---------- 🎯 zapper ----------
    def start_zapper(self, view=None):
        view = view or self.current()
        if EX is None or not is_web(view.url().toString()):
            self.status("🎯 The zapper works on websites.")
            return
        page = view.page()
        page.zapping = True
        page.runJavaScript(EX.ZAPPER_JS)
        self.status("🎯 Click the things you want gone on this site. Ctrl+Z undoes, Esc finishes.", 6000)

    def on_zap_message(self, page, msg):
        host = EX.zap_host(page.url().host())
        if not host:
            return
        kind, _, rest = msg.partition("{")
        try:
            data = json.loads("{" + rest) if rest else {}
        except ValueError:
            data = {}
        sel = str(data.get("sel", ""))
        if kind == "__novazap__" and EX.valid_selector(sel):
            lst = self.zaps.setdefault(host, [])
            if sel not in lst:
                lst.append(sel)
                del lst[:-200]
            self.zap_save_timer.start()
            if self.hub is not None:
                self.hub.xp_event("zap")
            self.status(f"🎯 Zapped on {host}. It stays hidden there. Ctrl+Z undoes, Esc finishes.", 4000)
        elif kind == "__novaunzap__" and sel in self.zaps.get(host, []):
            self.zaps[host].remove(sel)
            if not self.zaps[host]:
                self.zaps.pop(host)
            self.zap_save_timer.start()
            self.status("↩ Un-zapped.", 2500)
        elif kind == "__novazapdone__":
            page.zapping = False
            n = len(self.zaps.get(host, []))
            self.status(f"🎯 Done. {n} thing{'s' if n != 1 else ''} hidden on {host}." if n else "🎯 Done.", 4000)

    def save_zaps(self):
        self.zap_save_timer.stop()
        save_json(ZAPS_FILE, self.zaps)
        self.install_page_scripts()

    def unzap_site(self, view=None):
        view = view or self.current()
        host = EX.zap_host(view.url().host()) if EX else ""
        if not host or host not in self.zaps:
            self.status("Nothing is zapped on this site.")
            return
        n = len(self.zaps.pop(host))
        self.save_zaps()
        view.reload()
        self.status(f"↩ Brought back {n} zapped thing{'s' if n != 1 else ''} on {host}.")

    # ---------- 📌 sidebar apps ----------
    def setup_sidebar(self):
        self.side_bar = QToolBar("Sidebar apps", self)
        self.side_bar.setObjectName("SideBar")
        self.side_bar.setMovable(False)
        self.side_bar.setOrientation(Qt.Orientation.Vertical)
        self.side_bar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.side_stack = QStackedWidget()
        self.side_dock = QDockWidget(self)
        self.side_dock.setObjectName("SideDock")
        self.side_dock.setWidget(self.side_stack)
        self.side_dock.setTitleBarWidget(QWidget())
        self.side_dock.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, self.side_bar)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.side_dock)
        self.side_dock.hide()
        self.side_bar.hide()

    def apply_extras(self):
        s = self.settings
        for name in ("nova",):
            if name in self.tb:
                self.tb[name].setVisible(bool(s.get(f"show_btn_{name}", True)) and self.hub_button_ok(name))
        if not s.get("nova_on", True) and self.nova_dock is not None:
            self.nova_dock.hide()
        self.apply_voice()
        if EX is not None and s.get("voice_on", True) and self.voice_model_path() \
                and os.path.basename(self.voice_model_path()) != self.voice_model_name() \
                and not getattr(self, "_model_offer", False) and not EX.voice_addons_missing():
            self._model_offer = True
            QTimer.singleShot(400, self.open_voice_setup)
        for name in ("ram", "gamemode", "mic"):
            if name in self.tb:
                self.tb[name].setVisible(bool(s.get(f"show_btn_{name}", True)) and self.hub_button_ok(name))
        if self.hub_button_ok("ram") and s.get("show_btn_ram", True):
            self.ram_timer.start()
            QTimer.singleShot(1500, self.update_ram_button)
        else:
            self.ram_timer.stop()
        if self.side_bar is None:
            return
        apps = []
        if EX is not None and s.get("sidebar_on", True):
            apps = [(a[0], a[1], a[2], a[3]) for a in EX.SIDEBAR_APPS if s.get(f"sb_{a[0]}", a[4])]
            apps += EX.parse_custom_apps(s.get("sidebar_custom", ""))
        self.side_apps = apps
        ids = {a[0] for a in apps}
        for aid in [k for k in self.side_panels if k not in ids]:
            panel = self.side_panels.pop(aid)
            self.side_stack.removeWidget(panel)
            panel.view.setParent(None)
            panel.view.deleteLater()
            panel.deleteLater()
        for aid, panel in list(self.side_panels.items()):       # an address you changed reloads that app
            new = next(a for a in apps if a[0] == aid)
            if new != panel.app:
                self.side_panels.pop(aid)
                self.side_stack.removeWidget(panel)
                panel.view.setParent(None)
                panel.view.deleteLater()
                panel.deleteLater()
        self.side_bar.clear()
        self.side_actions = {}
        for aid, name, icon, url in apps:
            act = self.side_bar.addAction(icon)
            act.setToolTip(f"{name}  (Alt+B shows/hides)")
            act.setCheckable(True)
            act.triggered.connect(lambda _=False, a=aid: self.toggle_side_app(a))
            self.side_actions[aid] = act
        if apps:
            gear = self.side_bar.addAction("⚙")
            gear.setToolTip("Choose sidebar apps")
            gear.triggered.connect(self.open_customize_sidebar)
        area_t = Qt.ToolBarArea.RightToolBarArea if s.get("sidebar_side") == "Right" else Qt.ToolBarArea.LeftToolBarArea
        area_d = Qt.DockWidgetArea.RightDockWidgetArea if s.get("sidebar_side") == "Right" else Qt.DockWidgetArea.LeftDockWidgetArea
        if self.toolBarArea(self.side_bar) != area_t:
            self.removeToolBar(self.side_bar)
            self.addToolBar(area_t, self.side_bar)
        if self.dockWidgetArea(self.side_dock) != area_d:
            vis = self.side_dock.isVisible()
            self.removeDockWidget(self.side_dock)
            self.addDockWidget(area_d, self.side_dock)
            self.side_dock.setVisible(vis)
        self.side_bar.setVisible(bool(apps) and not self.video_fullscreen)
        if not apps or self.side_current not in ids:
            self.side_dock.hide()
            self.side_current = ""
        self.sync_side_actions()

    def sync_side_actions(self):
        vis = self.side_dock is not None and self.side_dock.isVisible()
        for aid, act in getattr(self, "side_actions", {}).items():
            act.setChecked(vis and aid == self.side_current)

    def open_side_app(self, aid, app=None):
        app = app or next((a for a in self.side_apps if a[0] == aid), None)
        if app is None or self.side_dock is None:
            return
        panel = self.side_panels.get(aid)
        if panel is None:
            panel = SidePanel(self, app)
            self.side_panels[aid] = panel
            self.side_stack.addWidget(panel)
        self.side_stack.setCurrentWidget(panel)
        self.side_current = aid
        if not self.side_dock.isVisible():
            self.side_dock.show()
            self.resizeDocks([self.side_dock], [int(self.settings.get("sidebar_width", 420))], Qt.Orientation.Horizontal)
        self.sync_side_actions()
        if self.hub is not None:
            self.hub.xp_event("sidebar")

    def toggle_side_app(self, aid):
        if self.side_dock.isVisible() and self.side_current == aid:
            self.hide_sidebar()
        else:
            self.open_side_app(aid)

    def toggle_sidebar(self):
        if self.side_dock is None or not self.side_apps:
            self.status("📌 Turn on sidebar apps in 🎨 Customize → Sidebar apps.")
            return
        if self.side_dock.isVisible():
            self.hide_sidebar()
        else:
            ids = [a[0] for a in self.side_apps]
            self.open_side_app(self.side_current if self.side_current in ids else ids[0])

    def hide_sidebar(self):
        if self.side_dock is not None:
            self.side_dock.hide()
        self.sync_side_actions()

    def open_customize_sidebar(self):
        self.open_customize()
        try:
            items = self.customize.cats.findItems("Sidebar apps", Qt.MatchFlag.MatchExactly)
            if items:
                self.customize.cats.setCurrentItem(items[0])
        except Exception:
            pass

    def handle_nova_url(self, url):
        """Links on the start page like nova://customize or nova://ask?q=..."""
        parts = urllib.parse.urlsplit(bytes(url.toEncoded()).decode("ascii", "replace"))
        action = (parts.netloc or parts.path.strip("/")).lower()
        if action == "customize" and not parts.query:
            self.open_customize()
        elif action in ("games", "following") and not parts.query:
            self.open_hub("games" if action == "games" else "follow")
        elif action == "anime":
            self.open_hub("follow", "anime")
        q = urllib.parse.parse_qs(parts.query)
        tab = q.get("tab", [""])[0]
        if action in ("games", "following") and tab:
            self.open_hub("games" if action == "games" else "follow", tab)
        elif action == "customize" and q.get("cat"):
            self.open_customize_cat(q["cat"][0])
        elif action in ("palette", "tour", "help", "voice", "voicehelp", "tabmanager", "gamemode", "zap", "sidebar",
                        "split", "focus", "screentime", "nova", "shortcuts"):
            {"palette": self.open_palette, "tour": self.show_tour, "help": self.open_help,
             "voice": lambda: self.start_listening(),
             "voicehelp": lambda: self.show_voice_help() if self.voice_ready() else self.open_voice_setup(),
             "tabmanager": self.open_tab_manager, "gamemode": self.toggle_game_mode, "zap": lambda: self.start_zapper(),
             "sidebar": self.toggle_sidebar, "split": self.toggle_split,
             "focus": lambda: self.start_focus(int(self.settings["focus_default"])), "screentime": self.show_screen_time,
             "nova": self.toggle_nova, "shortcuts": self.show_shortcuts}[action]()
        elif action == "ask":
            q = urllib.parse.parse_qs(parts.query).get("q", [""])[0].strip()
            if q:
                self.ask_nova(q[:1000])

    def go_home(self):
        home = (self.settings.get("home_url") or "").strip()
        if self.settings["home_button_opens"] == "Home address" and home:
            self.current().setUrl(to_url(home))
        else:
            self.rebuild_start(reload=False)
            self.current().setUrl(START_URL)

    def default_new_tab_url(self):
        choice = self.settings["new_tab_page"]
        home = (self.settings.get("home_url") or "").strip()
        if choice == "Blank page":
            return QUrl("about:blank")
        if choice == "Home address" and home:
            return to_url(home)
        self.rebuild_start(reload=False)
        return START_URL

    def cycle_tab(self, step):
        n = self.tabs.count()
        if n:
            self.tabs.setCurrentIndex((self.tabs.currentIndex() + step) % n)

    def toggle_window_fullscreen(self):
        if self.video_fullscreen:
            return
        self.showNormal() if self.isFullScreen() else self.showFullScreen()

    def print_page(self):
        v = self.current()
        if not is_web(v.url().toString()):
            self.status("🖨 Open a web page first.")
            return
        DOWNLOAD_DIR.mkdir(exist_ok=True)
        name = re.sub(r'[\\/:*?"<>|]+', " ", getattr(v, "base_title", "") or "page").strip()[:80] or "page"
        path = str(DOWNLOAD_DIR / f"{name}.pdf")
        v.page().printToPdf(path)
        self.status(f"🖨 Saved as PDF in Downloads: {name}.pdf", 6000)

    # ---------- menus, palette, misc ----------
    def fill_main_menu(self):
        m = self.main_menu
        m.clear()
        m.addAction("❓  Help & tour             F1").triggered.connect(lambda: self.open_help())
        m.addAction("🎨  Customize…              Ctrl+,").triggered.connect(self.open_customize)
        packs = m.addMenu("✨  Style packs")
        for name in STYLE_PACKS:
            packs.addAction(name).triggered.connect(lambda _=False, n=name: self.apply_pack(n))
        self.add_reward_packs(packs, self.apply_pack)
        m.addAction("🎲  Surprise me").triggered.connect(self.surprise_me)
        m.addSeparator()
        m.addAction("⌘  Command palette        Ctrl+K").triggered.connect(self.open_palette)
        m.addAction("🕶  New private tab        Ctrl+Shift+N").triggered.connect(lambda: self.new_tab(private=True))
        m.addAction("↺  Reopen closed tab      Ctrl+Shift+T").triggered.connect(self.reopen_closed)
        m.addSeparator()
        for label, key in (("🌙  Dark websites", "dark_web"), ("🛡  Block ads & trackers", "adblock"),
                           ("⟲  Reopen my tabs on start", "restore_session"),
                           ("💤  Memory saver (sleep unused tabs)", "memory_saver"),
                           ("🦎  Chameleon toolbar (site colours)", "chameleon")):
            act = m.addAction(label)
            act.setCheckable(True)
            act.setChecked(bool(self.settings[key]))
            if key == "dark_web":
                act.triggered.connect(lambda c: self.set_dark_web(c))
            elif key == "adblock":
                act.triggered.connect(lambda c: self.set_adblock(c))
            elif key == "chameleon":
                act.triggered.connect(lambda c: self.set_chameleon(c))
            else:
                act.triggered.connect(lambda c, k=key: self.set_option(k, c))
        themes = m.addMenu("🎨  Accent colour")
        for name in THEMES:
            act = themes.addAction(name)
            act.setCheckable(True)
            act.setChecked(name == self.settings["theme"])
            act.triggered.connect(lambda _=False, n=name: self.apply_theme(n))
        walls = m.addMenu("🖼  Wallpaper")
        for name in WALLPAPERS:
            act = walls.addAction(name)
            act.setCheckable(True)
            act.setChecked(name == self.settings["wp_type"])
            act.triggered.connect(lambda _=False, n=name: self.set_option("wp_type", n))
        m.addSeparator()
        focus = m.addMenu("🎯  Focus mode" + (f"  ({self.focus_minutes_left()} min left)" if self.focus_active() else ""))
        for mins in (25, 50, 90):
            focus.addAction(f"Focus for {mins} minutes").triggered.connect(lambda _=False, n=mins: self.start_focus(n))
        focus.addAction("End focus mode").triggered.connect(self.stop_focus)
        focus.addSeparator()
        focus.addAction("Edit blocked sites…").triggered.connect(self.edit_focus_sites)
        rl = m.addMenu(f"🔖  Read later ({len(self.read_later)})")
        if not self.read_later:
            rl.addAction("Nothing saved. Right-click a page → Save for later").setEnabled(False)
        for r in reversed(self.read_later[-30:]):
            rl.addAction(r["title"][:55]).triggered.connect(lambda _=False, u=r["url"]: self.open_read_later(u))
        if self.read_later:
            rl.addSeparator()
            rl.addAction("Open all").triggered.connect(
                lambda: [self.open_read_later(r["url"]) for r in list(self.read_later)])
        ws = m.addMenu("🗂  Workspaces")
        ws.addAction("Save current tabs as a workspace…").triggered.connect(self.save_workspace)
        if self.workspaces:
            ws.addSeparator()
            for name, urls in self.workspaces.items():
                sub = ws.addMenu(f"{name}  ({len(urls)} tabs)")
                sub.addAction("Open (add to my tabs)").triggered.connect(lambda _=False, n=name: self.open_workspace(n))
                sub.addAction("Switch to it (replace my tabs)").triggered.connect(
                    lambda _=False, n=name: self.open_workspace(n, replace=True))
                sub.addAction("Delete").triggered.connect(lambda _=False, n=name: self.delete_workspace(n))
        m.addAction("⏱  Screen time").triggered.connect(self.show_screen_time)
        if EX is not None:
            if self.settings.get("voice_on", True):
                m.addAction("🎤  Talk to the browser    Ctrl+Shift+Space").triggered.connect(lambda: self.start_listening())
                m.addAction("🎤  What can I say?").triggered.connect(
                    lambda: self.show_voice_help() if self.voice_ready() else self.open_voice_setup())
            m.addAction("🧠  Tab manager & memory   Shift+Esc").triggered.connect(self.open_tab_manager)
            m.addAction(("🕹  Turn Game Mode off" if self.game_mode else "🕹  Game Mode") + "   Ctrl+Shift+E").triggered.connect(
                self.toggle_game_mode)
            m.addAction("🎯  Zap things on this page   Alt+Z").triggered.connect(lambda: self.start_zapper())
            if self.side_apps:
                m.addAction("📌  Sidebar app   Alt+B").triggered.connect(self.toggle_sidebar)
        if self.hub is not None:
            if self.settings.get("hub_games", True):
                m.addAction("🎮  Games hub               Ctrl+Shift+G").triggered.connect(lambda: self.open_hub("games"))
            if self.settings.get("hub_follow", True):
                m.addAction("📣  Following hub           Ctrl+Shift+U").triggered.connect(lambda: self.open_hub("follow"))
        m.addSeparator()
        tools = m.addMenu("🧰  Page tools")
        tools.addAction("🪟  Float tab on top        Ctrl+Shift+F").triggered.connect(lambda: self.float_tab())
        tools.addAction("◫  Split view               Ctrl+\\").triggered.connect(self.toggle_split)
        tools.addAction("📝  Notes for this site     Ctrl+Shift+M").triggered.connect(self.edit_site_note)
        tools.addAction("📱  Send to phone (QR)").triggered.connect(self.send_to_phone)
        tools.addAction("📋  Paste and go            Ctrl+Shift+V").triggered.connect(self.paste_and_go)
        tools.addSeparator()
        tools.addAction("📖  Reader mode            F9").triggered.connect(self.reader_mode)
        tools.addAction("🔍  Find on page            Ctrl+F").triggered.connect(self.findbar.open_bar)
        tools.addAction("📸  Screenshot              Ctrl+Shift+S").triggered.connect(self.screenshot)
        tools.addAction("⏩  Video faster            Alt+]").triggered.connect(lambda: self.video_speed(1))
        tools.addAction("⏪  Video slower            Alt+[").triggered.connect(lambda: self.video_speed(-1))
        tools.addAction("▶  Video normal speed     Alt+\\").triggered.connect(lambda: self.video_speed(0, reset=True))
        tools.addAction("🔎  Zoom in                 Ctrl+=").triggered.connect(lambda: self.zoom(0.1))
        tools.addAction("🔎  Zoom out                Ctrl+-").triggered.connect(lambda: self.zoom(-0.1))
        tools.addAction("🔎  Reset zoom              Ctrl+0").triggered.connect(lambda: self.zoom(reset=True))
        m.addSeparator()
        m.addAction("📥  Downloads               Ctrl+J").triggered.connect(lambda: self.dl_btn.showMenu())
        m.addAction("🧹  Clear browsing data…").triggered.connect(self.clear_data)
        m.addAction("⌨  Keyboard shortcuts").triggered.connect(self.show_shortcuts)

    def open_palette(self):
        self.palette.open_palette()

    def palette_entries(self):
        entries = [(f"{self.command_icons.get(cid, '•')}  {label}", self.settings.get(f"key_{cid}", ""), self.key_fns[cid])
                   for cid, label, _d in KEY_COMMANDS] + list(self.commands)
        for i, v in enumerate(self.views()):
            t = getattr(v, "base_title", "") or "New Tab"
            entries.append((f"🗂  Tab: {t}", v.url().toString()[:80], lambda idx=i: self.tabs.setCurrentIndex(idx)))
        for b in self.bookmarks:
            entries.append((f"⭐  {b['title']}", b["url"], lambda u=b["url"]: self.open_in_current(u)))
        for r in self.read_later:
            entries.append((f"🔖  {r['title']}", r["url"], lambda u=r["url"]: self.open_read_later(u)))
        for name in self.workspaces:
            entries.append((f"🗂  Workspace: {name}", "open", lambda n=name: self.open_workspace(n)))
        if self.hub is not None and self.settings.get("hub_games", True):
            for g in HUB.GAMES:
                entries.append((f"{g['emoji']}  Play {g['name']}", "free game", lambda gid=g["id"]: self.open_game(gid)))
            if self.settings.get("xp_on", True):
                for name, (need, desc, _s) in HUB.REWARD_PACKS.items():
                    if self.hub.reward_unlocked(name):
                        entries.append((f"🏆  Reward style pack: {name}", desc, lambda n=name: self.apply_pack(n)))
        for app in self.side_apps:
            entries.append((f"📌  Sidebar: {app[2]} {app[1]}", app[3], lambda a=app[0]: self.open_side_app(a)))
        for sid, emoji, title, _intro, _items in HELP_SECTIONS:
            entries.append((f"❓  Help: {title}", "how it works", lambda x=sid: self.open_help(x)))
        if EX is not None:
            entries.append(("🎤  Voice control setup", "speech model, add-ons", self.open_voice_setup))
            entries.append(("🎤  What can I say? (voice commands)", "", self.show_voice_help))
        seen = set()
        for h in reversed(self.history):
            if h["url"] in seen:
                continue
            seen.add(h["url"])
            entries.append((f"🕘  {h['title']}", h["url"], lambda u=h["url"]: self.open_in_current(u)))
            if len(seen) >= 150:
                break
        return entries

    # ---------- ❓ help + tour ----------
    def show_tour(self):
        if getattr(self, "tour", None) is not None and self.tour.isVisible():
            self.tour.raise_()
            return
        self.tour = TourDialog(self)
        self.tour.show()

    def build_help_page(self):
        a, light, _ = theme_colors()
        sections = []
        for sid, emoji, title, intro, items in HELP_SECTIONS:
            if sid == "nova" and not self.settings.get("nova_on", True):
                items = [i for i in items if i[0] == "Turn her off"]
            sections.append({"id": sid, "emoji": emoji, "title": title, "intro": intro,
                             "items": [{"name": n, "how": h, "key": k, "act": act} for n, h, k, act in items]})
        keys = [(label, self.settings.get("key_" + cid) or "") for cid, label, _d in KEY_COMMANDS]
        gestures = []
        if EX is not None:
            for code, arrows in EX.GESTURES:
                label = self.gesture_label(code)
                if label != "Nothing":
                    gestures.append((arrows, label))
        data = {"colors": {"a": a, "al": light, "bg": pal("page"), "card": pal("card"), "field": pal("field"),
                           "line": pal("border"), "text": pal("text"), "dim": pal("dim")},
                "sections": sections, "keys": keys, "gestures": gestures}
        HELP_FILE.write_text(HELP_HTML.replace("/*HELP*/{}", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"), 1),
                             encoding="utf-8")

    def open_help(self, section=""):
        try:
            self.build_help_page()
        except Exception as e:
            self.status(f"Couldn't build the help page: {e}")
            return
        url = QUrl.fromLocalFile(str(HELP_FILE))
        if section:
            url.setFragment(section)
        for i, v in enumerate(self.views()):
            if is_help_page(v.url()):
                self.tabs.setCurrentIndex(i)
                v.setUrl(url)
                return
        cur = self.current()
        if cur is not None and is_start_page(cur.url()) and not cur.private:
            cur.setUrl(url)
        else:
            self.new_tab(url, private=False)

    def open_customize_cat(self, name):
        self.open_customize()
        try:
            items = self.customize.cats.findItems(name, Qt.MatchFlag.MatchExactly)
            if items:
                self.customize.cats.setCurrentItem(items[0])
        except Exception:
            pass

    def fill_help_menu(self):
        m = self.help_menu
        m.clear()
        m.addAction("❓  Help & features guide        F1").triggered.connect(lambda: self.open_help())
        m.addAction("👋  Take the welcome tour").triggered.connect(self.show_tour)
        m.addSeparator()
        m.addAction("⌨  Keyboard shortcuts").triggered.connect(lambda: self.open_help("keys"))
        m.addAction("🖱  Mouse gestures").triggered.connect(lambda: self.open_help("gestures"))
        if EX is not None and self.settings.get("voice_on", True):
            m.addAction("🎤  What can I say? (voice)").triggered.connect(
                lambda: self.show_voice_help() if self.voice_ready() else self.open_voice_setup())
        m.addAction("⌘  Command palette              Ctrl+K").triggered.connect(self.open_palette)
        m.addSeparator()
        for sid, emoji, title, _intro, _items in HELP_SECTIONS:
            if sid == "nova" and not self.settings.get("nova_on", True):
                continue
            m.addAction(f"{emoji}  {title}").triggered.connect(lambda _=False, x=sid: self.open_help(x))

    def show_shortcuts(self):
        lines = [f"{label:<28} {self.settings.get('key_' + cid) or '—'}" for cid, label, _d in KEY_COMMANDS]
        box = QMessageBox(self)
        box.setWindowTitle("Keyboard shortcuts")
        box.setText("Change any of these in 🎨 Customize → Keyboard shortcuts.")
        box.setDetailedText("\n".join(lines))
        box.setInformativeText("\n".join(lines[:22]) + ("\n…" if len(lines) > 22 else ""))
        box.exec()

    def clear_data(self):
        ans = QMessageBox.question(
            self, "Clear browsing data",
            "Clear your history, closed tabs, cache and cookies?\n(You'll be signed out of websites.)")
        if ans != QMessageBox.StandardButton.Yes:
            return
        self.clear_history()
        self.closed.clear()
        self.profile.clearHttpCache()
        self.profile.cookieStore().deleteAllCookies()
        self.status("🧹 Browsing data cleared.")

    # ---------- bookmarks ----------
    def is_bookmarked(self, url: str) -> bool:
        return any(b["url"] == url for b in self.bookmarks)

    def update_star(self):
        view = self.current()
        url = view.url().toString() if view else ""
        self.star_act.setText("★" if self.is_bookmarked(url) else "☆")

    def toggle_bookmark(self):
        view = self.current()
        url = view.url().toString()
        if not is_web(url):
            return
        if self.is_bookmarked(url):
            self.bookmarks = [b for b in self.bookmarks if b["url"] != url]
        else:
            self.bookmarks.append({"title": getattr(view, "base_title", "") or url, "url": url})
        self.save_bookmarks()

    def remove_bookmark(self, url: str):
        self.bookmarks = [b for b in self.bookmarks if b["url"] != url]
        self.save_bookmarks()

    def save_bookmarks(self):
        save_json(BOOKMARKS_FILE, self.bookmarks)
        self.update_star()
        self.rebuild_start()

    def fill_bookmarks_menu(self):
        menu = self.bookmarks_menu
        menu.clear()
        add = menu.addAction("☆  Bookmark this page        Ctrl+D")
        add.triggered.connect(self.toggle_bookmark)
        menu.addSeparator()
        if not self.bookmarks:
            menu.addAction("No bookmarks yet").setEnabled(False)
            return
        for b in self.bookmarks:
            act = menu.addAction(b["title"][:50])
            act.setToolTip(b["url"])
            act.triggered.connect(lambda _=False, u=b["url"]: self.open_in_current(u))
        menu.addSeparator()
        remove = menu.addMenu("Remove a bookmark")
        for b in self.bookmarks:
            act = remove.addAction(b["title"][:50])
            act.triggered.connect(lambda _=False, u=b["url"]: self.remove_bookmark(u))

    # ---------- Nova ----------
    def setup_nova(self):
        self.nova_panel = NovaPanel(self)
        self.nova_dock = QDockWidget(self)
        self.nova_dock.setWidget(self.nova_panel)
        self.nova_dock.setTitleBarWidget(QWidget())   # no ugly title bar
        self.nova_dock.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea if self.settings["nova_side"] == "Left"
                           else Qt.DockWidgetArea.RightDockWidgetArea, self.nova_dock)
        self.nova_dock.hide()

    def show_nova(self):
        if not self.nova_dock.isVisible():
            self.nova_dock.show()
            self.resizeDocks([self.nova_dock], [int(self.settings["nova_width"])], Qt.Orientation.Horizontal)
        self.nova_panel.ping()
        if self.nova_panel.locked:
            self.nova_panel.code_input.setFocus()
        else:
            self.nova_panel.input.setFocus()

    def toggle_nova(self):
        if self.nova_dock.isVisible():
            self.nova_dock.hide()
        else:
            self.show_nova()

    def ask_nova(self, text):
        self.show_nova()
        self.nova_panel.send(text)

    def closeEvent(self, event):
        if self.settings["confirm_close"] and self.tabs.count() > 1:
            ans = QMessageBox.question(self, "Close Nova Browser", f"Close all {self.tabs.count()} tabs?")
            if ans != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        if self.settings["clear_history_exit"]:
            self.clear_history()
        if self.settings["clear_cookies_exit"]:
            self.profile.cookieStore().deleteAllCookies()
        if self.settings["clear_cache_exit"]:
            self.profile.clearHttpCache()
        if self.hub is not None:
            self.hub.save()
        if self.tray is not None:
            self.tray.hide()
        if self.voice is not None:
            self.voice.stop()
        for lst in (self.listener, self.wake_listener):
            if lst is not None:
                lst.stop()
                lst.wait(1500)
        if self.speaker is not None:
            self.speaker.stop()
        if self.zap_save_timer.isActive():
            self.save_zaps()
        for panel in list(self.side_panels.values()):        # sidebar pages go before their profile does
            panel.view.setParent(None)
            panel.view.deleteLater()
        self.side_panels = {}
        for fw in list(self.floats):
            fw.close()                       # floating tabs come back first, so they're saved too
        self.save_screen_time()
        self.save_session()
        if self.nova_panel is not None:
            self.nova_panel.shutdown_if_ours()
        # Close the pages before their profiles go away (avoids a crash on exit)
        while self.tabs.count():
            w = self.tabs.widget(0)
            self.tabs.removeTab(0)
            w.setParent(None)
            w.deleteLater()
        if self.split is not None:
            self.split.view.setParent(None)
            self.split.view.deleteLater()
        super().closeEvent(event)

    # ---------- 🎤 the browser's own voice control ----------
    def voice_ready(self):
        return EX is not None and not EX.voice_addons_missing() and bool(self.voice_model_path())

    def voice_model_name(self):
        return EX.VOSK_MODELS.get(self.settings.get("voice_model"), EX.VOSK_MODELS["Small (40 MB, fastest)"])[0]

    def voice_model_path(self):
        return EX.find_model(VOICE_DIR, self.voice_model_name()) if EX else ""

    def voice_grammar(self, wake=""):
        if not self.settings.get("voice_command_mode", True):
            return None
        try:
            return EX.voice_grammar([(b.get("title", ""), b.get("url", "")) for b in self.bookmarks],
                                    [a[1] for a in self.side_apps], wake)
        except Exception:
            return None

    def open_voice_setup(self):
        if EX is None:
            self.status("Voice control needs nova_extras.py next to the browser.")
            return
        if self.voice_setup is None or not self.voice_setup.isVisible():
            self.voice_setup = VoiceSetup(self)
        self.voice_setup.show()
        self.voice_setup.raise_()

    def apply_voice(self):
        """Starts/stops the always-listening wake word mode to match your settings."""
        s = self.settings
        want = (EX is not None and s.get("voice_on", True) and s.get("voice_mode") == VOICE_MODES[1]
                and (not self.game_mode or s.get("voice_while_gaming", False)) and self.voice_ready())
        if want and self.wake_listener is None:
            wake = s.get("voice_wake") or "hey browser"
            self.wake_listener = EX.VoiceListener(self.voice_model_path(), once=False, parent=self,
                                                  grammar=self.voice_grammar(wake), wake=wake)
            self.wake_listener.final.connect(self.on_wake_heard)
            self.wake_listener.partial.connect(self.on_wake_partial)
            self.wake_listener.level.connect(self.voice_bubble.set_level)
            self.wake_listener.failed.connect(lambda m: (self.voice_bubble.show_msg("⚠", m, ms=6000), self.stop_wake()))
            self.wake_listener.start()
            if "mic" in self.tb:
                self.tb["mic"].setText("🎤•")
                self.tb["mic"].setToolTip(f"Listening for “{s.get('voice_wake') or 'hey browser'}” (click to talk now)")
        elif not want and self.wake_listener is not None:
            self.stop_wake()
        elif want and self.wake_listener is not None:
            key = (self.voice_model_path(), s.get("voice_command_mode", True), s.get("voice_wake"))
            if getattr(self, "_wake_key", None) not in (None, key):
                self.stop_wake()
                QTimer.singleShot(100, self.apply_voice)
            self._wake_key = key
            return
        if self.wake_listener is not None:
            self._wake_key = (self.voice_model_path(), s.get("voice_command_mode", True), s.get("voice_wake"))

    def stop_wake(self):
        if self.wake_listener is not None:
            self.wake_listener.stop()
            self.wake_listener.wait(1500)
            self.wake_listener = None
        if "mic" in self.tb:
            self.tb["mic"].setText("🎤")
            self.tb["mic"].setToolTip("Talk to the browser (Ctrl+Shift+Space)")

    def start_listening(self):
        """🎤 / Ctrl+Shift+Space: listen for one command."""
        if EX is None or not self.settings.get("voice_on", True):
            self.status("🎤 Voice control is off (🎨 Customize → Voice control).")
            return
        if not self.voice_ready():
            self.open_voice_setup()
            return
        if self.speaker is not None:
            self.speaker.stop()
        if self.wake_listener is not None:                 # the mic is already open: just listen now
            self.voice_armed_until = time.time() + 7
            self.voice_bubble.show_msg("🎤", "Listening…", listening=True)
            return
        if self.listener is not None:                      # pressed again: stop
            self.listener.stop()
            return
        self.listener = EX.VoiceListener(self.voice_model_path(), once=True, parent=self, grammar=self.voice_grammar())
        self.listener.partial.connect(lambda t: self.voice_bubble.show_msg("🎤", f"“{t}”", listening=True))
        self.listener.final.connect(self.on_voice_heard)
        self.listener.level.connect(self.voice_bubble.set_level)
        self.listener.failed.connect(lambda m: self.voice_bubble.show_msg("⚠", m, ms=6000))
        self.listener.finished.connect(self.on_listener_done)
        self.voice_bubble.show_msg("🎤", "Listening…  (say “what can I say” for ideas)", listening=True)
        if "mic" in self.tb:
            self.tb["mic"].setText("🔴")
        self.listener.start()

    def on_listener_done(self):
        lst, self.listener = self.listener, None
        if lst is not None:
            lst.deleteLater()
        if "mic" in self.tb and self.wake_listener is None:
            self.tb["mic"].setText("🎤")
        if self.voice_bubble.isVisible() and self.voice_bubble.meter.isVisible():
            self.voice_bubble.hide()

    def on_wake_partial(self, text):
        if time.time() < self.voice_armed_until:
            self.voice_bubble.show_msg("🎤", f"“{text}”", listening=True)
            return
        yes, rest = EX.heard_wake(text, self.settings.get("voice_wake") or "hey browser")
        if yes:
            if self.speaker is not None:
                self.speaker.stop()
            self.voice_bubble.show_msg("🎤", f"“{rest}”" if rest else "Listening…", listening=True)

    def on_wake_heard(self, text):
        if time.time() < self.voice_armed_until:
            self.voice_armed_until = 0
            self.on_voice_heard(text)
            return
        yes, rest = EX.heard_wake(text, self.settings.get("voice_wake") or "hey browser")
        if not yes:
            return
        if rest:
            self.on_voice_heard(rest)
        else:
            self.voice_armed_until = time.time() + 7       # said only the wake word: listen for the command
            self.voice_bubble.show_msg("🎤", "Yes? I'm listening…", listening=True)

    def voice_context(self):
        hub = None
        if self.hub is not None:
            try:
                hub = self.hub.voice_summary()
            except Exception:
                hub = None
        return {"hub": hub, "bookmarks": [(b.get("title", ""), b.get("url", "")) for b in self.bookmarks],
                "nova": bool(self.settings.get("nova_on", True) and self.nova_panel is not None
                             and self.nova_panel.online and not self.nova_panel.locked)}

    def on_voice_heard(self, text):
        text = (text or "").strip()
        if not text:
            self.voice_bubble.show_msg("🎤", "I didn't hear anything.", ms=2500)
            return
        res = EX.parse_voice(text, self.voice_context())
        if res is None:
            if self.settings.get("voice_unknown_search", False):
                res = {"actions": [{"type": "search", "query": text}], "say": "", "show": f"🔎 {text}"}
            else:
                self.voice_bubble.show_msg("🤔", f"“{text}”: not sure what to do. Say “what can I say” for ideas.", ms=5000)
                return
        self.voice_bubble.show_msg("✓", f"“{text}”  →  {res['show']}", ms=4500 if not res.get("say") else 9000)
        if self.hub is not None:
            self.hub.xp_event("voice")
        for a in res["actions"]:
            kind = a.get("type")
            if kind == "voice_stop":
                if self.speaker is not None:
                    self.speaker.stop()
            elif kind == "voice_help":
                self.show_voice_help()
            elif kind == "read_aloud":
                self.read_aloud()
            else:
                if kind in ("open_url", "search") and not is_web(self.current().url().toString()) \
                        and not is_start_page(self.current().url()) and not a.get("new_tab"):
                    a = dict(a, new_tab=True)                # don't replace a hub or game page
                if kind == "search":
                    if a.get("new_tab"):
                        self.new_tab(to_url(a.get("query", "")))
                        continue
                self.run_nova_action(a)
        if res.get("say") and self.settings.get("voice_speak", True) and self.speaker is not None:
            self.speaker.say(res["say"], int(self.settings.get("voice_rate", 0)) / 10)

    def read_aloud(self):
        if self.speaker is None:
            return
        v = self.current()
        if not is_web(v.url().toString()):
            self.status("🔊 Open a web page first.")
            return
        js = ("(function(){var a=document.querySelector('article')||document.querySelector('main')||document.body;"
              "return (document.title+'. '+a.innerText).replace(/\\s+/g,' ').slice(0,6000);})()")
        v.page().runJavaScript(js, lambda t: (self.speaker.say(t or "", int(self.settings.get("voice_rate", 0)) / 10),
                                             self.status("🔊 Reading… say “stop reading” or press 🎤 to stop.", 6000)))

    def show_voice_help(self):
        d = QDialog(self)
        d.setWindowTitle("🎤 What you can say")
        d.setMinimumWidth(620)
        lay = QVBoxLayout(d)
        wake = self.settings.get("voice_wake") or "hey browser"
        how = (f"Say <b>“{html.escape(wake)}”</b> and then your command" if self.settings.get("voice_mode") == VOICE_MODES[1]
               else "Press <b>🎤</b> or <b>Ctrl+Shift+Space</b>, then talk")
        rows = "".join(f"<tr><td style='padding:5px 12px 5px 0;color:{pal('dim')};white-space:nowrap'><b>{html.escape(k)}</b></td>"
                       f"<td style='padding:5px 0'>{html.escape(v)}</td></tr>" for k, v in EX.VOICE_HELP)
        lab = QLabel(f"<p>{how}. Everything is understood on this PC, offline.</p><table>{rows}</table>"
                     "<p style='color:#9a9ca6'>“stop” stops talking/reading. Nova isn't needed for any of these "
                     "except page summaries.</p>")
        lab.setWordWrap(True)
        lab.setTextFormat(Qt.TextFormat.RichText)
        lay.addWidget(lab)
        ok = QPushButton("Got it")
        ok.clicked.connect(d.close)
        lay.addWidget(ok, 0, Qt.AlignmentFlag.AlignRight)
        d.show()

    def on_voice_action(self, a):
        """Something you told Nova out loud (Jarvis section 13ZD sends it here)."""
        kind = str(a.get("type", ""))
        if self.hub is not None:
            self.hub.xp_event("voice")
        if self.settings.get("nova_voice_raise", True) and not self.game_mode and kind in (
                "open_url", "search", "hub", "ask_page", "play_game", "sidebar", "new_tab"):
            self.bring_to_front()
        say = str(a.get("say") or "")[:120]
        if say:
            self.status(f"🎙 {say}", 4000)
        self.run_nova_action(a)

    def run_nova_action(self, action):
        """Things Nova can ask the browser to do."""
        kind = action.get("type")
        view = self.current()
        if kind == "command":
            cid = str(action.get("id", ""))
            if cid in self.key_fns and cid not in ("print", "private_tab", "paste_go"):
                self.key_fns[cid]()
            return
        if kind == "media":
            op = str(action.get("op", ""))
            js = {"pause": "m.pause()", "play": "m.play()", "toggle": "(m.paused?m.play():m.pause())",
                  "forward": "m.currentTime+=Math.max(1,Math.min(600,%d))" % int(action.get("seconds") or 10),
                  "back": "m.currentTime-=Math.max(1,Math.min(600,%d))" % int(action.get("seconds") or 10),
                  "restart": "m.currentTime=0"}.get(op)
            if op in ("mute", "unmute"):
                view.page().setAudioMuted(op == "mute")
                self.refresh_tab_label(view)
            elif js:
                view.page().runJavaScript(
                    "(function(){var l=[].slice.call(document.querySelectorAll('video,audio'));"
                    "var m=l.filter(function(x){return !x.paused;})[0]||l.sort(function(a,b){return (b.duration||0)-(a.duration||0);})[0];"
                    "if(m){try{" + js + "}catch(e){}}})();")
            return
        if kind == "scroll":
            d = str(action.get("dir", "down"))
            js = {"down": "window.scrollBy({top:innerHeight*.8,behavior:'smooth'})", "up": "window.scrollBy({top:-innerHeight*.8,behavior:'smooth'})",
                  "top": "window.scrollTo({top:0,behavior:'smooth'})",
                  "bottom": "window.scrollTo({top:document.documentElement.scrollHeight,behavior:'smooth'})"}.get(d)
            if js:
                view.page().runJavaScript(js)
            return
        if kind == "tab":
            n = action.get("n")
            if n == "last":
                self.tabs.setCurrentIndex(self.tabs.count() - 1)
            elif isinstance(n, int) and 1 <= n <= self.tabs.count():
                self.tabs.setCurrentIndex(n - 1)
            return
        if kind == "hub":
            k = "games" if action.get("hub") == "games" else "follow"
            self.open_hub(k, action.get("tab"))
            return
        if kind == "play_game":
            if HUB is not None and str(action.get("id", "")) in HUB.GAME_IDS:
                self.open_game(str(action["id"]))
            return
        if kind == "sidebar":
            want = str(action.get("app", "")).lower().strip()
            if want in ("", "close", "hide"):
                self.hide_sidebar()
                return
            for app in self.side_apps + ([(a[0], a[1], a[2], a[3]) for a in EX.SIDEBAR_APPS] if EX else []):
                if want in (app[0], app[1].lower()) or want.replace(" ", "") == app[1].lower().replace(" ", ""):
                    self.open_side_app(app[0], app)
                    return
            self.status(f"🎙 No sidebar app called “{want}”.")
            return
        if kind == "game_mode":
            on = action.get("on")
            if on is True and not self.game_mode:
                self.enter_game_mode(None, manual=True)
            elif on is False and self.game_mode:
                self.exit_game_mode()
            elif on is None:
                self.toggle_game_mode()
            return
        if kind == "ask_page":
            q = str(action.get("q", "")).strip()[:300]
            if q:
                self.ask_nova(q)
            return
        if kind == "open_url":
            url = QUrl(action.get("url", ""))
            if url.scheme() in ("http", "https"):
                if action.get("new_tab"):
                    self.new_tab(url)
                else:
                    self.current().setUrl(url)
        elif kind == "search":
            self.current().setUrl(to_url(action.get("query", "")))
        elif kind == "back":
            self.current().back()
        elif kind == "forward":
            self.current().forward()
        elif kind == "reload":
            self.current().reload()
        elif kind == "new_tab":
            self.new_tab()
        elif kind == "close_tab":
            self.close_tab(self.tabs.currentIndex())
        elif kind == "bookmark":
            if not self.is_bookmarked(self.current().url().toString()):
                self.toggle_bookmark()

    # ---------- history ----------
    def record_history(self, view, ok):
        url = view.url().toString()
        if (not ok or view.private or not is_web(url) or view.title().startswith(("📖", "🎯"))
                or not self.settings["history_enabled"]):
            return
        if self.history and self.history[-1]["url"] == url:
            return
        self.history.append({
            "title": view.title() or url,
            "url": url,
            "time": time.strftime("%Y-%m-%d %H:%M"),
        })
        self.history = self.history[-int(self.settings['max_history']):]
        save_json(HISTORY_FILE, self.history)
        if self.hub is not None:
            self.hub.xp_event("page")

    def fill_history_menu(self):
        menu = self.history_menu
        menu.clear()
        if not self.history:
            menu.addAction("No history yet").setEnabled(False)
            return
        for h in reversed(self.history[-25:]):
            act = menu.addAction(f'{h["time"][11:]}   {h["title"][:50]}')
            act.setToolTip(h["url"])
            act.triggered.connect(lambda _=False, u=h["url"]: self.open_in_current(u))
        menu.addSeparator()
        menu.addAction("Clear history").triggered.connect(self.clear_history)

    def clear_history(self):
        self.history = []
        save_json(HISTORY_FILE, self.history)


if __name__ == "__main__":
    hide_own_console()
    app = QApplication(sys.argv)
    app.setApplicationName("Nova Browser")
    if sys.platform == "win32":
        try:   # its own taskbar icon/group instead of Python's
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Nova.Browser")
        except Exception:
            pass
    if ICON_FILE.exists():
        from PyQt6.QtGui import QIcon
        app.setWindowIcon(QIcon(str(ICON_FILE)))
    _settings = load_settings()
    set_theme_from(_settings)
    CURRENT_SEARCH["url"] = search_template(_settings)
    app.setStyleSheet(themed(DARK_STYLE) + chrome_extra_style(_settings))
    # Let Nova know where this browser lives, so "open nova browser" works
    _raw = load_json(SETTINGS_FILE, {})
    _raw = _raw if isinstance(_raw, dict) else {}
    _raw["browser_path"] = str(APP_PATH)
    save_json(SETTINGS_FILE, _raw)
    window = Browser()
    window.show()
    sys.exit(app.exec())
