"""Tab suspend/resume + pin + whitelist + form-dirty detection."""
from __future__ import annotations

import time
from collections.abc import Callable
from urllib.parse import urlparse
from weakref import WeakKeyDictionary, WeakSet

from PyQt6.QtCore import QUrl
from PyQt6.QtWidgets import QTabWidget

from .core import log
from .store import Store


# JS that returns true if any input/textarea/select has a value different
# from its default (dirty). Wrapped in try/catch so pages that block DOM
# access stay safe (return false).
_FORM_DIRTY_JS = r"""
(function(){
    try {
        var inputs = document.querySelectorAll('input, textarea, select');
        for (var i = 0; i < inputs.length; i++) {
            var el = inputs[i];
            var t = (el.type || '').toLowerCase();
            if (t === 'hidden' || t === 'submit' ||
                t === 'button' || t === 'reset') continue;
            if (t === 'checkbox' || t === 'radio') {
                if (el.checked !== el.defaultChecked) return true;
            } else if (el.tagName === 'SELECT') {
                for (var j = 0; j < el.options.length; j++) {
                    if (el.options[j].selected !== el.options[j].defaultSelected)
                        return true;
                }
            } else {
                if (el.value && el.value !== el.defaultValue) return true;
            }
        }
        return false;
    } catch (e) { return false; }
})();
"""


