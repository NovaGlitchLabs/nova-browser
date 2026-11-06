"""
nova_extras.py - extra powers for Nova Browser (keep it next to nova_browser.pyw, like nova_hub.py).

  * memory readings for the 🧠 tab manager (how much RAM each tab and the whole browser uses)
  * Game Mode helpers: is one of your games running right now?
  * mouse gestures (hold right-click and draw)
  * the element zapper (click annoying things to hide them on that site for good)
  * sidebar apps (Discord, YouTube Music, Spotify, WhatsApp ... pinned beside your tabs)
  * the voice link: lets Nova (Jarvis.py) drive the browser when you talk to her

Everything here only reads information on this PC; nothing is sent anywhere except to Nova on 127.0.0.1.
"""
import os
import re
import sys
import json

from PyQt6.QtCore import QObject, pyqtSignal, QTimer, QUrl, QByteArray
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkProxy


# ============================================================================== memory + processes
def fmt_bytes(n):
    if n is None:
        return "–"
    n = float(n)
    if n >= 1024 ** 3:
        return f"{n / 1024 ** 3:.2f} GB"
    if n >= 1024 ** 2:
        return f"{n / 1024 ** 2:.0f} MB"
    return f"{n / 1024:.0f} KB"


if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    _k32 = ctypes.WinDLL("kernel32", use_last_error=True)

    class _PE32(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("th32ProcessID", wintypes.DWORD),
                    ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                    ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", ctypes.c_long), ("dwFlags", wintypes.DWORD),
                    ("szExeFile", ctypes.c_wchar * 260)]

    class _PMC(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t), ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t), ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t), ("PrivateUsage", ctypes.c_size_t)]

    _k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    _k32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    _k32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PE32)]
    _k32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PE32)]
    _k32.OpenProcess.restype = wintypes.HANDLE
    _k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    _k32.CloseHandle.argtypes = [wintypes.HANDLE]
    _k32.K32GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PMC), wintypes.DWORD]
    _k32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    _INVALID = wintypes.HANDLE(-1).value
    _QUERY = 0x1000 | 0x0010            # PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_VM_READ

    def process_list():
        """[(pid, parent pid, exe name)] for every running process."""
        out = []
        snap = _k32.CreateToolhelp32Snapshot(0x2, 0)
        if not snap or snap == _INVALID:
            return out
        try:
            e = _PE32()
            e.dwSize = ctypes.sizeof(_PE32)
            ok = _k32.Process32FirstW(snap, ctypes.byref(e))
            while ok:
                out.append((int(e.th32ProcessID), int(e.th32ParentProcessID), e.szExeFile))
                ok = _k32.Process32NextW(snap, ctypes.byref(e))
        finally:
            _k32.CloseHandle(snap)
        return out

    def proc_memory(pid):
        """Private memory of a process in bytes (what Task Manager calls its memory), or None."""
        h = _k32.OpenProcess(_QUERY, False, int(pid))
        if not h:
            h = _k32.OpenProcess(0x1000, False, int(pid))
            if not h:
                return None
        try:
            c = _PMC()
            c.cb = ctypes.sizeof(_PMC)
            if _k32.K32GetProcessMemoryInfo(h, ctypes.byref(c), c.cb):
                return int(c.PrivateUsage or c.WorkingSetSize)
            return None
        finally:
            _k32.CloseHandle(h)

    def proc_path(pid):
        h = _k32.OpenProcess(0x1000, False, int(pid))
        if not h:
            return ""
        try:
            buf = ctypes.create_unicode_buffer(1024)
            size = wintypes.DWORD(1024)
            if _k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
                return buf.value
            return ""
        finally:
            _k32.CloseHandle(h)

    def steam_running_appid():
        """The Steam game running right now (Steam writes it in the registry), or 0."""
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as k:
                return int(winreg.QueryValueEx(k, "RunningAppID")[0] or 0)
        except (OSError, ValueError, ImportError):
            return 0
else:
    def process_list():
        out = []
        for d in os.listdir("/proc") if os.path.isdir("/proc") else []:
            if not d.isdigit():
                continue
            try:
                with open(f"/proc/{d}/stat") as f:
                    parts = f.read().rsplit(")", 1)
                name = parts[0].split("(", 1)[1]
                ppid = int(parts[1].split()[1])
                out.append((int(d), ppid, name))
            except (OSError, IndexError, ValueError):
                pass
        return out

    def proc_memory(pid):
        try:
            with open(f"/proc/{int(pid)}/status") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        return int(line.split()[1]) * 1024
        except (OSError, ValueError):
            pass
        return None

    def proc_path(pid):
        try:
            return os.readlink(f"/proc/{int(pid)}/exe")
        except OSError:
            return ""

    def steam_running_appid():
        return 0


def process_tree(root_pid, procs=None):
    """root_pid and every process started under it (QtWebEngine runs pages in child processes)."""
    procs = procs if procs is not None else process_list()
    kids = {}
    for pid, ppid, _n in procs:
        kids.setdefault(ppid, []).append(pid)
    out, todo = [], [int(root_pid)]
    while todo:
        p = todo.pop()
        if p in out:
            continue
        out.append(p)
        todo.extend(k for k in kids.get(p, []) if k != p)
    return out


def browser_memory(root_pid=None):
    """(total bytes, {pid: bytes}) for the browser and all its helper processes."""
    root_pid = root_pid or os.getpid()
    per = {}
    for pid in process_tree(root_pid):
        m = proc_memory(pid)
        if m is not None:
            per[pid] = m
    return sum(per.values()), per


# ============================================================================== Game Mode: is a game running?
GAME_MODE_IGNORE = re.compile(r"wallpaper engine|soundpad|lossless scaling|steamvr|spacewar|tool|sdk|server", re.I)


def running_paths():
    """Lower-cased full paths of running programs (only paths, nothing else is read)."""
    out = set()
    for pid, _ppid, _n in process_list():
        p = proc_path(pid)
        if p:
            out.add(os.path.normcase(p))
    return out


def detect_running_game(games, running_appid=0, paths=None):
    """Which of your linked games is running? games = hub game dicts (appid / dir / name)."""
    games = [g for g in games or [] if not GAME_MODE_IGNORE.search(str(g.get("name", "")))]
    if running_appid:
        for g in games:
            if str(g.get("appid", "")) == str(running_appid):
                return g
    for g in games:
        d = str(g.get("dir") or "").strip()
        if not d or len(d) < 6:
            continue
        nd = os.path.normcase(os.path.abspath(d)).rstrip("\\/") + os.sep
        for p in paths or ():
            if p.startswith(nd):
                return g
    return None


# ============================================================================== mouse gestures
GESTURES = [("L", "←"), ("R", "→"), ("U", "↑"), ("D", "↓"), ("DR", "↓→"), ("DL", "↓←"), ("UD", "↑↓"), ("DU", "↓↑"),
            ("UL", "↑←"), ("UR", "↑→"), ("LR", "←→"), ("RL", "→←")]
