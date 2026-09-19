"""Paths, logging, i18n, search engines, URL safety, RAM detection."""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

APP_NAME = "Frame"
DEFAULT_HOME = "https://www.google.com"
SCHEME = b"frame"

# ── Logging ──────────────────────────────────────────────────────────
log = logging.getLogger("frame")
if not log.handlers:
    _h = logging.StreamHandler(sys.stderr)
    _h.setFormatter(logging.Formatter("[Frame] %(levelname)s: %(message)s"))
    log.addHandler(_h)
    log.setLevel(logging.INFO)


# ── i18n ─────────────────────────────────────────────────────────────
_FALLBACK: dict[str, str] = {
    "app.name": "Frame",
    "tab.new": "New Tab",
    "private.title": "Frame — Incognito",
    "menu.settings": "Settings",
    "url.blocked": "Blocked URL: {url}",
    "nav.blocked": "Navigation blocked: {url}",
    "tab.limit.title": "Tab limit reached",
    "tab.limit.body": (
        "You already have {count} tabs (limit: {max}).\n\n"
        "Close some tabs, or change the limit in "
        "Settings → Performance & Resources."
    ),
    "low_end.title": "Low Power Mode Enabled",
    "low_end.body": (
        "Frame detected around <b>{ram:.1f} GB</b> of RAM.<br><br>"
        "<b>Low Power Mode</b> has been enabled automatically:<br>"
        "• Max tabs: 8<br>"
        "• Idle tabs sleep after 2 minutes<br>"
        "• WebGL & PDF viewer disabled<br>"
        "• Chromium renderer processes limited<br><br>"
        "You can change all of this in <b>Settings → "
        "Performance & Resources</b>."
    ),
}