class SuspendManager:
    """Manages sleep/pin/whitelist state for tabs.

    Keys are the tab objects themselves inside WeakKeyDictionary/WeakSet,
    avoiding `id()` reuse bugs.

    The tab-based API (`suspend_tab`, `check_dirty_and_suspend`) accepts
    **tab objects**, not indices — safe against race conditions when the
    JS callback runs during auto-suspend.

    Form-dirty check is **fail-safe**: if the status cannot be verified
    (JS bridge error), the tab is **not** suspended. This prevents losing
    drafts when conditions are uncertain.
    """

    def __init__(self, tabs: QTabWidget, store: Store) -> None:
        self.tabs = tabs
        self.store = store
        self._suspended: WeakKeyDictionary = WeakKeyDictionary()
        self._last_active: WeakKeyDictionary = WeakKeyDictionary()
        self._pinned: WeakSet = WeakSet()

    # ── Query ───────────────────────────────────────────────────────
    def is_suspended(self, tab) -> bool:
        return tab is not None and tab in self._suspended

    def is_pinned(self, tab) -> bool:
        return tab is not None and tab in self._pinned

    def suspended_url(self, tab) -> str | None:
        if tab is None:
            return None
        data = self._suspended.get(tab)
        return data[0] if data else None

    def suspended_title(self, tab) -> str | None:
        if tab is None:
            return None
        data = self._suspended.get(tab)
        return data[1] if data else None

    def is_whitelisted(self, url: str) -> bool:
        try:
            host = urlparse(url).netloc.lower()
        except ValueError:
            return False
        if not host:
            return False
        if ":" in host:
            host = host.split(":", 1)[0]
        for entry in self.store.settings.get("suspend_whitelist", []):
            e = entry.lower().strip()
            if e and (host == e or host.endswith("." + e)):
                return True
        return False

    def _tab_alive(self, tab) -> bool:
        """True if the tab object is still valid and registered in QTabWidget."""
        if tab is None:
            return False
        try:
            return self.tabs.indexOf(tab) >= 0
        except RuntimeError:
            # C++ object already deleted (e.g. when window closed).
            return False

    # ── Tracking ────────────────────────────────────────────────────
    def touch(self, tab) -> None:
        if tab is not None:
            self._last_active[tab] = time.time()

    def forget(self, tab) -> None:
        if tab is None:
            return
        self._suspended.pop(tab, None)
        self._last_active.pop(tab, None)
        self._pinned.discard(tab)

    # ── Pin ─────────────────────────────────────────────────────────
    def pin(self, tab) -> None:
        if tab is not None:
            self._pinned.add(tab)

    def unpin(self, tab) -> None:
        if tab is not None:
            self._pinned.discard(tab)
    
        # ── Lazy preload (session restore) ──────────────────────────────
    def suspend_preload(self, tab, url: str, title: str) -> bool:
        """Register a tab as suspended WITHOUT ever loading its URL.

        Used for lazy session restore: the tab appears in the strip, but
        its URL is only fetched when the user clicks it. Different from
        `_do_suspend_tab`, which suspends a tab that had already loaded.

        Return True on success.
        """
        if not self._tab_alive(tab):
            return False
        try:
            tab.view.setUrl(QUrl("about:blank"))
        except RuntimeError:
            return False
        self._suspended[tab] = (url, title, None)
        return True

    # ── Whitelist ───────────────────────────────────────────────────
    def toggle_whitelist(self, url: str) -> tuple[bool, str]:
        try:
            host = urlparse(url).netloc.lower()
        except ValueError:
            return False, ""
        if ":" in host:
            host = host.split(":", 1)[0]
        if not host:
            return False, ""
        wl = self.store.settings.get("suspend_whitelist", [])
        if host in wl:
            wl.remove(host)
            added = False
        else:
            wl.append(host)
            added = True
        self.store.settings["suspend_whitelist"] = wl
        self.store.save()
        return added, host

    # ── Form-dirty detection ────────────────────────────────────────
    def _has_unsaved_form(
        self,
        tab,
        callback: Callable[[bool | None], None],
    ) -> None:
        """Async: callback(dirty), where dirty can be True/False/None.

        - True  = there is an unsubmitted form/input
        - False = page is clean (no forms / all values are defaults)
        - None  = **cannot be verified** (invalid tab, or JS bridge
                  error). Callers must treat None as "do not suspend" —
                  fail-safe to protect user data.
        """
        if tab is None:
            callback(None)
            return
        try:
            tab.view.page().runJavaScript(_FORM_DIRTY_JS, callback)
        except (AttributeError, RuntimeError) as exc:
            log.debug("runJavaScript form-dirty failed: %s", exc)
            callback(None)

    # ── Suspend / unsuspend ─────────────────────────────────────────
    def _can_suspend_tab(self, tab, *, manual: bool) -> bool:
        if not self._tab_alive(tab):
            return False
        if self.is_suspended(tab):
            return False
        if not manual and tab is self.tabs.currentWidget():
            return False
        url = tab.view.url().toString()
        if not url or url == "about:blank" or url.startswith("frame://"):
            return False
        if not manual and (self.is_whitelisted(url) or self.is_pinned(tab)):
            return False
        return True

    def _do_suspend_tab(self, tab) -> tuple[str, str, int | None] | None:
        """Suspend without additional checks. Returns (url, title, scroll_y)."""
        if not self._tab_alive(tab):
            return None
        url = tab.view.url().toString()
        title = tab.view.title() or "Tab"

        scroll_y: int | None = None
        if self.store.settings.get("restore_scroll", True):
            try:
                pos = tab.view.page().scrollPosition()
                scroll_y = int(pos.y()) if pos else None
            except (AttributeError, RuntimeError):
                scroll_y = None

        self._suspended[tab] = (url, title, scroll_y)
        try:
            tab.view.setUrl(QUrl("about:blank"))
        except RuntimeError:
            # Tab deleted between check and setUrl — roll back state.
            self._suspended.pop(tab, None)
            return None
        return url, title, scroll_y

    def suspend_tab(
        self, tab, *, manual: bool = False
    ) -> tuple[str, str, int | None] | None:
        """Suspend by tab reference — safe against reorder/close."""
        if not self._can_suspend_tab(tab, manual=manual):
            return None
        return self._do_suspend_tab(tab)

    def suspend(
        self, idx: int, *, manual: bool = False
    ) -> tuple[str, str, int | None] | None:
        """Compat: suspend by index. Looks up the tab, then delegates.

        Prefer `suspend_tab()` in new code — this API is kept for old
        tests and short-lived synchronous use.
        """
        tab = self.tabs.widget(idx)
        return self.suspend_tab(tab, manual=manual)

    def check_dirty_and_suspend(
        self,
        tab,
        on_done: Callable[[bool, tuple | None], None] | None = None,
    ) -> None:
        """Auto-suspend with form-dirty check.

        Accepts **tab objects**, not indices. The JS callback may run
        milliseconds to seconds after being invoked, and during that time
        the user could close / drag-reorder / pin / whitelist the tab.
        Holding the object reference ensures we always check the right tab.

        After the JS callback returns, we **re-verify**:
        - tab still exists in QTabWidget (if not → abort),
        - still passes `_can_suspend_tab` (user may have interacted),
        - form-dirty status is **not None** (JS bridge error → can't
          guarantee safety → skip, fail-safe).

        `on_done(suspended, data)` is always called exactly once.
        """
        if not self._can_suspend_tab(tab, manual=False):
            if on_done:
                on_done(False, None)
            return

        # If the skip-dirty feature is disabled, suspend directly without JS.
        if not self.store.settings.get("suspend_skip_dirty_form", True):
            res = self._do_suspend_tab(tab)
            if on_done:
                on_done(res is not None, res)
            return

        def _after_check(dirty: bool | None) -> None:
            # Race check 1: tab may have been closed during JS execution.
            if not self._tab_alive(tab):
                if on_done:
                    on_done(False, None)
                return
            # Race check 2: conditions may have changed during JS execution
            # (user returned to the tab, pinned, new whitelist entry, etc).
            if not self._can_suspend_tab(tab, manual=False):
                if on_done:
                    on_done(False, None)
                return
            # Fail-safe: if status cannot be verified, do not suspend.
            if dirty is None:
                log.debug(
                    "Skip auto-suspend: form-dirty status unverifiable"
                )
                if on_done:
                    on_done(False, None)
                return
            if dirty:
                log.debug("Skip auto-suspend: tab has an unsubmitted form")
                if on_done:
                    on_done(False, None)
                return
            res = self._do_suspend_tab(tab)
            if on_done:
                on_done(res is not None, res)

        self._has_unsaved_form(tab, _after_check)

    def unsuspend(self, idx: int) -> tuple[str, int | None] | None:
        tab = self.tabs.widget(idx)
        if tab is None:
            return None
        data = self._suspended.pop(tab, None)
        if data is None:
            return None
        url, _title, scroll_y = data
        tab.view.setUrl(QUrl(url))
        return url, scroll_y

    # ── Bulk idle ───────────────────────────────────────────────────
    def idle_tabs(self, timeout: float) -> list:
        """Tab objects (not indices) idle for more than `timeout` seconds."""
        cur = self.tabs.currentWidget()
        now = time.time()
        out: list = []
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if tab is None or tab is cur or self.is_suspended(tab):
                continue
            url = tab.view.url().toString()
            if self.is_whitelisted(url) or self.is_pinned(tab):
                continue
            if now - self._last_active.get(tab, now) > timeout:
                out.append(tab)
        return out

    def idle_indices(self, timeout: float) -> list[int]:
        """Compat: idle tab indices. Prefer `idle_tabs()`."""
        cur = self.tabs.currentWidget()
        now = time.time()
        out: list[int] = []
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if tab is None or tab is cur or self.is_suspended(tab):
                continue
            url = tab.view.url().toString()
            if self.is_whitelisted(url) or self.is_pinned(tab):
                continue
            if now - self._last_active.get(tab, now) > timeout:
                out.append(i)
        return out

    def suspendable_now(self) -> tuple[list[int], int]:
        """Tabs that can be suspended right now (for the synchronous menu action).

        Since the menu action is synchronous (no JS callback), index-based
        is safe.
        """
        cur = self.tabs.currentWidget()
        out: list[int] = []
        skipped = 0
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if tab is None or tab is cur or self.is_suspended(tab):
                continue
            url = tab.view.url().toString()
            if self.is_whitelisted(url) or self.is_pinned(tab):
                skipped += 1
                continue
            out.append(i)
        return out, skipped