GESTURE_DEFAULTS = {"L": "back", "R": "forward", "U": "scroll_top", "D": "scroll_bottom", "DR": "close_tab",
                    "DL": "reopen", "UD": "reload", "DU": "new_tab", "UL": "prev_tab", "UR": "next_tab", "LR": "", "RL": ""}


def recognize_gesture(points, step=30):
    """Turns a mouse path [(x, y), …] into moves like 'L', 'DR'. Diagonal wobble is ignored."""
    moves = []
    if len(points) < 2:
        return ""
    ax, ay = points[0]
    for x, y in points[1:]:
        dx, dy = x - ax, y - ay
        if max(abs(dx), abs(dy)) < step:
            continue
        if abs(dx) > 1.5 * abs(dy):
            d = "R" if dx > 0 else "L"
        elif abs(dy) > 1.5 * abs(dx):
            d = "D" if dy > 0 else "U"
        else:
            ax, ay = x, y
            continue
        if not moves or moves[-1] != d:
            moves.append(d)
        ax, ay = x, y
    return "".join(moves) if len(moves) <= 2 else ""


def gesture_arrows(code):
    return dict(GESTURES).get(code, code)


# ============================================================================== element zapper
def valid_selector(sel):
    sel = str(sel or "")
    return 0 < len(sel) <= 400 and not re.search(r"[{};<@\\\n\r]|/\*|\*/", sel)


def zap_host(host):
    host = str(host or "").lower().strip(".")
    return host[4:] if host.startswith("www.") else host


def clean_zaps(zaps):
    out = {}
    for h, sels in (zaps.items() if isinstance(zaps, dict) else []):
        h = zap_host(h)
        if not re.fullmatch(r"[a-z0-9.-]{1,253}", h):
            continue
        good = [s for s in (sels if isinstance(sels, list) else []) if valid_selector(s)]
        if good:
            out[h] = list(dict.fromkeys(good))[-200:]
    return out


def zap_css_script(zaps):
    """Page script that hides every zapped thing on its site (each rule separate, so one bad rule can't break the rest)."""
    data = json.dumps(clean_zaps(zaps))
    return ("(function(){var Z=%s,h=location.hostname.replace(/^www\\./,''),s=Z[h];if(!s||!s.length)return;"
            "function add(){if(document.getElementById('nova-zaps'))return;var st=document.createElement('style');st.id='nova-zaps';"
            "st.textContent=s.map(function(x){return x+'{display:none!important}';}).join('\\n');"
            "(document.head||document.documentElement).appendChild(st);}"
            "if(document.documentElement)add();else document.addEventListener('readystatechange',add,{once:true});})();") % data


ZAPPER_JS = r"""(function () {
if (location.protocol === "file:") return;
if (window.__novaZap) window.__novaZap.stop();
var box = document.createElement("div"), tip = document.createElement("div"), bar = document.createElement("div"), done = [], cur = null;
box.style.cssText = "position:fixed;z-index:2147483646;pointer-events:none;border:2px solid #ff4d5e;background:rgba(255,77,94,.16);border-radius:4px;display:none";
tip.style.cssText = "position:fixed;z-index:2147483647;pointer-events:none;background:#ff4d5e;color:#fff;font:12px 'Segoe UI',sans-serif;padding:2px 7px;border-radius:4px;display:none";
bar.style.cssText = "position:fixed;z-index:2147483647;top:12px;left:50%;transform:translateX(-50%);background:#1d1f25;color:#fff;font:13px 'Segoe UI',sans-serif;" +
  "padding:9px 16px;border-radius:12px;border:1px solid #ff4d5e;box-shadow:0 10px 30px rgba(0,0,0,.45);pointer-events:none";
bar.textContent = "🎯 Zapper: click anything to hide it on this site for good  ·  Ctrl+Z undo  ·  Esc when done";
document.documentElement.appendChild(box); document.documentElement.appendChild(tip); document.documentElement.appendChild(bar);
function okId(id) { return /^[A-Za-z][\w-]{0,60}$/.test(id) && !/\d{4,}/.test(id); }
function okCls(c) { return /^[A-Za-z][\w-]{1,40}$/.test(c) && !/\d{3,}/.test(c) && !/^(hover|active|focus|open|show|visible|selected|is-|js-)/.test(c); }
function selector(el) {
  var parts = [];
  while (el && el.nodeType === 1 && el !== document.documentElement && el !== document.body && parts.length < 7) {
    if (el.id && okId(el.id)) { parts.unshift("#" + CSS.escape(el.id)); break; }
    var p = el.tagName.toLowerCase(), cl = [].slice.call(el.classList).filter(okCls).slice(0, 2);
    if (cl.length) p += "." + cl.map(CSS.escape).join(".");
    var par = el.parentElement;
    if (par && !cl.length) { var same = [].filter.call(par.children, function (c) { return c.tagName === el.tagName; });
      if (same.length > 1) p += ":nth-of-type(" + (same.indexOf(el) + 1) + ")"; }
    parts.unshift(p); el = par;
  }
  return parts.join(" > ");
}
function under(e) { var el = document.elementFromPoint(e.clientX, e.clientY);
  return (!el || el === box || el === tip || el === bar || el === document.body || el === document.documentElement) ? null : el; }
function move(e) {
  var el = under(e); cur = el;
  if (!el) { box.style.display = tip.style.display = "none"; return; }
  var r = el.getBoundingClientRect();
  box.style.display = tip.style.display = "block";
  box.style.left = r.left + "px"; box.style.top = r.top + "px"; box.style.width = r.width + "px"; box.style.height = r.height + "px";
  tip.textContent = el.tagName.toLowerCase() + " · " + Math.round(r.width) + "×" + Math.round(r.height);
  tip.style.left = Math.max(4, r.left) + "px"; tip.style.top = Math.max(4, r.top - 24) + "px";
}
function zap(e) {
  e.preventDefault(); e.stopPropagation();
  var el = cur || under(e); if (!el) return;
  var s = selector(el), list;
  try { list = document.querySelectorAll(s); } catch (x) { return; }
  if (!s || !list.length || list.length > 40 || [].indexOf.call(list, el) < 0) return;
  var hid = [];
  [].forEach.call(list, function (n) { hid.push([n, n.style.getPropertyValue("display"), n.style.getPropertyPriority("display")]); n.style.setProperty("display", "none", "important"); });
  done.push({ sel: s, hid: hid });
  console.log("__novazap__" + JSON.stringify({ sel: s }));
  box.style.display = tip.style.display = "none"; cur = null;
}
function undo() {
  var last = done.pop(); if (!last) return;
  last.hid.forEach(function (h) { if (h[1]) h[0].style.setProperty("display", h[1], h[2]); else h[0].style.removeProperty("display"); });
  var st = document.getElementById("nova-zaps");
  if (st) st.textContent = st.textContent.split("\n").filter(function (l) { return l !== last.sel + "{display:none!important}"; }).join("\n");
  console.log("__novaunzap__" + JSON.stringify({ sel: last.sel }));
}
function key(e) {
  if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); stop(); }
  else if ((e.ctrlKey || e.metaKey) && (e.key === "z" || e.key === "Z")) { e.preventDefault(); e.stopPropagation(); undo(); }
}
function block(e) { e.preventDefault(); e.stopPropagation(); }
var BLOCK = ["mousedown", "mouseup", "pointerdown", "pointerup", "auxclick", "dblclick"];
function stop() {
  removeEventListener("mousemove", move, true); removeEventListener("click", zap, true); removeEventListener("keydown", key, true);
  BLOCK.forEach(function (t) { removeEventListener(t, block, true); });
  box.remove(); tip.remove(); bar.remove(); window.__novaZap = null;
  console.log("__novazapdone__");
}
addEventListener("mousemove", move, true); addEventListener("click", zap, true); addEventListener("keydown", key, true);
BLOCK.forEach(function (t) { addEventListener(t, block, true); });
window.__novaZap = { stop: stop };
})();"""


