"""Main Frame window (frameless + tapered glow border)."""
from __future__ import annotations

import os
import time
from pathlib import Path

from PyQt6.QtCore import QEvent, QSize, Qt, QTimer, QUrl
from PyQt6.QtGui import QAction, QIcon, QKeySequence
from PyQt6.QtWebEngineCore import QWebEngineProfile
from PyQt6.QtWidgets import (
    QLineEdit, QMainWindow, QMenu, QMessageBox, QStatusBar, QTabBar,
    QTabWidget, QToolBar, QToolButton, QVBoxLayout, QWidget,
)

from .adblock import AdBlocker
from .chrome import CustomTitleBar, FramelessHelper, GlowBorder, GlowMode
from .core import (
    APP_NAME, DEFAULT_HOME, SCHEME, SEARCH_ENGINES, is_safe_url,
    log, tr,
)
from .dialogs import (
    BookmarksDialog, DownloadsDialog, HistoryDialog, SettingsDialog,
)
from .icons import (
    SVG_BACK, SVG_CLOSE, SVG_DOWNLOAD, SVG_ENTER, SVG_FORWARD, SVG_HOME,
    SVG_INFO, SVG_INSECURE, SVG_LOCK, SVG_MENU, SVG_NEW, SVG_RELOAD,
    SVG_SEARCH, SVG_STAR_FILLED, SVG_STAR_OUTLINE,
    clear_icon_cache, icon_from_svg,
)
from .internal import InternalSchemeHandler
from .spinner import TabSpinner
from .store import Store
from .suspend_manager import SuspendManager
from .theme import THEMES, apply_theme
from .toast import ToastHost
from .ui_bars import BookmarkBar, DownloadShelf, FindBar
from .web import BrowserTab, BrowserTabBar


def _load_app_icon() -> QIcon:
    """Load app icon with all resolutions for sharp title bar + taskbar."""
    data_dir = Path(__file__).parent / "data"
    ico_path = data_dir / "ikon.ico"
    png_path = data_dir / "ikon.png"

    icon = QIcon()
    added = False

    if ico_path.exists():
        icon.addFile(str(ico_path))
        added = True

    if png_path.exists():
        for size in (16, 24, 32, 48, 64, 128, 256):
            icon.addFile(str(png_path), QSize(size, size))
        added = True

    if not added:
        log.warning("No icon file in %s", data_dir)

    return icon


