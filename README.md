<div align="center">

<img src="frame/data/ikon.png" alt="Frame logo" width="120">

# Frame

**A lightweight PyQt6 WebEngine browser, built for low-spec laptops.**

[![Tests](https://img.shields.io/github/actions/workflow/status/<owner>/<repo>/tests.yml?branch=main&label=tests)](../../actions)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](#-system-requirements)
[![PyQt6](https://img.shields.io/badge/PyQt6-%E2%89%A56.6-41cd52)](#-system-requirements)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](#-license)
[![Version](https://img.shields.io/badge/version-0.2.0-orange)](#-project-status)

**Language:** [🇮🇩 Indonesia](./README.id.md) · 🇬🇧 English

</div>

---

## 📋 Table of Contents

1. [Introduction](#-introduction)
2. [System Requirements](#-system-requirements)
3. [Installation](#-installation)
4. [Usage Guide](#-usage-guide)
5. [Project Structure & Code Documentation](#-project-structure--code-documentation)
6. [Testing](#-testing)
7. [Known Limitations](#-known-limitations)
8. [Contributing](#-contributing)
9. [Reporting Bugs](#-reporting-bugs)
10. [License](#-license)
11. [Contact](#-contact)
12. [Project Status](#-project-status)

---

## 📖 Introduction

**Frame** is a lightweight web browser built on top of **PyQt6** and the **QtWebEngine (Chromium)** rendering engine. This project exists to address one specific problem: most modern browsers (Chrome, Edge, Firefox) are fairly heavy on RAM/CPU, making them sluggish on low-spec laptops — while existing "lightweight" browser alternatives often sacrifice basic security features or day-to-day usability to get there.

Frame tries to strike a middle ground: it still runs on a mature, secure Chromium engine (via QtWebEngine), but with configuration, process limits, and a power-saving mode that can be tuned for devices with limited RAM — without dropping the core features expected from a modern browser.

### ✨ Key Features

| Category | Features |
|---|---|
| **Performance** | Low-End Mode (WebGL/PDF viewer disabled, renderer process limits), automatic system RAM detection, auto-suspend for idle tabs with a domain whitelist |
| **Tabs & Navigation** | Multi-tab with pin, duplicate, reopen closed tab (`Ctrl+Shift+T`), session + scroll-position restore, tab strip merged into the title bar (Chrome-style) |
| **Privacy & Security** | Host-list based AdBlocker, private browsing window (in-memory cache, no persistent cookies), WebRTC IP-leak protection, URL scheme whitelist (blocks `javascript:`, `data:`, `vbscript:`, etc.), per-site permission manager (camera/microphone/location/notifications) |
| **Interface** | Dark/light theme, frameless window with a custom title bar + glow border effect, bookmark bar with an overflow menu, find-in-page, toast notifications |
| **Convenience** | Bookmarks, history (max. 5,000 entries), download manager — all with built-in UI |
| **OS Integration** | Can be registered as a default-browser candidate (Windows/Linux), single-instance with IPC (a link clicked from another app is forwarded to the already-open window instead of opening a new one) |

### 🛠️ Core Technologies

- **[Python](https://www.python.org/)** 3.10+ — primary language
- **[PyQt6](https://www.riverbankcomputing.com/software/pyqt/)** — Qt6 bindings for the desktop UI
- **[PyQt6-WebEngine](https://pypi.org/project/PyQt6-WebEngine/)** (Chromium/QtWebEngine) — web page rendering engine
- **[pytest](https://pytest.org/)** — automated test framework
- **[PyInstaller](https://pyinstaller.org/)** — standalone build packaging (`.exe`/binary)
- **GitHub Actions** — CI, running the test matrix on Ubuntu/Windows/macOS × Python 3.10/3.12

> Frame does **not** use an external database or backend server — all data (bookmarks, history, session, settings) is stored locally as JSON files in the user's data directory. No `.env` file is required to run this project.

---

## 💻 System Requirements

Make sure the following are in place before installing:

| Requirement | Minimum Version | Notes |
|---|---|---|
| **Python** | 3.10 or newer | Check with `python --version` |
| **pip** | Latest version recommended | `python -m pip install --upgrade pip` |
| **RAM** | 4 GB (minimum), 8 GB (recommended) | Below 4 GB, Low-End Mode is enabled automatically |
| **Operating System** | Windows 10+, macOS 11+, or Linux (X11/Wayland) | |
| **Disk space** | ~500 MB free | For PyQt6 dependencies + QtWebEngine's bundled Chromium components |

### Python dependencies (installed automatically via `pip install`)

- `PyQt6 >= 6.6`
- `PyQt6-WebEngine >= 6.6`
- *(optional, dev)* `pytest >= 7.0`
- *(optional, perf)* `psutil >= 5.9`

### Additional system libraries (Linux only)

QtWebEngine needs a few system libraries that are usually not installed by default:

```bash
sudo apt install libegl1 libgl1 libxkbcommon-x11-0 \
  libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 \
  libxcb-render-util0 libxcb-shape0 libxcb-xinerama0 \
  libxcb-xfixes0 libxcb-sync1 libxcb-xkb1 libdbus-1-3
```

> Windows and macOS don't need this extra step — all native dependencies already ship inside the `PyQt6-WebEngine` wheel.

---

## 🚀 Installation

### 1. Clone the repository

```bash
git clone https://github.com/<owner>/<repo>.git
cd <repo>
```

### 2. Create a virtual environment (strongly recommended)

```bash
python -m venv .venv

# Activate it:
# Windows (PowerShell)
.venv\Scripts\Activate.ps1
# Windows (cmd)
.venv\Scripts\activate.bat
# Linux / macOS
source .venv/bin/activate
```

### 3. Install the project and its dependencies

```bash
# Standard install
pip install -e .

# If you also want to run the test suite (dev)
pip install -e ".[dev]"

# If you want more accurate RAM detection (optional)
pip install -e ".[perf]"
```

Running `pip install -e .` reads `pyproject.toml`, installs `PyQt6`/`PyQt6-WebEngine`, and registers the `frame` command as an entry point (see the `[project.scripts]` section in `pyproject.toml`).

### 4. Environment variables & configuration

Frame **does not require a `.env` file**. There's no API key, secret, or database connection to configure before running the app. The only relevant environment variable is optional:

| Variable | Purpose | Required? |
|---|---|---|
| `QTWEBENGINE_CHROMIUM_FLAGS` | Overrides the Chromium flags Frame applies by default (e.g. for performance experiments) | No — if set manually, Frame will print a warning to stderr that its built-in flags (including WebRTC protection) are not being applied |

Day-to-day app settings (theme, low-end mode, auto-suspend whitelist, etc.) are **not** configured through a manual config file — they're all available from the in-app **Settings** menu once the app is running, and are automatically saved as JSON in the user's data directory.

### 5. Database

**No database needs to be set up.** Bookmarks, history, session, and settings are stored as local JSON files (managed by the `frame/store.py` module), created automatically the first time the app runs.

---

## 📘 Usage Guide

### Running in a development environment

From the project root (with the virtual environment active):

```bash
python -m frame
```

Alternative — if the project is already installed (`pip install -e .`), you can also run it directly:

```bash
frame
```

On first launch, Frame automatically detects the system's RAM. If less than 4 GB is detected, **Low-End Mode** is enabled automatically (this can be changed manually at any time from Settings).

### Opening a URL directly from the command line

```bash
python -m frame https://example.com
```

If Frame is already running (another instance is detected via the single-instance mechanism), the URL is automatically forwarded to the already-open window instead of opening a new one.

### Running the test suite

```bash
pytest -q
```

### Building a standalone executable ("production" build)

Frame already ships a `Frame.spec` file for [PyInstaller](https://pyinstaller.org/):

```bash
pip install pyinstaller
pyinstaller Frame.spec
```

The build output will appear in the `dist/` folder.

### Registering Frame as a default-browser candidate (optional)

- **Windows**: run `python scripts/install_windows_default.py` and follow the on-screen instructions (import the generated `.reg` file, then manually select Frame via *Settings → Apps → Default apps* — Windows doesn't allow apps to change the default browser automatically).
- **Linux**: use a standard `.desktop` file (`xdg-settings set default-web-browser frame.desktop`).

### Basic usage examples

| Action | How |
|---|---|
| New tab | `Ctrl+T` or click the `+` icon |
| Reopen the last closed tab | `Ctrl+Shift+T` |
| Switch tabs | `Ctrl+Tab` / click a tab |
| Find in page | `Ctrl+F` |
| Private window | ☰ menu → *New Private Window* |
| Fullscreen | `F11` |
| Open Settings (theme, low-end mode, auto-suspend) | ☰ menu → *Settings* |

---

## 🗂️ Project Structure & Code Documentation

```
browser3/
├── frame/                      # Main source code (Python package)
│   ├── __main__.py             # Entry point: python -m frame
│   ├── core.py                 # Paths, logging, i18n, RAM detection, Chromium flags
│   ├── main_window.py          # Main window (frameless + tabs + toolbar)
│   ├── web.py                  # WebView, BrowserTab, BrowserTabBar, FrameWebPage
│   ├── tab_container.py        # Decouples QTabBar from QStackedWidget (tabs in title bar)
│   ├── titlebar.py             # Custom title bar (drag, resize, window buttons)
│   ├── chrome.py               # Frameless window chrome + glow border effect
│   ├── ui_bars.py              # FindBar, BookmarkBar (with overflow), DownloadShelf
│   ├── theme.py                # Theme colors, QSS stylesheet, Qt palette
│   ├── icons.py                # SVG icon → QIcon rendering (DPI-aware, cached)
│   ├── dialogs.py               # Bookmarks, History, Downloads, Settings dialogs
│   ├── store.py                # Persistence: bookmarks, history, session, settings (JSON)
│   ├── suspend_manager.py      # Idle tab auto-suspend, pinning, whitelist
│   ├── permissions.py          # Per-origin permission manager (camera, mic, etc.)
│   ├── adblock.py              # Host-list based AdBlocker
│   ├── internal.py             # `frame://` scheme + New Tab page
│   ├── private_window.py       # Private browsing window (MainWindow wrapper)
│   ├── singleton.py            # Single-instance IPC (QLocalServer/QLocalSocket)
│   ├── spinner.py              # Spinning loading indicator on tabs
│   ├── toast.py                # Non-blocking toast notifications
│   └── data/                   # Static assets: adblock_hosts.txt, icons, i18n strings
├── scripts/                     # Support scripts (Windows default-browser registration)
├── tests/                       # Unit tests (pytest)
├── run_frame.py                 # Dedicated entry point for PyInstaller
├── Frame.spec                   # PyInstaller build configuration
├── pyproject.toml                # Project metadata & dependencies
└── .github/workflows/tests.yml   # CI: test matrix (3 OSes × 2 Python versions)
```

### Overview of the main modules

<details>
<summary><strong>frame/core.py</strong> — Application foundation</summary>

Contains data-directory paths, logging setup, the i18n loader, the list of search engines, URL safety validation (`is_safe_url`), and the RAM-detection + Chromium-flag-building logic (`pre_init_should_use_low_end()`, `detect_total_ram_gb()`). These functions are called very early, **before** `QApplication` is created.
</details>

<details>
<summary><strong>frame/main_window.py</strong> — Main window</summary>

The `MainWindow` class: assembles the navigation toolbar, address bar, tab container, and all dialogs. Handles session restore, keyboard shortcuts, and coordination between modules (theme, suspend manager, permission manager).
</details>

<details>
<summary><strong>frame/web.py</strong> — Web engine layer</summary>

`WebView` (a `QWebEngineView` subclass), `BrowserTab` (one tab = one `WebView` + metadata), `BrowserTabBar` (custom tab bar with fixed width & eliding), and `FrameWebPage` (a `QWebEnginePage` subclass for intercepting navigation, permission requests, and fullscreen).
</details>

<details>
<summary><strong>frame/store.py</strong> — Data persistence</summary>

The `Store` class: reads/writes bookmarks, history (capped at 5,000 entries via a `deque`), the last tab session, and user settings — all as local JSON files in the data directory. No external database dependency.
</details>

<details>
<summary><strong>frame/suspend_manager.py</strong> — Idle tab management</summary>

Suspends tabs that have been inactive beyond a certain duration (default 180 seconds) to save RAM, with exceptions for pinned tabs, whitelisted domains, or tabs with an unsubmitted form.
</details>

<details>
<summary><strong>frame/permissions.py</strong> — Per-site permissions</summary>

Handles the <code>featurePermissionRequested</code> signal from <code>QWebEnginePage</code> (camera, microphone, location, notifications, clipboard, mouse lock). Permission decisions are stored per-origin so the user isn't asked repeatedly.
</details>

<details>
<summary><strong>frame/adblock.py</strong> — Ad blocker</summary>

A simple AdBlocker based on host matching from <code>frame/data/adblock_hosts.txt</code>, extendable (overridable) via a <code>filters.txt</code> file in the user's data directory. Active in every mode, including private browsing.
</details>

> Every module has a docstring at the top of the file briefly explaining its responsibility — open the relevant file directly for details on each function/class's parameters and return values.

---

## 🧪 Testing

This project has unit tests under `tests/`, covering:

- `test_adblock.py` — AdBlocker host matching & filter parsing
- `test_permissions.py` — permission decision logic, persistence, private mode
- `test_store.py` — bookmarks, history, top sites, JSON I/O
- `test_suspend_manager.py` — whitelist, toggling, async "dirty form" detection
- `test_url_safety.py` — allowed URL scheme validation

Run the whole suite:

```bash
pytest -q
```

CI (GitHub Actions, `.github/workflows/tests.yml`) runs these tests automatically on every `push`/`pull request` to the `main`/`master` branch, across a matrix of **Ubuntu, Windows, and macOS** × **Python 3.10 and 3.12**.

There's also an optional `.pre-commit-config.yaml` that runs `pytest` automatically before every `git commit` (enable it with `pre-commit install`).

---

## ⚠️ Known Limitations

- **WebRTC**: Frame restricts ICE candidates to public interfaces only (`--force-webrtc-ip-handling-policy=default_public_interface_only`) to close the classic "WebRTC leak" that exposes your real IP while a VPN is active. Can be turned off from *Settings → Privacy*.
- **User-Agent**: Frame **deliberately does not spoof** the QtWebEngine User-Agent. Spoofing the UA without also adjusting Client Hints can make the fingerprint even more distinctive, and doesn't solve fingerprinting from other signals (TLS ClientHello, canvas/WebGL, font list, etc.) anyway.
- **DNS**: DNS queries go out in plaintext to the OS resolver (no built-in DNS-over-HTTPS yet). This matches the default behavior of most other browsers.
- **Default permissions**: All web permission requests (camera, microphone, location, etc.) are **denied by default** unless the user explicitly grants them.
- **Not a full browser replacement**: no extensions, no cross-device bookmark sync, and no integrated password manager yet — good for personal use/experimentation, not yet ideal as a general user's daily-driver browser.

---

## 🤝 Contributing

Contributions of any kind — bug reports, feature ideas, or pull requests — are very welcome.

1. **Fork** this repository, then create a new branch from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```
2. Make sure your dev environment is installed: `pip install -e ".[dev]"`.
3. Write/update tests for your change under `tests/`.
4. Run the test suite before committing:
   ```bash
   pytest -q
   ```
5. (Optional but recommended) enable the pre-commit hook: `pre-commit install`.
6. Commit with a clear message, then open a **Pull Request** against `main` describing the change and the reasoning behind it.

For larger changes (e.g. a UI redesign or architectural change), it's a good idea to open a discussion **Issue** first before writing code, to make sure the direction lines up with the project's goals.

---

## 🐛 Reporting Bugs

Before filing a report, check whether a similar issue already exists. If not, open a new issue and include the following so it can be diagnosed faster:

- **Frame version** (see `frame/__init__.py` → `__version__`, or `pyproject.toml`)
- **Operating system** and version (e.g. Windows 11 23H2)
- **Python version** (`python --version`) and **PyQt6** version (`pip show PyQt6`)
- **Clear, ordered reproduction steps**
- **Expected behavior** vs. **actual behavior**
- **Console log** from running `python -m frame` in a terminal (not by double-clicking), including any error/traceback
- **Screenshot/screen recording**, if it's UI/appearance-related

---

## 📄 License

This project is licensed under the **MIT License** — see the [`LICENSE`](./LICENSE) file for the full text.

---

## 📬 Contact

The fastest way to ask questions, suggest ideas, or report issues is through **GitHub Issues** on this repository. Fill in the other contact details below as you prefer, as the project maintainer:

- **Issues/Discussion**: use the *Issues* tab on this GitHub repository
- **Maintainer**: `<your name/username>`
- **Email** *(optional)*: `<your contact email>`

---

## 📊 Project Status

| Aspect | Status |
|---|---|
| **Latest release version** | `0.2.0` (see `pyproject.toml`) |
| **Development status** | Actively developed (pre-1.0, not yet recommended for wide distribution to general users) |
| **CI/Build** | GitHub Actions — test matrix across 3 OSes × 2 Python versions (see badge above) |
| **Test coverage** | 5 core modules covered by unit tests (`adblock`, `permissions`, `store`, `suspend_manager`, `url_safety`) |
| **Supported platforms** | Windows 10+, macOS 11+, Linux (X11/Wayland) |

---

<div align="center">

Built with 🖤 using Python & PyQt6.

</div>