# ============================================================================== sidebar apps
SIDEBAR_APPS = [
    ("discord", "Discord", "💬", "https://discord.com/app", True),
    ("ytmusic", "YouTube Music", "🎧", "https://music.youtube.com", True),
    ("spotify", "Spotify", "🟢", "https://open.spotify.com", True),
    ("whatsapp", "WhatsApp", "📱", "https://web.whatsapp.com", True),
    ("crunchyroll", "Crunchyroll", "🍥", "https://www.crunchyroll.com", False),
    ("youtube", "YouTube", "▶️", "https://www.youtube.com", False),
    ("twitch", "Twitch", "🟣", "https://www.twitch.tv", False),
    ("reddit", "Reddit", "👽", "https://www.reddit.com", False),
    ("x", "X / Twitter", "𝕏", "https://x.com", False),
    ("gmail", "Gmail", "✉️", "https://mail.google.com", False),
    ("calendar", "Google Calendar", "📅", "https://calendar.google.com", False),
    ("chatgpt", "ChatGPT", "🤖", "https://chatgpt.com", False),
]


def parse_custom_apps(text):
    """'Notion | notion.so; Netflix | https://netflix.com' → [(id, name, icon, url)] (web addresses only)."""
    out = []
    for i, part in enumerate(re.split(r"[;\n]", str(text or ""))):
        name, _, url = part.partition("|")
        name, url = name.strip()[:30], url.strip()
        if not name or not url:
            continue
        if not re.match(r"^https?://", url, re.I):
            url = "https://" + url
        if not re.match(r"^https?://[\w.-]+\.[a-z]{2,}(?::\d+)?(/\S*)?$", url, re.I):
            continue
        out.append((f"custom{i}", name, name[0].upper(), url))
    return out[:12]


# ============================================================================== voice link (Nova → browser)
class VoiceLink(QObject):
    """Waits for things Nova was told by voice ("pause the video", "open crunchyroll") and hands them to the browser.
    Talks only to Nova on 127.0.0.1 with her secret code from nova_bridge.json."""
    action = pyqtSignal(dict)
    status = pyqtSignal(str)          # "connected" / "waiting" / "old-nova"

    def __init__(self, link_file, enabled, parent=None):
        super().__init__(parent)
        self.link_file = link_file
        self.enabled = enabled                    # callable -> bool
        self.nam = QNetworkAccessManager(self)
        self.nam.setProxy(QNetworkProxy(QNetworkProxy.ProxyType.NoProxy))
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.poll)
        self.reply = None
        self.state = ""

    def start(self, delay=1500):
        self.timer.start(delay)

    def stop(self):
        self.timer.stop()
        if self.reply is not None:
            try:
                self.reply.abort()
            except RuntimeError:
                pass
            self.reply = None

    def _set(self, st):
        if st != self.state:
            self.state = st
            self.status.emit(st)

    def _req(self, path, timeout):
        try:
            info = json.loads(open(self.link_file, encoding="utf-8").read())
        except (OSError, ValueError):
            return None
        if not isinstance(info, dict) or not info.get("token"):
            return None
        req = QNetworkRequest(QUrl(f"http://127.0.0.1:{int(info.get('port', 8766))}{path}"))
        req.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, "application/json")
        req.setRawHeader(b"X-Nova-Token", str(info["token"]).encode("utf-8"))
        try:
            req.setTransferTimeout(timeout)
        except AttributeError:
            pass
        return req

    def poll(self):
        if self.reply is not None:
            return
        if not self.enabled():
            self._set("off")
            self.timer.start(4000)
            return
        req = self._req("/events?wait=25", 40000)
        if req is None:
            self._set("waiting")
            self.timer.start(5000)
            return
        self.reply = self.nam.get(req)
        self.reply.finished.connect(lambda r=self.reply: self._done(r))

    def _done(self, reply):
        self.reply = None
        code = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
        try:
            data = json.loads(bytes(reply.readAll()).decode("utf-8"))
        except ValueError:
            data = {}
        reply.deleteLater()
        if code == 200 and isinstance(data, dict):
            self._set("connected")
            for ev in data.get("events") or []:
                if isinstance(ev, dict) and isinstance(ev.get("type"), str):
                    self.action.emit(ev)
            self.timer.start(30)
        elif code == 404:
            self._set("old-nova")                 # Nova is running without the voice section
            self.timer.start(60000)
        else:
            self._set("waiting")
            self.timer.start(3000)

    def push(self, path, payload):
        """Fire-and-forget POST to Nova (e.g. the scores/anime summary she reads out)."""
        req = self._req(path, 8000)
        if req is None:
            return
        r = self.nam.post(req, QByteArray(json.dumps(payload).encode("utf-8")))
        r.finished.connect(r.deleteLater)


# ============================================================================== 🎤 the browser's own voice control (offline, no Nova needed)
# Speech recognition: Vosk (free, runs on this PC, nothing is sent anywhere) + sounddevice (the microphone).
# Spoken answers: Qt's text-to-speech, or Windows' built-in voices.
import threading
import zipfile
import difflib
import time
import subprocess

from PyQt6.QtCore import QThread

VOSK_MODEL_NAME = "vosk-model-small-en-us-0.15"
VOSK_MODEL_URL = "https://alphacephei.com/vosk/models/" + VOSK_MODEL_NAME + ".zip"
VOSK_MODEL_MB = 40
# Both understand "command mode" (a fixed list of phrases), which is what keeps words from getting mixed up.
VOSK_MODELS = {"Small (40 MB, fastest)": ("vosk-model-small-en-us-0.15", 40),
               "Better (128 MB, more accurate)": ("vosk-model-en-us-0.22-lgraph", 128)}


def model_url(name):
    return "https://alphacephei.com/vosk/models/" + name + ".zip"