class Translator:
    """Translator with fallback to the default language.

    No global mutable state — an instance can be recreated per test.
    """

    def __init__(self, fallback: dict[str, str]) -> None:
        self._strings: dict[str, str] = {}
        self._fallback: dict[str, str] = fallback

    def load(self, lang: str, locale_dir: Path) -> None:
        p = locale_dir / f"{lang}.json"
        if not p.exists():
            return
        try:
            self._strings = json.loads(p.read_text("utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            log.warning("Failed to load locale %s: %s", p, exc)

    def tr(self, key: str, **kw) -> str:
        s = self._strings.get(key) or self._fallback.get(key) or key
        return s.format(**kw) if kw else s


translator = Translator(_FALLBACK)


def i18n_load(lang: str, locale_dir: Path) -> None:
    translator.load(lang, locale_dir)


# Compatible with old callers: `from .core import tr`
tr = translator.tr


# ── Paths ────────────────────────────────────────────────────────────
def _compute_data_dir() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        p = Path(base) / APP_NAME / APP_NAME
    elif sys.platform == "darwin":
        p = Path.home() / "Library" / "Application Support" / APP_NAME / APP_NAME
    else:
        base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
        p = Path(base) / APP_NAME / APP_NAME
    try:
        p.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        log.warning("Cannot create data directory %s: %s", p, exc)
    return p


def data_dir() -> Path:
    return _compute_data_dir()


# ── RAM detection ────────────────────────────────────────────────────
def detect_total_ram_gb() -> float | None:
    try:
        import psutil
        return psutil.virtual_memory().total / (1024 ** 3)
    except ImportError:
        pass
    except (OSError, AttributeError) as exc:
        log.debug("psutil failed: %s", exc)

    try:
        if sys.platform == "win32":
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(stat)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
            return stat.ullTotalPhys / (1024 ** 3)

        if sys.platform == "darwin":
            out = subprocess.check_output(["sysctl", "-n", "hw.memsize"])
            return int(out.strip()) / (1024 ** 3)

        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    return int(line.split()[1]) / (1024 ** 2)
    except (OSError, subprocess.SubprocessError, ValueError, AttributeError) as exc:
        log.debug("RAM detection failed: %s", exc)
    return None


def _read_settings_raw() -> dict:
    """Read frame_data.json's `settings` block without instantiating Store."""
    path = _compute_data_dir() / "frame_data.json"
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text("utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("frame_data.json corrupt/unreadable: %s", exc)
        return {}
    return raw.get("settings", {}) or {}


def pre_init_should_use_low_end() -> bool:
    settings = _read_settings_raw()
    if "low_end_mode" in settings:
        return bool(settings["low_end_mode"])
    if not settings.get("first_run_done"):
        ram = detect_total_ram_gb()
        return ram is not None and ram < 4.0
    return False


def pre_init_aggressive_process() -> bool:
    """Read `aggressive_process_mode` from frame_data.json before
    QApplication is created (needed to build Chromium flags).

    Default: True — this mode has no visible feature loss, so we opt
    users in unless they've explicitly disabled it.
    """
    settings = _read_settings_raw()
    return bool(settings.get("aggressive_process_mode", True))


# ── Search engines ───────────────────────────────────────────────────
SEARCH_ENGINES = {
    "Google":     {"action": "https://www.google.com/search",   "param": "q"},
    "DuckDuckGo": {"action": "https://duckduckgo.com/",         "param": "q"},
    "Bing":       {"action": "https://www.bing.com/search",     "param": "q"},
    "Brave":      {"action": "https://search.brave.com/search", "param": "q"},
    "Ecosia":     {"action": "https://www.ecosia.org/search",   "param": "q"},
    "Yahoo":      {"action": "https://search.yahoo.com/search", "param": "p"},
}


# ── URL safety ───────────────────────────────────────────────────────
SAFE_SCHEMES = {"http", "https", "file", "frame", "about", "view-source"}


def is_safe_url(url: str) -> bool:
    """True if the URL scheme is on the allowlist.

    Prevents `javascript:`, `data:`, `vbscript:`, etc. from executing
    via the address bar, bookmarks, history, or page links.
    """
    if not url:
        return False
    try:
        scheme = urlparse(url).scheme.lower()
    except ValueError:
        return False
    return scheme in SAFE_SCHEMES


# ── Helpers ──────────────────────────────────────────────────────────
def human_size(n: int) -> str:
    n = float(n or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def human_speed(bps: float) -> str:
    if bps <= 0:
        return "—"
    return human_size(int(bps)) + "/s"


def fmt_time(ts: float) -> str:
    return time.strftime("%d %b %Y · %H:%M", time.localtime(ts))

# ── Chromium flags ───────────────────────────────────────────────────
NORMAL_FLAGS = " ".join([
    "--disable-gpu-shader-disk-cache",
])

LOW_END_FLAGS = " ".join([
    "--disable-gpu-shader-disk-cache",
    "--disable-background-networking",
    "--disable-component-update",
    "--disable-default-apps",
    "--disable-domain-reliability",
    "--disable-sync",
    "--disable-extensions",
    "--disable-client-side-phishing-detection",
    "--disable-breakpad",
    "--disable-dev-shm-usage",
    "--renderer-process-limit=2",
    "--process-per-site",
    "--disk-cache-size=52428800",
    "--media-cache-size=10485760",
    "--enable-low-end-device-mode",
])

# ══════════════════════════════════════════════════════════════════════
#  Chromium flags — tiered
# ══════════════════════════════════════════════════════════════════════
# Base flags — always on. Currently just GPU shader disk cache.
_BASE_FLAGS = [
    "--disable-gpu-shader-disk-cache",
]

# WebRTC leak protection — stop WebRTC from leaking local IPs.
_WEBRTC_FLAG = (
    "--force-webrtc-ip-handling-policy=default_public_interface_only"
)

# Safe process flags — reduce Chromium's per-tab process overhead.
# NO visible feature loss. Real trade-off: a crash in one renderer
# takes down all tabs sharing that process (weaker isolation).
# Default ON; users can disable via `aggressive_process_mode` in Settings.
_SAFE_PROCESS_FLAGS = [
    "--renderer-process-limit=2",
    "--process-per-site",
    "--disk-cache-size=52428800",       # 50 MB
    "--media-cache-size=10485760",      # 10 MB
]

# V8 heap cap per renderer — keeps JS-heavy tabs (YouTube, Figma, Sheets)
# from eating all RAM.
_V8_HEAP_FLAGS = [
    "--js-flags=--max-old-space-size=256",
]

# Low-end mode — feature trade-offs (WebGL, PDF viewer, etc. disabled).
# Only active when the user enables Low Power Mode or RAM < 4 GB.
_LOW_END_EXTRA_FLAGS = [
    "--disable-background-networking",
    "--disable-component-update",
    "--disable-default-apps",
    "--disable-domain-reliability",
    "--disable-sync",
    "--disable-extensions",
    "--disable-client-side-phishing-detection",
    "--disable-breakpad",
    "--disable-dev-shm-usage",
    "--enable-low-end-device-mode",
]


def build_chromium_flags(
    *,
    low_end: bool,
    webrtc_protection: bool = True,
    aggressive_process: bool = True,
) -> str:
    """Build QTWEBENGINE_CHROMIUM_FLAGS in tiers.

    Tiers:
      1. Base flags — always
      2. WebRTC protection — default on
      3. Safe process flags + V8 heap cap — default on, opt-out possible
      4. Low-end feature trade-offs — only when `low_end=True`
    """
    flags = list(_BASE_FLAGS)
    if webrtc_protection:
        flags.append(_WEBRTC_FLAG)
    if aggressive_process:
        flags.extend(_SAFE_PROCESS_FLAGS)
        flags.extend(_V8_HEAP_FLAGS)
    if low_end:
        flags.extend(_LOW_END_EXTRA_FLAGS)
    return " ".join(flags)