class MainWindow(QMainWindow):
    """Main browser window. Incognito mode via `private=True`."""

    _private_windows: list["MainWindow"] = []

    def __init__(
        self,
        pre_init_low_end: bool | None = None,
        *,
        private: bool = False,
    ) -> None:
        super().__init__()
        self._private = private
        self.setWindowTitle(tr("private.title") if private else APP_NAME)
        self.resize(1200, 800)
        self.setMinimumSize(720, 480)
        self.setWindowIcon(_load_app_icon())

        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowSystemMenuHint
            | Qt.WindowType.WindowMinMaxButtonsHint
        )

        self.store = Store(self)
        _theme = self.store.settings.get("theme", "dark")
        apply_theme(_theme)

        glow_mode: GlowMode = self.store.settings.get("window_glow", "rgb")
        if glow_mode not in ("off", "static", "rgb"):
            glow_mode = "rgb"

        if not private and not self.store.settings.get("first_run_done"):
            if pre_init_low_end:
                self.store.settings["low_end_mode"] = True
                self.store.settings["max_tabs"] = 8
                self.store.settings["auto_suspend_tabs"] = True
                self.store.settings["suspend_after_sec"] = 120
            self.store.settings["first_run_done"] = True
            self.store.save()

        # ── Profile ────────────────────────────────────────────────
        if private:
            self.profile = QWebEngineProfile(self)
            self.profile.setHttpCacheType(
                QWebEngineProfile.HttpCacheType.MemoryHttpCache
            )
            self.profile.setPersistentCookiesPolicy(
                QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies
            )
        else:
            self.profile = QWebEngineProfile.defaultProfile()
            self.profile.setPersistentStoragePath(str(self.store.dir / "profile"))
            self.profile.setCachePath(str(self.store.dir / "cache"))
            self.profile.setPersistentCookiesPolicy(
                QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies
            )
            try:
                if self.store.settings.get("low_end_mode", False):
                    self.profile.setHttpCacheMaximumSize(25 * 1024 * 1024)
                else:
                    self.profile.setHttpCacheMaximumSize(150 * 1024 * 1024)
            except (AttributeError, RuntimeError) as exc:
                log.debug("setHttpCacheMaximumSize failed: %s", exc)

        self.adblocker = AdBlocker(self.store.dir, self)
        self.adblocker.enabled = self.store.settings.get("adblock_enabled", True)
        self.profile.setUrlRequestInterceptor(self.adblocker)

        self.profile.downloadRequested.connect(self.handle_download)
        self.internal_handler = InternalSchemeHandler(self.store, self)
        self.profile.installUrlSchemeHandler(SCHEME, self.internal_handler)

        # ── Lazy dialogs ───────────────────────────────────────────
        self._bookmarks_dlg: BookmarksDialog | None = None
        self._history_dlg: HistoryDialog | None = None
        self._downloads_dlg: DownloadsDialog | None = None
        self._settings_dlg: SettingsDialog | None = None

        # ── Tab spinners ───────────────────────────────────────────
        # tab.id() -> TabSpinner
        self._tab_spinners: dict[int, TabSpinner] = {}

        # ── Tabs ───────────────────────────────────────────────────
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setTabsClosable(False)
        _tab_bar = BrowserTabBar()
        self.tabs.setTabBar(_tab_bar)
        self.tabs.setMovable(True)
        _tab_bar.setMovable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.current_tab_changed)
        tb = self.tabs.tabBar()
        tb.setUsesScrollButtons(True)
        tb.setElideMode(Qt.TextElideMode.ElideRight)
        tb.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        tb.customContextMenuRequested.connect(self._tab_context_menu)
        tb.middle_clicked.connect(self.close_tab)

        plus_btn = QToolButton()
        plus_btn.setObjectName("NewTabButton")
        plus_btn.setText("+")
        plus_btn.setToolTip("New tab (Ctrl+T)")
        plus_btn.setFixedSize(28, 28)
        plus_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        plus_btn.clicked.connect(lambda: self.add_new_tab())
        self.tabs.setCornerWidget(plus_btn, Qt.Corner.TopRightCorner)

        self.suspend_mgr = SuspendManager(self.tabs, self.store)

        # ── Bookmark bar ───────────────────────────────────────────
        if private:
            self.bookmark_bar = None
        else:
            self.bookmark_bar = BookmarkBar(self.store)
            self.bookmark_bar.open_requested.connect(self.open_url_in_current)
            self.bookmark_bar.set_user_visible(
                self.store.settings.get("show_bookmark_bar", True)
            )

        # ── Download shelf & find bar ──────────────────────────────
        self.download_shelf = DownloadShelf()
        self.download_shelf.hide()
        self.download_shelf.show_all_requested.connect(self.show_downloads)

        self.findbar = FindBar()
        self.findbar.hide()

        # ── Chrome: glow border + title bar ────────────────────────
        self.glow = GlowBorder(
            theme_getter=lambda: self.store.settings.get("theme", "dark"),
            mode=glow_mode,
            glow_width=self.store.settings.get("window_glow_width", 1),
            radius=8,
            taper_ratio=self.store.settings.get("window_glow_taper", 0.4),
            light_style=self.store.settings.get("window_glow_light_style", "solid"),
            light_sat=self.store.settings.get("window_glow_light_sat", 0.95),
            light_lightness=self.store.settings.get(
                "window_glow_light_lightness", 0.32
            ),
        )
        glow_lay = self.glow.content_layout()

        self.title_bar = CustomTitleBar(self)
        glow_lay.addWidget(self.title_bar)

        self._build_toolbar()
        glow_lay.addWidget(self.navtb)

        if self.bookmark_bar is not None:
            glow_lay.addWidget(self.bookmark_bar)
        glow_lay.addWidget(self.findbar)
        glow_lay.addWidget(self.tabs, 1)
        glow_lay.addWidget(self.download_shelf)

        # ── Orphan status bar ──────────────────────────────────────
        self.status = QStatusBar(self)

        self.setCentralWidget(self.glow)

        # ── Toast ──────────────────────────────────────────────────
        self.toast = ToastHost(self)

        # ── Frameless resize helper ────────────────────────────────
        self._frameless = FramelessHelper(
            window=self,
            source_widget=self.glow,
            border=self.glow.glow_width() + 4,
        )

        # ── Shortcuts ──────────────────────────────────────────────
        self._make_shortcut(QKeySequence("Ctrl+T"), lambda: self.add_new_tab())
        self._make_shortcut(QKeySequence("Ctrl+W"),
                            lambda: self.close_tab(self.tabs.currentIndex()))
        self._make_shortcut(QKeySequence("Ctrl+L"), self.focus_urlbar)
        self._make_shortcut(QKeySequence("Ctrl+R"), lambda: self.current_view().reload())
        self._make_shortcut(QKeySequence("F5"), lambda: self.current_view().reload())
        self._make_shortcut(QKeySequence("Ctrl+Shift+T"), self.reopen_last_tab)
        self._make_shortcut(QKeySequence("Ctrl+D"), self.toggle_bookmark)
        self._make_shortcut(QKeySequence("Ctrl+Shift+B"), self.toggle_bookmark_bar)
        self._make_shortcut(QKeySequence("Ctrl+H"), self.show_history)
        self._make_shortcut(QKeySequence("Ctrl+J"), self.show_downloads)
        self._make_shortcut(QKeySequence("Ctrl+F"), self.show_find)
        self._make_shortcut(QKeySequence("Ctrl+="), self.zoom_in)
        self._make_shortcut(QKeySequence("Ctrl++"), self.zoom_in)
        self._make_shortcut(QKeySequence("Ctrl+-"), self.zoom_out)
        self._make_shortcut(QKeySequence("Ctrl+0"), self.zoom_reset)
        self._make_shortcut(QKeySequence("F11"), self.toggle_fullscreen)
        self._make_shortcut(QKeySequence("Alt+Left"), lambda: self.current_view().back())
        self._make_shortcut(QKeySequence("Alt+Right"), lambda: self.current_view().forward())

        self.closed_tabs: list[QUrl] = []

        # ── Auto-suspend timer ─────────────────────────────────────
        self._suspend_timer = QTimer(self)
        self._suspend_timer.setInterval(30_000)
        self._suspend_timer.timeout.connect(self._maybe_suspend_tabs)
        if self.store.settings.get("auto_suspend_tabs", False):
            self._suspend_timer.start()

        # ── Restore session / initial tab ──────────────────────────
        restored = False
        if (
            not private
            and self.store.settings.get("restore_session", True)
            and self.store.session
        ):
            urls = [
                u for u in self.store.session
                if u and u != "about:blank" and is_safe_url(u)
            ]
            if urls:
                for u in urls:
                    self.add_new_tab(QUrl(u), "New Tab", switch=False, force=True)
                self.tabs.setCurrentIndex(0)
                restored = True

                max_t = self.store.settings.get("max_tabs", 30)
                if self.tabs.count() > max_t:
                    for i in range(max_t, self.tabs.count()):
                        self._suspend_tab(i)

        if not restored:
            self.add_new_tab(None, "New Tab")

    # ── Screen change (DPR changed) ────────────────────────────────
    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        screen_change = getattr(QEvent.Type, "ScreenChangeInternal", None)
        if screen_change is None:
            return
        if event.type() == screen_change:
            clear_icon_cache()
            self._rebuild_icons()

    # ── Spinner helpers ────────────────────────────────────────────
    def _start_spinner(self, tab) -> None:
        spinner = self._tab_spinners.get(id(tab))
        if spinner is None:
            return
        theme = THEMES.get(self.store.settings.get("theme", "dark"), THEMES["dark"])
        spinner.set_color(theme["muted"])
        spinner.start()

    def _stop_spinner(self, tab) -> None:
        spinner = self._tab_spinners.get(id(tab))
        if spinner is None:
            return
        spinner.stop()
        # Favicon bisa datang setelah loadFinished; pastikan pakai
        # yang terbaru kalau sudah ada.
        self._update_tab_icon(tab)

    # ── Toolbar ────────────────────────────────────────────────────
    def _build_toolbar(self) -> None:
        theme = THEMES.get(self.store.settings.get("theme", "dark"), THEMES["dark"])
        ic = theme["text"]

        self.navtb = QToolBar("Navigation")
        self.navtb.setIconSize(QSize(20, 20))
        self.navtb.setMovable(False)

        def add_action(svg, tip, slot):
            act = QAction(icon_from_svg(svg, color=ic, size=24), "", self)
            act.setToolTip(tip)
            act.triggered.connect(slot)
            self.navtb.addAction(act)
            return act

        add_action(SVG_BACK, "Back (Alt+←)", lambda: self.current_view().back())
        add_action(SVG_FORWARD, "Forward (Alt+→)", lambda: self.current_view().forward())
        add_action(SVG_RELOAD, "Reload (Ctrl+R)", lambda: self.current_view().reload())
        add_action(SVG_HOME, "Home", self.navigate_home)

        self.navtb.addSeparator()

        self.urlbar = QLineEdit()
        self.urlbar.setMinimumWidth(400)
        self.urlbar.setPlaceholderText("Search or type a URL")
        self.urlbar.returnPressed.connect(self.navigate_to_url)
        self.navtb.addWidget(self.urlbar)

        self.security_action = QAction(
            icon_from_svg(SVG_INFO, color=theme["muted"], size=16), "", self
        )
        self.security_action.setToolTip("Internal page")
        self.security_action.triggered.connect(self._show_connection_info)
        self.urlbar.addAction(
            self.security_action, QLineEdit.ActionPosition.LeadingPosition
        )

        search_icon = icon_from_svg(SVG_SEARCH, color="#808080", size=18)
        self.urlbar.addAction(search_icon, QLineEdit.ActionPosition.TrailingPosition)
        self.urlbar.setClearButtonEnabled(True)

        add_action(SVG_ENTER, "Open (Enter)", self.navigate_to_url)

        self.star_action = QAction(
            icon_from_svg(SVG_STAR_OUTLINE, color=ic, size=24), "", self
        )
        self.star_action.setToolTip("Bookmark this page (Ctrl+D)")
        self.star_action.triggered.connect(self.toggle_bookmark)
        self.navtb.addAction(self.star_action)

        add_action(SVG_DOWNLOAD, "Downloads (Ctrl+J)", self.show_downloads)
        add_action(SVG_NEW, "New tab (Ctrl+T)", lambda: self.add_new_tab())

        menu = QMenu(self)

        def add_menu_item(text, slot, shortcut=None):
            display = f"{text}\t{shortcut}" if shortcut else text
            act = QAction(display, self)
            act.triggered.connect(slot)
            menu.addAction(act)
            return act

        add_menu_item("New tab", lambda: self.add_new_tab(), "Ctrl+T")
        add_menu_item("Incognito window", self.open_private_window)
        menu.addSeparator()
        add_menu_item("Bookmarks", self.show_bookmarks)
        add_menu_item("History", self.show_history, "Ctrl+H")
        add_menu_item("Downloads", self.show_downloads, "Ctrl+J")
        menu.addSeparator()
        add_menu_item("Find in page", self.show_find, "Ctrl+F")
        add_menu_item("Zoom in", self.zoom_in, "Ctrl++")
        add_menu_item("Zoom out", self.zoom_out, "Ctrl+-")
        add_menu_item("Reset zoom", self.zoom_reset, "Ctrl+0")
        add_menu_item("Fullscreen", self.toggle_fullscreen, "F11")
        menu.addSeparator()
        add_menu_item("Sleep idle tabs now", self._suspend_idle_now)
        add_menu_item(tr("menu.settings"), self.show_settings)
        menu.addSeparator()
        add_menu_item("Quit", self.close, "Ctrl+Q")

        menu_btn = QToolButton()
        menu_btn.setIcon(icon_from_svg(SVG_MENU, color=ic, size=24))
        menu_btn.setToolTip("Menu")
        menu_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu_btn.setMenu(menu)
        self.navtb.addWidget(menu_btn)

    def _make_shortcut(self, seq, func) -> None:
        act = QAction(self)
        act.setShortcut(seq)
        act.triggered.connect(func)
        self.addAction(act)

    # ── Tab management ─────────────────────────────────────────────
    def _install_tab_close_button(self, idx: int) -> None:
        bar = self.tabs.tabBar()
        tab = self.tabs.widget(idx)
        if tab is None:
            return
        theme = THEMES.get(self.store.settings.get("theme", "dark"), THEMES["dark"])
        btn = QToolButton()
        btn.setObjectName("TabCloseButton")
        btn.setToolTip("Close tab (Ctrl+W)")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setAutoRaise(True)
        btn.setIcon(icon_from_svg(SVG_CLOSE, color=theme["muted"], size=14))
        btn.clicked.connect(lambda _, t=tab: self.close_tab(self.tabs.indexOf(t)))
        bar.setTabButton(idx, QTabBar.ButtonPosition.RightSide, btn)

    def _forget_tab(self, tab) -> None:
        if tab is None:
            return
        self.closed_tabs.append(tab.view.url())
        self.suspend_mgr.forget(tab)
        # Hentikan spinner kalau masih jalan.
        spinner = self._tab_spinners.pop(id(tab), None)
        if spinner is not None:
            spinner.stop()

    def _format_tab_label(self, tab, title: str) -> str:
        title = (title or "New Tab").strip()
        if self.suspend_mgr.is_suspended(tab):
            return "💤 " + title[:16]
        if self.suspend_mgr.is_pinned(tab):
            return "📌 " + title[:24]
        return title

    def add_new_tab(self, qurl=None, label="New Tab", switch=True, force=False):
        if not force:
            max_t = self.store.settings.get("max_tabs", 30)
            if self.tabs.count() >= max_t:
                QMessageBox.information(
                    self, tr("tab.limit.title"),
                    tr("tab.limit.body", count=self.tabs.count(), max=max_t),
                )
                return None

        tab = BrowserTab(self, profile=self.profile)
        i = self.tabs.addTab(tab, label)
        if switch:
            self.tabs.setCurrentIndex(i)
        self._install_tab_close_button(i)
        self.suspend_mgr.touch(tab)

        # Spinner per tab.
        spinner = TabSpinner(self, tab)
        self._tab_spinners[id(tab)] = spinner

        tab.view.urlChanged.connect(lambda url, t=tab: self.update_urlbar(url, t))
        tab.view.titleChanged.connect(lambda title, t=tab: self.update_tab_title(t, title))
        tab.view.iconChanged.connect(lambda _icon, t=tab: self._update_tab_icon(t))
        tab.view.loadStarted.connect(lambda t=tab: self._start_spinner(t))
        tab.view.loadFinished.connect(lambda ok, t=tab: self._stop_spinner(t))
        tab.view.loadFinished.connect(lambda ok, t=tab: self.on_load_finished(t, ok))
        tab.view.page().linkHovered.connect(self._on_link_hovered)

        if qurl is None:
            target = QUrl("frame://newtab")
        elif isinstance(qurl, QUrl):
            target = qurl
        else:
            target = QUrl(qurl)

        if target.isEmpty() or not is_safe_url(target.toString()):
            if not target.isEmpty():
                log.warning("add_new_tab blocked: %s", target.toString()[:120])
            target = QUrl("frame://newtab")

        tab.view.setUrl(target)
        return tab

    def _update_tab_icon(self, tab) -> None:
        i = self.tabs.indexOf(tab)
        if i == -1:
            return
        # Jangan timpa spinner yang sedang aktif.
        spinner = self._tab_spinners.get(id(tab))
        if spinner is not None and spinner.is_running():
            return
        try:
            icon = tab.view.icon()
        except RuntimeError:
            return
        if icon is not None and not icon.isNull():
            self.tabs.setTabIcon(i, icon)

    def close_tab(self, i: int) -> None:
        if i < 0:
            return
        if self.tabs.count() <= 1:
            self.close()
            return
        self._forget_tab(self.tabs.widget(i))
        self.tabs.removeTab(i)

    def reopen_last_tab(self) -> None:
        if self.closed_tabs:
            url = self.closed_tabs.pop()
            self.add_new_tab(url, "New Tab")

    def current_tab_changed(self, i: int) -> None:
        if i < 0:
            return
        tab = self.tabs.widget(i)
        if tab is None:
            return

        self.suspend_mgr.touch(tab)
        if self.suspend_mgr.is_suspended(tab):
            self._unsuspend_tab(i)

        qurl = tab.view.url()
        self.update_urlbar(qurl, tab)
        self.setWindowTitle(tr("private.title") if self._private else APP_NAME)
        if self.findbar.isVisible():
            self.findbar.set_view(tab.view)

        if self.store.settings.get("auto_suspend_tabs", False):
            self._suspend_timer.start()

    def current_view(self):
        tab = self.tabs.currentWidget()
        return tab.view if tab else None

    def update_tab_title(self, tab, title=None) -> None:
        i = self.tabs.indexOf(tab)
        if i == -1:
            return
        if title is None:
            title = tab.view.title()
        title = title or "New Tab"
        self.tabs.setTabText(i, self._format_tab_label(tab, title))
        self.tabs.setTabToolTip(i, title)

    def on_load_finished(self, tab, ok: bool) -> None:
        self.update_tab_title(tab)
        if ok:
            url = tab.view.url().toString()
            if url.startswith("http"):
                self.store.add_history(tab.view.title(), url)
        if tab is self.tabs.currentWidget():
            self._refresh_star()
            self._update_security_indicator(tab.view.url())

    def _on_link_hovered(self, link: str) -> None:
        # Status bar dihapus — link hover tidak ditampilkan.
        pass

    # ── Suspend / resume ───────────────────────────────────────────
    def _apply_suspended_ui(self, idx: int, res: tuple) -> None:
        tab = self.tabs.widget(idx)
        if tab is None:
            return
        url, title, _scroll = res
        self.tabs.setTabText(idx, self._format_tab_label(tab, title))
        self.tabs.setTabToolTip(
            idx, f"{title}\n{url}\n\n(asleep — click to reload)"
        )

    def _suspend_tab(self, idx: int, manual: bool = False) -> None:
        res = self.suspend_mgr.suspend(idx, manual=manual)
        if res is None:
            return
        self._apply_suspended_ui(idx, res)

    def _unsuspend_tab(self, idx: int) -> None:
        tab = self.tabs.widget(idx)
        if tab is None:
            return
        res = self.suspend_mgr.unsuspend(idx)
        if res is None:
            return
        url, scroll_y = res
        title = tab.view.title() or "Tab"
        self.tabs.setTabText(idx, self._format_tab_label(tab, title))
        self.tabs.setTabToolTip(idx, url)

        if scroll_y:
            def _restore_scroll(ok):
                if not ok:
                    return
                try:
                    tab.view.page().runJavaScript(
                        f"window.scrollTo(0, {int(scroll_y)});",
                        lambda _: None,
                    )
                except (AttributeError, RuntimeError):
                    pass

            try:
                tab.view.loadFinished.disconnect(_restore_scroll)
            except TypeError:
                pass
            tab.view.loadFinished.connect(_restore_scroll)

    def _maybe_suspend_tabs(self) -> None:
        if not self.store.settings.get("auto_suspend_tabs", False):
            return
        timeout = self.store.settings.get("suspend_after_sec", 180)
        for tab in self.suspend_mgr.idle_tabs(timeout):
            self.suspend_mgr.check_dirty_and_suspend(
                tab, on_done=self._make_auto_suspend_cb(tab)
            )

    def _make_auto_suspend_cb(self, tab):
        def cb(ok: bool, res):
            if not (ok and res is not None):
                return
            try:
                idx = self.tabs.indexOf(tab)
            except RuntimeError:
                return
            if idx < 0:
                return
            self._apply_suspended_ui(idx, res)
        return cb

    def _suspend_idle_now(self) -> None:
        indices, skipped = self.suspend_mgr.suspendable_now()
        for i in indices:
            self._suspend_tab(i)
        if indices:
            msg = f"{len(indices)} tab(s) put to sleep."
            if skipped:
                msg += f" ({skipped} skipped — whitelist/pinned)"
            self.toast.show_message(msg, key="suspend")
        else:
            self.toast.show_message(
                "No tabs to put to sleep.", key="suspend"
            )

    # ── Navigation ─────────────────────────────────────────────────
    def focus_urlbar(self) -> None:
        self.urlbar.setFocus()
        self.urlbar.selectAll()

    def navigate_home(self) -> None:
        view = self.current_view()
        if view:
            view.setUrl(QUrl(self.store.settings.get("homepage", DEFAULT_HOME)))

    def navigate_to_url(self) -> None:
        text = self.urlbar.text().strip()
        if not text:
            return
        view = self.current_view()
        if view is None:
            return

        if text.startswith(("frame://", "about:", "file://", "view-source:")):
            if not is_safe_url(text):
                self.toast.show_message(
                    tr("url.blocked", url=text[:80]), key="url", duration_ms=4000
                )
                return
            view.setUrl(QUrl(text))
            return

        looks_like_url = text.startswith(("http://", "https://")) or (
            "." in text and " " not in text and not text.startswith(".")
        )
        if looks_like_url:
            url = text if text.startswith(("http://", "https://")) else "http://" + text
        else:
            engine_name = self.store.settings.get("search_engine", "Google")
            engine = SEARCH_ENGINES.get(engine_name, SEARCH_ENGINES["Google"])
            q = QUrl.toPercentEncoding(text).data().decode()
            url = f"{engine['action']}?{engine['param']}={q}"

        if not is_safe_url(url):
            self.toast.show_message(
                tr("url.blocked", url=url[:80]), key="url", duration_ms=4000
            )
            return
        view.setUrl(QUrl(url))
        self.urlbar.clearFocus()

    def update_urlbar(self, qurl, tab=None) -> None:
        if tab is not None and tab is not self.tabs.currentWidget():
            return
        self.urlbar.setText(qurl.toString())
        self.urlbar.setCursorPosition(0)
        self._refresh_star()
        self._update_security_indicator(qurl)

    def _update_security_indicator(self, qurl: QUrl) -> None:
        if not hasattr(self, "security_action"):
            return

        scheme = qurl.scheme().lower()
        host = qurl.host() or ""
        theme = THEMES.get(self.store.settings.get("theme", "dark"), THEMES["dark"])

        if scheme == "https":
            icon = icon_from_svg(SVG_LOCK, color="#4caf50", size=16)
            tip = (f"Encrypted connection (HTTPS)\n{host}" if host
                   else "Encrypted connection (HTTPS)")
        elif scheme == "http":
            icon = icon_from_svg(SVG_INSECURE, color="#f44336", size=16)
            tip = (f"Not encrypted (HTTP) — do not enter sensitive data!\n{host}"
                   if host else
                   "Not encrypted (HTTP) — do not enter sensitive data!")
        elif scheme == "frame":
            icon = icon_from_svg(SVG_INFO, color=theme["muted"], size=16)
            tip = "Frame internal page"
        elif scheme == "file":
            icon = icon_from_svg(SVG_INFO, color=theme["muted"], size=16)
            tip = "Local file"
        elif scheme in ("about", "view-source"):
            icon = icon_from_svg(SVG_INFO, color=theme["muted"], size=16)
            tip = f"Page {scheme}:"
        else:
            icon = icon_from_svg(SVG_INFO, color=theme["muted"], size=16)
            tip = scheme or "Unknown"

        self.security_action.setIcon(icon)
        self.security_action.setToolTip(tip)

    def _show_connection_info(self) -> None:
        view = self.current_view()
        if view is None:
            return
        qurl = view.url()
        scheme = qurl.scheme().lower()
        host = qurl.host() or "(none)"

        if scheme == "https":
            title = "Encrypted Connection"
            body = (
                f"<p><b>Scheme:</b> HTTPS</p>"
                f"<p><b>Host:</b> {host}</p>"
                "<p>Traffic between Frame and the server is encrypted with "
                "TLS. The server certificate is verified by Chromium.</p>"
                "<p style='color:#888;font-size:11px'>"
                "Frame does not perform pinning or additional validation — "
                "certificate trust relies entirely on the system trust store.</p>"
            )
        elif scheme == "http":
            title = "Unencrypted Connection"
            body = (
                f"<p><b>Scheme:</b> HTTP</p>"
                f"<p><b>Host:</b> {host}</p>"
                "<p><b style='color:#f44336'>Warning:</b> this page is "
                "not encrypted. Do not enter passwords, card numbers, or "
                "other sensitive data — it can be intercepted on public "
                "networks.</p>"
            )
        elif scheme == "frame":
            title = "Frame Internal Page"
            body = (
                f"<p><b>Scheme:</b> frame://</p>"
                f"<p><b>Host:</b> {host}</p>"
                "<p>This page is generated by Frame itself, not fetched "
                "from the internet.</p>"
            )
        elif scheme == "file":
            title = "Local File"
            body = (
                f"<p><b>Scheme:</b> file://</p>"
                f"<p><b>Path:</b> {qurl.toLocalFile()}</p>"
                "<p>Content is read from disk. Network access from "
                "file:// pages is disabled by default.</p>"
            )
        else:
            title = f"Page {scheme or 'unknown'}"
            body = (
                f"<p><b>Scheme:</b> {scheme or '(none)'}</p>"
                f"<p><b>URL:</b> {qurl.toString()}</p>"
            )

        QMessageBox.information(self, title, body)

    # ── Bookmark ───────────────────────────────────────────────────
    def _refresh_star(self) -> None:
        view = self.current_view()
        if view is None:
            return
        url = view.url().toString()
        theme = THEMES.get(self.store.settings.get("theme", "dark"), THEMES["dark"])
        marked = self.store.is_bookmarked(url)
        svg = SVG_STAR_FILLED if marked else SVG_STAR_OUTLINE
        self.star_action.setIcon(
            icon_from_svg(svg, color=theme["accent"] if marked else theme["text"], size=24)
        )

    def toggle_bookmark(self) -> None:
        view = self.current_view()
        if view is None:
            return
        url = view.url().toString()
        if not url or url.startswith("frame://"):
            return
        added = self.store.toggle_bookmark(view.title(), url)
        self._refresh_star()
        self.toast.show_message(
            "Bookmark added" if added else "Bookmark removed",
            key="bookmark",
            duration_ms=2000,
        )
        if self._bookmarks_dlg is not None and self._bookmarks_dlg.isVisible():
            self._bookmarks_dlg.refresh()

    def toggle_bookmark_bar(self) -> None:
        if self.bookmark_bar is None:
            return
        visible = not self.bookmark_bar._user_wants_visible
        self.bookmark_bar.set_user_visible(visible)
        self.store.settings["show_bookmark_bar"] = visible
        self.store.save()

    # ── Tab context menu ───────────────────────────────────────────
    def _tab_context_menu(self, pos) -> None:
        idx = self.tabs.tabBar().tabAt(pos)
        if idx < 0:
            return

        tab = self.tabs.widget(idx)
        url = tab.view.url().toString() if tab else ""
        susp = self.suspend_mgr.is_suspended(tab)
        pinned = self.suspend_mgr.is_pinned(tab)
        wl = self.suspend_mgr.is_whitelisted(url)

        menu = QMenu(self)
        act_reload = menu.addAction("Reload")
        act_dup = menu.addAction("Duplicate tab")
        act_pin = menu.addAction("Unpin tab" if pinned else "Pin tab")

        act_susp = menu.addAction("Wake tab" if susp else "Sleep tab")

        if url.startswith("http"):
            act_wl = menu.addAction(
                "Remove from whitelist" if wl
                else "Add to whitelist (anti-suspend)"
            )
        else:
            act_wl = None

        menu.addSeparator()
        act_close = menu.addAction("Close tab")
        act_close_others = menu.addAction("Close other tabs")
        act_close_right = menu.addAction("Close tabs to the right")
        menu.addSeparator()
        act_reopen = menu.addAction("Reopen closed tab")
        act_reopen.setEnabled(bool(self.closed_tabs))

        chosen = menu.exec(self.tabs.tabBar().mapToGlobal(pos))
        if chosen is None:
            return
        if chosen is act_reload:
            tab.view.reload()
        elif chosen is act_dup:
            self.duplicate_tab(idx)
        elif chosen is act_pin:
            self.toggle_pin(idx)
        elif chosen is act_susp:
            if susp:
                self._unsuspend_tab(idx)
            else:
                self._suspend_tab(idx, manual=True)
        elif act_wl is not None and chosen is act_wl:
            added, host = self.suspend_mgr.toggle_whitelist(url)
            if host:
                action = ("Added to whitelist" if added
                          else "Removed from whitelist")
                self.toast.show_message(f"{action}: {host}", key="whitelist")
        elif chosen is act_close:
            self.close_tab(idx)
        elif chosen is act_close_others:
            self.close_other_tabs(idx)
        elif chosen is act_close_right:
            self.close_tabs_to_right(idx)
        elif chosen is act_reopen:
            self.reopen_last_tab()

    def duplicate_tab(self, idx: int) -> None:
        tab = self.tabs.widget(idx)
        if tab is None:
            return
        susp_url = self.suspend_mgr.suspended_url(tab)
        url = QUrl(susp_url) if susp_url else tab.view.url()
        self.add_new_tab(url, "New Tab", switch=True)

    def toggle_pin(self, idx: int) -> None:
        tab = self.tabs.widget(idx)
        if tab is None:
            return
        bar = self.tabs.tabBar()
        if self.suspend_mgr.is_pinned(tab):
            self.suspend_mgr.unpin(tab)
            bar.setTabButton(idx, QTabBar.ButtonPosition.RightSide, None)
            self._install_tab_close_button(idx)
        else:
            self.suspend_mgr.pin(tab)
            bar.setTabButton(idx, QTabBar.ButtonPosition.RightSide, None)
            bar.moveTab(idx, 0)
        self.update_tab_title(tab)

    def close_other_tabs(self, keep_idx: int) -> None:
        keep = self.tabs.widget(keep_idx)
        for i in reversed(range(self.tabs.count())):
            if self.tabs.widget(i) is not keep:
                self._forget_tab(self.tabs.widget(i))
                self.tabs.removeTab(i)

    def close_tabs_to_right(self, idx: int) -> None:
        for i in reversed(range(idx + 1, self.tabs.count())):
            self._forget_tab(self.tabs.widget(i))
            self.tabs.removeTab(i)

    # ── Dialogs ────────────────────────────────────────────────────
    def show_bookmarks(self) -> None:
        if self._bookmarks_dlg is None:
            self._bookmarks_dlg = BookmarksDialog(self.store, self)
            self._bookmarks_dlg.open_requested.connect(self.open_url_in_current)
        else:
            self._bookmarks_dlg.refresh()
        self._bookmarks_dlg.show(); self._bookmarks_dlg.raise_()
        self._bookmarks_dlg.activateWindow()

    def show_history(self) -> None:
        if self._history_dlg is None:
            self._history_dlg = HistoryDialog(self.store, self)
            self._history_dlg.open_requested.connect(self.open_url_in_current)
        else:
            self._history_dlg.refresh()
        self._history_dlg.show(); self._history_dlg.raise_()
        self._history_dlg.activateWindow()

    def show_downloads(self) -> None:
        if self._downloads_dlg is None:
            self._downloads_dlg = DownloadsDialog(self)
        self._downloads_dlg.show(); self._downloads_dlg.raise_()
        self._downloads_dlg.activateWindow()

    def show_settings(self) -> None:
        if self._settings_dlg is None:
            self._settings_dlg = SettingsDialog(self.store, self.profile, self)
            self._settings_dlg.settings_saved.connect(self._apply_settings)
        self._settings_dlg.show(); self._settings_dlg.raise_()
        self._settings_dlg.activateWindow()

    def _apply_settings(self) -> None:
        theme_name = self.store.settings.get("theme", "dark")
        apply_theme(theme_name)

        if hasattr(self, "glow"):
            self.glow.refresh_theme()
            self.glow.set_glow_width(
                self.store.settings.get("window_glow_width", 1)
            )
            self.glow.set_light_style(
                self.store.settings.get("window_glow_light_style", "solid")
            )
            self.glow.set_light_rgb_params(
                self.store.settings.get("window_glow_light_sat", 0.95),
                self.store.settings.get("window_glow_light_lightness", 0.32),
            )
            self.glow.set_taper_ratio(
                self.store.settings.get("window_glow_taper", 0.4)
            )

        self.toast.show_message(
            "Settings saved", key="settings", duration_ms=2000
        )
        if self.bookmark_bar is not None:
            self.bookmark_bar.set_user_visible(
                self.store.settings.get("show_bookmark_bar", True)
            )
            self.bookmark_bar.refresh()
        self.adblocker.enabled = self.store.settings.get("adblock_enabled", True)

        if self.store.settings.get("auto_suspend_tabs", False):
            self._suspend_timer.start()
        else:
            self._suspend_timer.stop()

        self._rebuild_icons()

    def _rebuild_icons(self) -> None:
        parent_layout = self.glow.content_layout()
        parent_layout.removeWidget(self.navtb)
        self.navtb.deleteLater()
        self._build_toolbar()
        parent_layout.insertWidget(1, self.navtb)
        self._refresh_star()
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if tab and not self.suspend_mgr.is_pinned(tab):
                self._install_tab_close_button(i)
        view = self.current_view()
        if view is not None:
            self._update_security_indicator(view.url())

    def open_url_in_current(self, qurl: QUrl) -> None:
        s = qurl.toString()
        if not is_safe_url(s):
            self.toast.show_message(
                tr("url.blocked", url=s[:80]), key="url", duration_ms=4000
            )
            return
        view = self.current_view()
        if view:
            view.setUrl(qurl)
        self.raise_(); self.activateWindow()

    def show_find(self) -> None:
        view = self.current_view()
        if view:
            self.findbar.open_bar(view)

    # ── Downloads ──────────────────────────────────────────────────
    def handle_download(self, download) -> None:
        dl_dir = self.store.settings.get("download_dir") or str(
            Path.home() / "Downloads"
        )
        try:
            Path(dl_dir).mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            log.warning("Cannot create download folder (%s): %s", dl_dir, exc)
            dl_dir = str(Path.home())
        download.setDownloadDirectory(dl_dir)
        download.accept()

        self.download_shelf.add_download(download)

        if self._downloads_dlg is None:
            self._downloads_dlg = DownloadsDialog(self)
        self._downloads_dlg.add_download(download, show=False)

    # ── Zoom / Fullscreen / Private ────────────────────────────────
    def zoom_in(self) -> None:
        view = self.current_view()
        if view:
            view.setZoomFactor(min(5.0, round(view.zoomFactor() + 0.1, 2)))
            self.toast.show_message(
                f"Zoom {int(view.zoomFactor() * 100)}%",
                key="zoom", duration_ms=1200,
            )

    def zoom_out(self) -> None:
        view = self.current_view()
        if view:
            view.setZoomFactor(max(0.25, round(view.zoomFactor() - 0.1, 2)))
            self.toast.show_message(
                f"Zoom {int(view.zoomFactor() * 100)}%",
                key="zoom", duration_ms=1200,
            )

    def zoom_reset(self) -> None:
        view = self.current_view()
        if view:
            view.setZoomFactor(1.0)
            self.toast.show_message(
                "Zoom 100%", key="zoom", duration_ms=1200
            )

    def toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
            self.title_bar.show()
            self.glow.set_mode(
                self.store.settings.get("window_glow", "rgb")
            )
        else:
            self.showFullScreen()
            self.title_bar.hide()
            self.glow.set_mode("off")

    def open_private_window(self) -> None:
        from .private_window import PrivateWindow
        MainWindow._private_windows = [
            w for w in MainWindow._private_windows if w.isVisible()
        ]
        win = PrivateWindow()
        MainWindow._private_windows.append(win)
        win.show()

    # ── Close ──────────────────────────────────────────────────────
    def closeEvent(self, event) -> None:
        try:
            self.download_shelf._auto_hide.stop()
        except (RuntimeError, AttributeError) as exc:
            log.debug("auto_hide.stop: %s", exc)
        try:
            self._suspend_timer.stop()
        except RuntimeError as exc:
            log.debug("suspend_timer.stop: %s", exc)

        # Stop semua spinner yang masih jalan.
        for spinner in list(self._tab_spinners.values()):
            try:
                spinner.stop()
            except RuntimeError:
                pass
        self._tab_spinners.clear()

        if not self._private:
            urls = []
            for i in range(self.tabs.count()):
                t = self.tabs.widget(i)
                if t is None:
                    continue
                susp_url = self.suspend_mgr.suspended_url(t)
                if susp_url:
                    urls.append(susp_url)
                    continue
                u = t.view.url().toString()
                if u and u != "about:blank":
                    urls.append(u)
            self.store.session = urls

            if self.store.settings.get("clear_on_exit", False):
                try:
                    self.profile.clearHttpCache()
                    self.profile.cookieStore().deleteAllCookies()
                except (RuntimeError, AttributeError) as exc:
                    log.warning("Failed to clear data on exit: %s", exc)
                self.store.history.clear()

            self.store.flush()
        event.accept()