SITES = {
    "youtube": "https://www.youtube.com", "google": "https://www.google.com", "duckduckgo": "https://duckduckgo.com",
    "github": "https://github.com", "wikipedia": "https://en.wikipedia.org", "reddit": "https://www.reddit.com",
    "crunchyroll": "https://www.crunchyroll.com", "crunchy roll": "https://www.crunchyroll.com", "netflix": "https://www.netflix.com",
    "twitch": "https://www.twitch.tv", "gmail": "https://mail.google.com", "google maps": "https://maps.google.com",
    "maps": "https://maps.google.com", "amazon": "https://www.amazon.com", "chatgpt": "https://chatgpt.com",
    "chat gpt": "https://chatgpt.com", "claude": "https://claude.ai", "x": "https://x.com", "twitter": "https://x.com",
    "instagram": "https://www.instagram.com", "tiktok": "https://www.tiktok.com", "tik tok": "https://www.tiktok.com",
    "pinterest": "https://www.pinterest.com", "stack overflow": "https://stackoverflow.com", "spotify": "https://open.spotify.com",
    "youtube music": "https://music.youtube.com", "myanimelist": "https://myanimelist.net", "my anime list": "https://myanimelist.net",
    "google drive": "https://drive.google.com", "google docs": "https://docs.google.com", "outlook": "https://outlook.live.com",
    "discord": "https://discord.com/app", "steam": "https://store.steampowered.com", "epic games": "https://store.epicgames.com",
    "espn": "https://www.espn.com", "facebook": "https://www.facebook.com", "whatsapp": "https://web.whatsapp.com",
    "hulu": "https://www.hulu.com", "disney plus": "https://www.disneyplus.com", "prime video": "https://www.primevideo.com",
    "roblox": "https://www.roblox.com", "khan academy": "https://www.khanacademy.org", "weather": "https://weather.com",
}
VOICE_NUM = {"one": 1, "two": 2, "to": 2, "too": 2, "three": 3, "four": 4, "for": 4, "five": 5, "six": 6, "seven": 7,
             "eight": 8, "nine": 9, "ten": 10, "fifteen": 15, "twenty": 20, "thirty": 30, "forty": 40, "forty five": 45,
             "fifty": 50, "sixty": 60, "ninety": 90, "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
             "a": 1, "an": 1}
MEDIA = r"(?:the |this |that |my )?(?:video|youtube|episode|stream|show|movie|anime|clip|music|song|audio)"
VOICE_GAMES = {"tetris": "blocks", "starfall blocks": "blocks", "blocks": "blocks", "two thousand forty eight": "fusion",
               "twenty forty eight": "fusion", "2048": "fusion", "fusion": "fusion", "brick breaker": "bricks", "breakout": "bricks",
               "bricks": "bricks", "flappy bird": "flight", "nova flight": "flight", "minesweeper": "mines", "mine sweeper": "mines",
               "mine sweep": "mines", "memory": "memory", "memory cards": "memory", "pong": "paddle", "paddle": "paddle",
               "paddle duel": "paddle", "asteroids": "rocks", "space rocks": "rocks", "connect four": "four",
               "four in a row": "four", "neon dash": "dash", "dash": "dash", "tic tac toe": "ttt", "snake": "snake"}
VOICE_HELP = [
    ("Websites", "“open YouTube” · “go to github dot com” · “search for one piece” · “open my bookmark …”"),
    ("Pages & tabs", "“go back” · “refresh” · “new tab” · “close tab” · “next tab” · “switch to tab 3” · “reopen the closed tab”"),
    ("Scrolling & zoom", "“scroll down / up” · “scroll to the top / bottom” · “zoom in / out” · “full screen”"),
    ("Videos", "“pause the video” · “play the video” · “skip ahead 30 seconds” · “rewind 10 seconds” · “mute this tab”"),
    ("Reading", "“read this page” · “stop reading” · “reader mode” · “summarize this page” (needs Nova)"),
    ("Hubs & games", "“open my games” · “show my anime” · “show my deals” · “play tetris” · “turn on game mode”"),
    ("Questions", "“what's the Lakers score” · “when's the next episode of Frieren” · “any game deals” · “what level am I”"),
    ("Extras", "“open Discord in the sidebar” · “zap this page” · “open the tab manager” · “take a screenshot”"),
]


def voice_num(s):
    s = str(s or "").strip()
    return int(s) if s.isdigit() else VOICE_NUM.get(s)


# How speech recognition tends to write names it doesn't know (or mishears) -> what you meant.
SPOKEN = {
    "youtube": ["you tube", "u tube", "you tub", "youtubes"],
    "youtube music": ["you tube music", "u tube music"],
    "crunchyroll": ["crunchy roll", "crunch roll", "crunchy role", "crunchy rolls", "crunchie roll", "crunchy row",
                    "crunch e roll", "crunchy royal", "crunchyroll"],
    "github": ["git hub", "get hub", "good hub", "kit hub"],
    "netflix": ["net flix", "net flicks", "netflicks"],
    "tiktok": ["tick tock", "tik tok", "tic tac", "tick tok", "tic toc"],
    "chatgpt": ["chat g p t", "chat gpt", "chad gpt", "chat g pt", "chat gbt"],
    "spotify": ["spot if i", "spot a fly", "spotty fi", "spot fi", "spot if y"],
    "wikipedia": ["wiki pedia", "wicked pedia"],
    "instagram": ["insta gram", "instant gram", "insta graham"],
    "discord": ["dis cord", "this cord"],
    "reddit": ["red it", "read it dot com", "red dit"],
    "duckduckgo": ["duck duck go", "duck go"],
    "myanimelist": ["my anime list"],
    "whatsapp": ["whats app", "what's app", "what sap", "watts app"],
    "gmail": ["g mail", "gee mail", "g male"],
    "espn": ["e s p n", "e. s. p. n."],
    "roblox": ["row blocks", "rob locks", "roe blocks", "rob lox", "row box"],
    "pinterest": ["pin trust", "pinter est", "pin interest"],
    "hulu": ["who lou", "who lu"],
        "tetris": ["tetras", "tetra's"],
    "minesweeper": ["mine sweeper", "mind sweeper"],
    "2048": ["twenty forty eight", "two thousand forty eight", "two zero four eight", "twenty forty-eight"],
    "tic tac toe": ["tick tack toe", "tic tac tow", "tick tac toe"],
    "full screen": ["fool screen", "full scream"],
}
_SPOKEN_FIXES = sorted(((re.compile(r"\b" + re.escape(v) + r"\b(?! toe)"), k) for k, vs in SPOKEN.items() for v in vs if v != k),
                       key=lambda kv: -len(kv[0].pattern))
LEAD_FIXES = [  # only at the start of what you said
    (r"^(?:oh|o|uh|ah|a|i) (?:been|ben|pen|pin|bin|bean|penn|pan|open|opened)\b", "open"),
    (r"^(?:hoping|hope in|opening|opened|opens|open up|upon|o\.? pen)\b", "open"),
    (r"^(?:gotta|goto|go two|go too|got to)\b", "go to"),
    (r"^(?:school|scrawl|scroll|squirrel|schulz?) (up|down|to)\b", r"scroll \1"),
    (r"^(?:paws|pods)\b(?= |$)", "pause"),
    (r"^(?:search four|surge for|search far|church for)\b", "search for"),
    (r"^(?:next to|necks tab|next tap|next stab)$", "next tab"),
    (r"^(?:new tap|knew tab|new top|you tab)$", "new tab"),
    (r"^(?:close tap|close stab|clothes tab|close top)$", "close tab"),
    (r"^(?:re fresh|we fresh|refreshed)$", "refresh"),
    (r"^(?:mutes?|mute it|muted)$", "mute"),
    (r"^(?:play the video|played the video|plate the video)$", "play the video"),
]
_LEAD_FIXES = [(re.compile(a), b) for a, b in LEAD_FIXES]


def voice_fix(t):
    """Fixes words speech recognition commonly gets wrong ("you tube" -> youtube, "oh been" -> open)."""
    for rx, to in _LEAD_FIXES:
        t = rx.sub(to, t, count=1)
    for rx, to in _SPOKEN_FIXES:
        t = rx.sub(to, t)
    return re.sub(r"\s+", " ", t).strip()


def voice_clean(text, wake=""):
    t = str(text or "").lower()
    t = re.sub(r"[^\w\s'.:/-]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    if wake:
        w = wake.lower().strip()
        if t.startswith(w):
            t = t[len(w):].strip(" ,")
    t = voice_fix(t)                                 # before "uh"/"um" go, so "uh been …" still becomes "open …"
    t = re.sub(r"^(?:please |can you |could you |would you |hey |ok |okay |um |uh )+", "", t)
    t = re.sub(r"\s+(?:please|for me|thanks|thank you|real quick|now)$", "", t)
    return voice_fix(t.strip())


def heard_wake(text, wake):
    """Did this start with the wake word? Returns (yes, rest of the sentence). Forgiving about mishearing."""
    def light(x):
        return re.sub(r"\s+", " ", re.sub(r"[^\w\s']", " ", str(x or "").lower())).strip()
    t = light(text)
    w = light(wake or "hey browser")
    if not w:
        return False, voice_clean(t)
    tw, ww = t.split(), w.split()
    for extra in (0, 1):
        n = len(ww) + extra
        if len(tw) >= len(ww) and difflib.SequenceMatcher(None, " ".join(tw[:n]), w).ratio() >= 0.78:
            return True, voice_clean(" ".join(tw[n:]))
    return False, voice_clean(t)


def _key(s):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", str(s or "").lower())).strip()


def voice_hub_answer(t, hub):
    """Answers from your Following/Games hubs (teams, anime, deals, XP). None = not that kind of question."""
    if not hub:
        return None
    teams, anime, deals = hub.get("teams") or [], hub.get("anime") or [], hub.get("deals") or []
    if teams and re.search(r"\b(?:score|scores|playing|play next|game|games|win|won|lose|lost|record|doing|beat|match)\b", t):
        hit = [x for x in teams if any(k and re.search(r"\b" + re.escape(k) + r"\b", t)
                                      for k in (_key(x.get("short")), _key(x.get("name"))))]
        if hit:
            return " ".join(x["line"] for x in hit[:2])
        if re.search(r"\bmy teams?\b|\bany scores\b|\bsports scores\b|\bhow are my\b", t):
            return " ".join(x["line"] for x in teams[:3])
    if anime and re.search(r"\b(?:episode|episodes|anime|ep)\b", t):
        hit = []
        for x in anime:
            for title in (x.get("name"), x.get("romaji")):
                k = _key(re.split(r"[:\-–(]", str(title or ""))[0])
                if k and len(k) >= 4 and k in t:
                    hit.append(x)
                    break
        if hit:
            return " ".join(f"{x['name']}: {x['line']}" for x in hit[:2])
        if re.search(r"\b(?:any|new|my)\b", t):
            out = [f"{x['name']}: {x['line']}" for x in anime if "is out" in x.get("line", "")]
            return " ".join(out[:3]) or "No new episodes right now. You're caught up."
    if re.search(r"\b(?:deal|deals|on sale|sale|price|cheap|wishlist)\b", t):
        hit = [x for x in deals if _key(x.get("name")) and _key(x.get("name")) in t]
        if hit:
            return " ".join(x["line"] for x in hit[:2])
        if deals and re.search(r"\b(?:any|my|game)\b", t):
            return " ".join(x["line"] for x in deals[:3])
        if re.search(r"\bany (?:game )?deals\b", t):
            return "Nothing on your wishlist yet. Add games in Games, Deals."
    if re.search(r"\bwhat level am i\b|\bmy (?:level|xp)\b|\bhow much xp\b", t):
        return f"You're level {hub.get('level', 1)} with {hub.get('xp', 0)} XP."
    return None


SIMPLE_CMDS = {"go back": "back", "back": "back", "previous page": "back", "go forward": "forward", "forward": "forward",
               "next page": "forward", "refresh": "reload", "reload": "reload", "refresh the page": "reload",
               "reload the page": "reload", "refresh this page": "reload", "new tab": "new_tab", "open a new tab": "new_tab",
               "open new tab": "new_tab", "close tab": "close_tab", "close this tab": "close_tab", "close the tab": "close_tab",
               "bookmark this": "bookmark", "bookmark this page": "bookmark", "bookmark it": "bookmark", "save this page": "bookmark"}
PAGE_CMDS = {"next tab": "next_tab", "go to the next tab": "next_tab", "previous tab": "prev_tab",
             "go to the previous tab": "prev_tab", "zoom in": "zoom_in", "zoom out": "zoom_out", "reset zoom": "zoom_reset",
             "reset the zoom": "zoom_reset", "full screen": "fullscreen", "fullscreen": "fullscreen", "exit full screen": "fullscreen",
             "make it full screen": "fullscreen", "reader mode": "reader", "take a screenshot": "screenshot",
             "screenshot": "screenshot", "screenshot this page": "screenshot", "save for later": "later",
             "save this for later": "later", "go home": "home", "home page": "home", "find on page": "find",
             "show history": "history", "open history": "history", "show downloads": "downloads", "open downloads": "downloads",
             "new private tab": "private_tab", "open a private tab": "private_tab", "split view": "split",
             "dark mode": "dark", "toggle dark mode": "dark", "open customize": "customize", "open settings": "customize",
             "surprise me": "surprise", "float this tab": "float", "open the command palette": "palette",
             "open nova": "nova", "close nova": "nova"}
_GRAMMAR_FIXED = [
    "stop", "stop talking", "stop reading", "be quiet", "never mind", "cancel", "help", "what can i say", "what can you do",
    "pause", "pause the video", "pause the episode", "pause the music", "play", "resume", "play the video", "resume the video",
    "play the episode", "unpause", "mute", "unmute", "mute this tab", "unmute this tab", "restart the video",
    "speed up the video", "slow down the video", "normal speed", "scroll down", "scroll up", "scroll down a bit",
    "scroll up a bit", "scroll to the top", "scroll to the bottom", "go to the top", "go to the bottom", "page down", "page up",
    "last tab", "go to the last tab", "reopen the closed tab", "reopen the last tab", "read this page", "read this page to me",
    "read it to me", "summarize this page", "key points", "what is this video about", "what is this page about",
    "open my games", "show my games", "open the games hub", "open following", "show my teams", "open my anime", "show my anime",
    "show my deals", "open my deals", "show my wishlist", "show my badges", "show my level", "show my profile",
    "turn on game mode", "turn off game mode", "start game mode", "stop game mode", "game mode on", "game mode off",
    "open the sidebar", "close the sidebar", "hide the sidebar", "zap this page", "zap this", "open the tab manager",
    "what level am i", "any game deals",
]
_GRAMMAR_NUMS = ["one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "fifteen", "twenty",
                 "thirty", "forty five", "sixty", "ninety"]
_GRAMMAR_OPEN = ["open", "go to", "pull up", "take me to"]


def voice_grammar(bookmarks=(), apps=(), wake=""):
    """Every command phrase the browser knows, for "command mode" recognition (it can only hear these, so it can't mix
    words up). Free speech like "search for …" still uses the normal recognizer."""
    out = set(_GRAMMAR_FIXED) | set(SIMPLE_CMDS) | set(PAGE_CMDS)
    names = set(SITES)
    for k, vs in SPOKEN.items():
        if k in SITES:
            names |= set(vs)
    for title, _url in bookmarks or ():
        k = _key(title)
        if 2 < len(k) <= 40:
            names.add(k)
            names.add("my " + k)
    for v in _GRAMMAR_OPEN:
        for n in names:
            out.add(f"{v} {n}")
            if v == "open":
                out.add(f"open {n} in a new tab")
    for n in _GRAMMAR_NUMS:
        for unit in (("seconds", "minutes") if n not in ("one",) else ("second", "minute")):
            out |= {f"skip ahead {n} {unit}", f"rewind {n} {unit}", f"go back {n} {unit}", f"skip {n} {unit}"}
    for n in _GRAMMAR_NUMS[:10]:
        out |= {f"switch to tab {n}", f"go to tab {n}"}
    games = set(VOICE_GAMES) | {v for k, vs in SPOKEN.items() if k in VOICE_GAMES for v in vs}
    for g in games:
        if not re.search(r"\d", g):
            out |= {f"play {g}", f"play the {g} game", f"let's play {g}"}
    for a in apps or ():
        k = _key(a)
        if k:
            out |= {f"open {k} in the sidebar", f"show {k} in the sidebar"}
    for app_id, name, _i, _u, _on in SIDEBAR_APPS:
        out.add(f"open {_key(name)} in the sidebar")
    phrases = sorted(p for p in out if p and not re.search(r"\d", p))
    w = _key(wake)
    if w:
        phrases += [f"{w} {p}" for p in phrases] + [w]
    return phrases + ["[unk]"]


def choose_heard(free, cmd, conf, wake=""):
    """Picks between what the normal recognizer heard (free) and what command mode heard (cmd, with its confidence)."""
    f, c = voice_clean(free), voice_clean(cmd)
    if not c or "[unk]" in str(cmd):
        return free
    body = heard_wake(cmd, wake)[1] if wake else c
    fbody = heard_wake(free, wake)[1] if wake else f
    if re.match(r"^(?:search|google|look up|find me|look for|ask nova|nova)\b", fbody):
        return free                                  # searching needs every word you said
    if parse_voice(body) is None:
        return free                                  # command mode only counts when it heard a real command
    if conf >= 0.72 or (conf >= 0.6 and parse_voice(fbody) is None):
        return cmd
    return free


def parse_voice(text, ctx=None):
    """What you said → {"actions": [...browser actions...], "say": spoken answer, "show": text for the bubble}.
    None when it isn't a command. ctx: hub (voice summary), bookmarks [(title, url)], sidebar [names], nova (bool)."""
    ctx = ctx or {}
    t = voice_clean(text)
    if not t:
        return None

    def act(show, *actions, say=""):
        return {"actions": list(actions), "say": say, "show": show}

    # ---- the voice itself
    if t in ("stop", "stop talking", "stop reading", "be quiet", "shut up", "quiet", "silence", "never mind", "nevermind", "cancel"):
        return act("Okay.", {"type": "voice_stop"})
    if re.fullmatch(r"(?:help|what can i say|what can you do|voice commands|show (?:me )?(?:the )?voice commands)", t):
        return act("Here's what you can say.", {"type": "voice_help"})

    # ---- video / audio
    if re.fullmatch(r"(?:pause|stop|freeze) " + MEDIA, t) or t in ("pause", "pause it", "pause that"):
        return act("⏸ Paused", {"type": "media", "op": "pause"})
    if re.fullmatch(r"(?:play|resume|unpause|continue|start) " + MEDIA + r"(?: again)?", t) or t in ("play", "resume", "play it", "unpause"):
        return act("▶ Playing", {"type": "media", "op": "play"})
    m = re.fullmatch(r"(?:skip|jump|go|fast forward|move)(?: it)?(?: ahead| forward)?(?: by)? (\w+(?: \w+)?) (second|seconds|minute|minutes)(?: ahead| forward)?", t)
    if m and voice_num(m.group(1)):
        n = voice_num(m.group(1)) * (60 if m.group(2).startswith("minute") else 1)
        return act(f"⏩ +{n}s", {"type": "media", "op": "forward", "seconds": n})
    m = re.fullmatch(r"(?:rewind|go back|back up|skip back|jump back)(?: by)? (\w+(?: \w+)?) (second|seconds|minute|minutes)", t)
    if m and voice_num(m.group(1)):
        n = voice_num(m.group(1)) * (60 if m.group(2).startswith("minute") else 1)
        return act(f"⏪ −{n}s", {"type": "media", "op": "back", "seconds": n})
    if re.fullmatch(r"(?:restart|replay) " + MEDIA + r"|start " + MEDIA + r" over", t):
        return act("⏮ From the start", {"type": "media", "op": "restart"})
    if re.fullmatch(r"mute(?: (?:this|the|that) (?:tab|page|video|site))?", t):
        return act("🔇 Muted", {"type": "media", "op": "mute"})
    if re.fullmatch(r"unmute(?: (?:this|the|that) (?:tab|page|video|site))?", t):
        return act("🔊 Unmuted", {"type": "media", "op": "unmute"})
    if re.fullmatch(r"(?:speed up|faster) " + MEDIA + r"|speed " + MEDIA + r" up|play " + MEDIA + r" faster|speed it up", t):
        return act("⏩ Faster", {"type": "command", "id": "faster"})
    if re.fullmatch(r"slow down " + MEDIA + r"|slow " + MEDIA + r" down|play " + MEDIA + r" slower|slow it down", t):
        return act("⏪ Slower", {"type": "command", "id": "slower"})
    if re.fullmatch(r"(?:normal|regular) speed|play " + MEDIA + r" (?:at )?normal speed", t):
        return act("▶ Normal speed", {"type": "command", "id": "normal_speed"})

    # ---- reading pages
    if re.fullmatch(r"read (?:this|the|me the|this whole) (?:page|article|post|story)(?: to me| out loud| aloud)?|read (?:it|this) (?:to me|out loud|aloud)", t):
        return act("🔊 Reading the page…", {"type": "read_aloud"})
    if re.search(r"\b(?:summari[sz]e|tl ?dr|key points|main points)\b|what(?:'s| is) this (?:page|article|video|post) about", t):
        if ctx.get("nova"):
            return act("✦ Asking Nova…", {"type": "ask_page", "q": text.strip()[:300]})
        return act("Summaries need Nova. Here's reader mode instead.", {"type": "command", "id": "reader"},
                   say="Summaries need Nova, so I opened reader mode instead.")
    m = re.fullmatch(r"(?:ask nova|nova|hey nova)[, ]+(.+)", t)
    if m:
        if ctx.get("nova"):
            return act("✦ Asking Nova…", {"type": "ask_page", "q": m.group(1)})
        return act("Nova isn't running.", say="Nova isn't running right now.")

    # ---- scrolling, tabs, zoom, page commands
    m = re.fullmatch(r"(?:scroll|page|go) (down|up)(?: a bit| some| more| a little)?", t)
    if m:
        return act("↕", {"type": "scroll", "dir": m.group(1)})
    m = re.fullmatch(r"(?:scroll|go|jump) (?:to )?the (top|bottom)(?: of (?:the|this) page)?|(?:scroll|go) to (top|bottom)", t)
    if m:
        return act("↕", {"type": "scroll", "dir": m.group(1) or m.group(2)})
    simple = SIMPLE_CMDS
    if t in simple:
        return act("✓ " + t.capitalize(), {"type": simple[t]})
    commands = PAGE_CMDS
    if t in commands:
        return act("✓ " + t.capitalize(), {"type": "command", "id": commands[t]})
    m = re.fullmatch(r"(?:switch to|go to|open|show) (?:the )?tab (?:number )?(\w+)|(?:switch to|go to) the (\w+) tab", t)
    if m:
        word = m.group(1) or m.group(2)
        if word == "last":
            return act("Last tab", {"type": "tab", "n": "last"})
        n = voice_num(word)
        if n:
            return act(f"Tab {n}", {"type": "tab", "n": n})
    if t in ("go to the last tab", "switch to the last tab", "last tab"):
        return act("Last tab", {"type": "tab", "n": "last"})
    if re.fullmatch(r"(?:reopen|bring back|undo close)(?: the)?(?: last| closed| last closed)? tab", t):
        return act("↺ Reopened", {"type": "command", "id": "reopen"})

    # ---- hubs, built-in games, game mode, sidebar, zapper, tab manager
    if re.fullmatch(r"(?:open|show|pull up|go to)(?: me)? (?:my |the )?(?:games|game hub|games hub|gaming hub|games page)", t):
        return act("🎮 Games", {"type": "hub", "hub": "games"})
    if re.fullmatch(r"(?:open|show|pull up)(?: me)? (?:my |the )?(?:following|follows|following hub|sports hub|feed|teams|sports)(?: page)?", t):
        return act("📣 Following", {"type": "hub", "hub": "follow"})
    if re.fullmatch(r"(?:open|show|pull up)(?: me)? (?:my |the )?(?:anime|anime list|anime tracker|shows i'm watching)", t):
        return act("📺 Anime", {"type": "hub", "hub": "follow", "tab": "anime"})
    if re.fullmatch(r"(?:open|show|pull up)(?: me)? (?:my |the )?(?:game )?(?:deals|wishlist|game wishlist)", t):
        return act("💸 Deals", {"type": "hub", "hub": "games", "tab": "deals"})
    if re.fullmatch(r"(?:open|show|pull up)(?: me)? (?:my |the )?(?:badges|xp|level|profile|achievements)", t):
        return act("🏆 Profile", {"type": "hub", "hub": "games", "tab": "profile"})
    m = re.fullmatch(r"(?:let's |let me |i want to )?play (?:a game of |some |the )?(.+?)(?: game)?", t)
    if m and m.group(1).strip() in VOICE_GAMES:
        return act("🕹 Game on!", {"type": "play_game", "id": VOICE_GAMES[m.group(1).strip()]})
    if re.fullmatch(r"(?:turn on|start|enable|activate) game mode|game mode on", t):
        return act("🕹 Game Mode on", {"type": "game_mode", "on": True})
    if re.fullmatch(r"(?:turn off|stop|end|disable|exit) game mode|game mode off", t):
        return act("🕹 Game Mode off", {"type": "game_mode", "on": False})
    m = re.fullmatch(r"(?:open|show|put|pull up) (.+?) (?:in|on) (?:the |my )?side ?bar", t)
    if m:
        return act("📌 " + m.group(1), {"type": "sidebar", "app": m.group(1).strip()})
    if re.fullmatch(r"(?:open|show) (?:the |my )?side ?bar", t):
        return act("📌 Sidebar", {"type": "command", "id": "sidebar"})
    if re.fullmatch(r"(?:close|hide) (?:the |my )?side ?bar", t):
        return act("📌 Sidebar hidden", {"type": "sidebar", "app": "close"})
    if re.fullmatch(r"zap (?:this page|this site|something|stuff|ads|this|things)|start the zapper|open the zapper", t):
        return act("🎯 Click what you want gone", {"type": "command", "id": "zap"})
    if re.fullmatch(r"(?:open|show) (?:the )?tab manager|how much (?:memory|ram) (?:is (?:the|my) browser using|am i using)", t):
        return act("🧠 Tab manager", {"type": "command", "id": "tab_manager"})

    # ---- questions about your hubs (after commands, so "show my anime" opens it instead of answering)
    ans = voice_hub_answer(t, ctx.get("hub"))
    if ans:
        return act(ans, say=ans)

    # ---- searching + opening websites
    m = re.fullmatch(r"(?:search for|search up|search|google|look up|find me|look for)\s+(.+)", t)
    if m:
        q = m.group(1).strip()
        return act(f"🔎 {q}", {"type": "search", "query": q}, say="")
    new_tab = bool(re.search(r"\bin (?:a )?new tab\b", t))
    t2 = re.sub(r"\s*\bin (?:a )?new tab\b", "", t).strip()
    m = re.fullmatch(r"(?:open|go to|goto|take me to|pull up|load|navigate to|bring up|visit|show me)\s+(.+)", t2)
    if m:
        target = re.sub(r"^(?:the|my)\s+", "", m.group(1).strip())
        target = re.sub(r"\s+(?:website|site|web site|page|homepage|home page)$", "", target).strip()
        target = re.sub(r"\s+dot\s+(com|net|org|io|tv|gg|ai|dev|co|edu|gov)\b", r".\1", target)
        if target in SITES:
            return act(f"🌐 {target.title()}", {"type": "open_url", "url": SITES[target], "new_tab": new_tab})
        if re.fullmatch(r"(?:https?://)?[a-z0-9-]+(?:\.[a-z0-9-]+)+(?:/\S*)?", target):
            url = target if target.startswith(("http://", "https://")) else "https://" + target
            return act(f"🌐 {target}", {"type": "open_url", "url": url, "new_tab": new_tab})
        target = re.sub(r"^bookmark\s+", "", target)
        best, score = None, 0.0
        for title, url in ctx.get("bookmarks") or []:
            r = difflib.SequenceMatcher(None, _key(title), target).ratio()
            if _key(title).startswith(target) and len(target) >= 3:
                r = max(r, 0.9)
            if r > score:
                best, score = (title, url), r
        if best and score >= 0.72:
            return act(f"⭐ {best[0][:40]}", {"type": "open_url", "url": best[1], "new_tab": new_tab})
        return act(f"🔎 {target}", {"type": "search", "query": target})
    return None


class VoiceListener(QThread):
    """Listens to the microphone and turns speech into text, on this PC only.
    once=True: one sentence (push to talk). once=False: keeps listening (wake word mode)."""
    partial = pyqtSignal(str)
    final = pyqtSignal(str)
    failed = pyqtSignal(str)
    level = pyqtSignal(float)

    _model = None
    _model_path = ""
    _lock = threading.Lock()

    def __init__(self, model_path, once=True, parent=None, grammar=None, wake=""):
        super().__init__(parent)
        self.model_path = str(model_path)
        self.once = once
        self.grammar = list(grammar or [])
        self.wake = wake
        self.stop_flag = False

    def stop(self):
        self.stop_flag = True

    @classmethod
    def load_model(cls, path):
        with cls._lock:
            if cls._model is None or cls._model_path != path:
                import vosk
                vosk.SetLogLevel(-1)
                cls._model = vosk.Model(path)
                cls._model_path = path
            return cls._model

    def run(self):
        try:
            import vosk
            import sounddevice as sd
        except Exception as e:
            self.failed.emit(f"Voice add-ons missing ({e.__class__.__name__}).")
            return
        try:
            model = self.load_model(self.model_path)
            dev = sd.query_devices(kind="input")
            rate = int(dev.get("default_samplerate") or 16000)
        except Exception as e:
            self.failed.emit(f"Couldn't start listening: {e}")
            return
        rec = vosk.KaldiRecognizer(model, rate)
        cmd = None
        if self.grammar:
            try:                                     # command mode: can only hear the browser's own phrases
                cmd = vosk.KaldiRecognizer(model, rate, json.dumps(self.grammar))
                cmd.SetWords(True)
            except Exception:
                cmd = None

        def decide(text):
            if cmd is None:
                return text
            try:
                r = json.loads(cmd.FinalResult())
                words = r.get("result") or []
                conf = sum(float(w.get("conf", 0)) for w in words) / len(words) if words else 0.0
                heard = str(r.get("text", "")).strip()
                try:
                    cmd.Reset()
                except Exception:
                    pass
                return choose_heard(text, heard, conf, self.wake) or text
            except Exception:
                return text
        started = time.time()
        heard_any = False
        try:
            with sd.RawInputStream(samplerate=rate, blocksize=int(rate / 5), dtype="int16", channels=1) as stream:
                while not self.stop_flag:
                    data, _over = stream.read(int(rate / 5))
                    data = bytes(data)
                    if len(data) >= 2:
                        import array
                        a = array.array("h", data[: len(data) // 2 * 2])
                        peak = max(abs(min(a)), abs(max(a))) if a else 0
                        self.level.emit(min(1.0, peak / 12000.0))
                    if cmd is not None:
                        cmd.AcceptWaveform(data)
                    if rec.AcceptWaveform(data):
                        text = json.loads(rec.Result()).get("text", "").strip()
                        if text:
                            self.final.emit(decide(text))
                            if self.once:
                                return
                        elif cmd is not None:
                            try:
                                cmd.Reset()
                            except Exception:
                                pass
                    else:
                        p = json.loads(rec.PartialResult()).get("partial", "").strip()
                        if p:
                            heard_any = True
                            self.partial.emit(p)
                    if self.once and (time.time() - started > (14 if heard_any else 7)):
                        text = json.loads(rec.FinalResult()).get("text", "").strip()
                        self.final.emit(decide(text) if text else "")
                        return
        except Exception as e:
            self.failed.emit(f"Microphone problem: {e}")


class Speaker(QObject):
    """Says things out loud: Qt's text-to-speech if it's there, otherwise Windows' own voices."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tts = None
        self.proc = None
        try:
            from PyQt6.QtTextToSpeech import QTextToSpeech
            self.tts = QTextToSpeech(self)
        except Exception:
            self.tts = None

    def available(self):
        return self.tts is not None or sys.platform == "win32"

    def say(self, text, rate=0.0):
        text = re.sub(r"[*_#`>|]", " ", str(text or "")).strip()[:6000]
        if not text:
            return
        self.stop()
        if self.tts is not None:
            try:
                self.tts.setRate(max(-1.0, min(1.0, rate)))
                self.tts.say(text)
                return
            except Exception:
                pass
        if sys.platform == "win32":
            try:
                ps = ("Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                      f"$s.Rate = {int(max(-10, min(10, rate * 10)))}; $s.Speak([Console]::In.ReadToEnd())")
                self.proc = subprocess.Popen(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                                             stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                self.proc.stdin.write(text.encode("utf-8", "replace"))
                self.proc.stdin.close()
            except Exception:
                self.proc = None

    def stop(self):
        if self.tts is not None:
            try:
                self.tts.stop()
            except Exception:
                pass
        if self.proc is not None and self.proc.poll() is None:
            try:
                self.proc.kill()
            except Exception:
                pass
        self.proc = None


def voice_addons_missing():
    """Which of the two free voice add-ons aren't installed (vosk, sounddevice)."""
    missing = []
    for mod in ("vosk", "sounddevice"):
        try:
            __import__(mod)
        except Exception:
            missing.append(mod)
    return missing


def find_model(voice_dir, prefer=""):
    """The speech model folder if it's downloaded. Uses `prefer` (a model folder name) when it's there, else any model."""
    d = os.path.join(str(voice_dir))
    if not os.path.isdir(d):
        return ""
    found = []
    for name in sorted(os.listdir(d)):
        p = os.path.join(d, name)
        if os.path.isdir(p) and (os.path.isfile(os.path.join(p, "am", "final.mdl")) or os.path.isfile(os.path.join(p, "conf", "model.conf"))):
            if prefer and name == prefer:
                return p
            found.append(p)
    big = [p for p in found if "small" not in os.path.basename(p)]
    return (big or found or [""])[0]


def unpack_model(zip_path, voice_dir):
    """Unzips a downloaded model safely (nothing can be written outside the voice folder)."""
    root = os.path.abspath(str(voice_dir))
    os.makedirs(root, exist_ok=True)
    with zipfile.ZipFile(zip_path) as z:
        for info in z.infolist():
            target = os.path.abspath(os.path.join(root, info.filename))
            if not target.startswith(root + os.sep):
                raise ValueError("bad file in the download")
        z.extractall(root)
    return find_model(root)
