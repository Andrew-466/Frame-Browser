"""Tests for SuspendManager — including async JS dirty-check & race-safety.

Categories:
  A. Whitelist / toggle
  B. Pin / forget
  C. `_tab_alive` — tab object validation
  D. `_has_unsaved_form` — direct JS bridge test (incl. fail-safe None)
  E. `suspend_tab` / `_do_suspend_tab` — edge cases + rollback
  F. `check_dirty_and_suspend` — happy path + fail-safe
  G. Race scenarios — tab state changes while JS is running
  H. `idle_tabs` / `suspendable_now`
"""
from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest
from PyQt6.QtCore import QPoint, QUrl
from PyQt6.QtWidgets import QTabWidget, QWidget

from frame.suspend_manager import SuspendManager


# ══════════════════════════════════════════════════════════════════════
#  Fake objects
# ══════════════════════════════════════════════════════════════════════
class FakePage:
    """Mock QWebEnginePage — runJavaScript is configurable."""

    def __init__(self) -> None:
        self._scroll_y = 0
        self.js_result = False
        self.js_calls: list[str] = []
        self.js_override = None   # callable(script, callback)
        self.js_raise = None      # exception class to simulate error

    def scrollPosition(self):  # noqa: N802 (Qt naming)
        return QPoint(0, self._scroll_y)

    def runJavaScript(self, script, callback):  # noqa: N802
        self.js_calls.append(script)
        if self.js_raise is not None:
            raise self.js_raise("js bridge down")
        if self.js_override is not None:
            self.js_override(script, callback)
        else:
            callback(self.js_result)


class FakeView:
    def __init__(self, url: str = "https://example.com", title: str = "Ex") -> None:
        self._url = QUrl(url)
        self._title = title
        self.page_obj = FakePage()
        self.setUrl_calls: list[QUrl] = []
        self.setUrl_raise: Exception | None = None

    def url(self) -> QUrl:
        return self._url

    def title(self) -> str:
        return self._title

    def setUrl(self, qurl: QUrl) -> None:  # noqa: N802
        if self.setUrl_raise is not None:
            raise self.setUrl_raise
        self.setUrl_calls.append(qurl)
        self._url = qurl

    def page(self):
        return self.page_obj


class FakeTab(QWidget):
    def __init__(self, url: str = "https://example.com", title: str = "Ex") -> None:
        super().__init__()
        self.view = FakeView(url, title)


# ══════════════════════════════════════════════════════════════════════
#  Fixtures
# ══════════════════════════════════════════════════════════════════════
@pytest.fixture
def fake_store():
    store = MagicMock()
    store.settings = {
        "restore_scroll": True,
        "suspend_whitelist": ["mail.google.com", "docs.google.com"],
        "suspend_skip_dirty_form": True,
    }
    return store


@pytest.fixture
def tabs_and_mgr(fake_store):
    tabs = QTabWidget()
    mgr = SuspendManager(tabs, fake_store)
    yield tabs, mgr
    for i in reversed(range(tabs.count())):
        tabs.removeTab(i)


def _two_tabs(tabs, target_url: str = "https://example.com/x"):
    """Two tabs: current = 'Other', target = URL. Return (current, target)."""
    t_current = FakeTab(url="https://other.com")
    t_target = FakeTab(url=target_url)
    tabs.addTab(t_current, "Other")
    tabs.addTab(t_target, "Target")
    tabs.setCurrentIndex(0)
    return t_current, t_target


# ══════════════════════════════════════════════════════════════════════
#  A. Whitelist
# ══════════════════════════════════════════════════════════════════════
def test_whitelist_exact_host(tabs_and_mgr):
    _, mgr = tabs_and_mgr
    assert mgr.is_whitelisted("https://mail.google.com/inbox") is True


def test_whitelist_subdomain(tabs_and_mgr):
    _, mgr = tabs_and_mgr
    assert mgr.is_whitelisted("https://sub.mail.google.com/") is True


def test_whitelist_suffix_attack_rejected(tabs_and_mgr):
    _, mgr = tabs_and_mgr
    assert mgr.is_whitelisted("https://mail.google.com.evil.com/") is False


def test_whitelist_with_port(tabs_and_mgr):
    _, mgr = tabs_and_mgr
    assert mgr.is_whitelisted("https://mail.google.com:8443/x") is True


def test_whitelist_unrelated(tabs_and_mgr):
    _, mgr = tabs_and_mgr
    assert mgr.is_whitelisted("https://example.com/") is False


def test_whitelist_empty_url(tabs_and_mgr):
    _, mgr = tabs_and_mgr
    assert mgr.is_whitelisted("") is False


def test_toggle_whitelist_add(tabs_and_mgr):
    _, mgr = tabs_and_mgr
    added, host = mgr.toggle_whitelist("https://new.example.com/x")
    assert added is True
    assert host == "new.example.com"
    assert "new.example.com" in mgr.store.settings["suspend_whitelist"]


def test_toggle_whitelist_remove(tabs_and_mgr):
    _, mgr = tabs_and_mgr
    added, host = mgr.toggle_whitelist("https://mail.google.com/")
    assert added is False
    assert host == "mail.google.com"
    assert "mail.google.com" not in mgr.store.settings["suspend_whitelist"]


# ══════════════════════════════════════════════════════════════════════
#  B. Pin / forget
# ══════════════════════════════════════════════════════════════════════
def test_pin_and_unpin(tabs_and_mgr):
    _, mgr = tabs_and_mgr
    tab = FakeTab()
    assert mgr.is_pinned(tab) is False
    mgr.pin(tab)
    assert mgr.is_pinned(tab) is True
    mgr.unpin(tab)
    assert mgr.is_pinned(tab) is False


def test_forget_clears_pin(tabs_and_mgr):
    _, mgr = tabs_and_mgr
    tab = FakeTab()
    mgr.pin(tab)
    mgr.forget(tab)
    assert mgr.is_pinned(tab) is False


def test_forget_clears_suspended_state(tabs_and_mgr):
    tabs, mgr = tabs_and_mgr
    _, target = _two_tabs(tabs)
    mgr.suspend_tab(target, manual=True)
    assert mgr.is_suspended(target) is True
    mgr.forget(target)
    assert mgr.is_suspended(target) is False


# ══════════════════════════════════════════════════════════════════════
#  C. `_tab_alive` — tab object validation
# ══════════════════════════════════════════════════════════════════════
def test_tab_alive_true_for_registered(tabs_and_mgr):
    tabs, mgr = tabs_and_mgr
    tab = FakeTab()
    tabs.addTab(tab, "X")
    assert mgr._tab_alive(tab) is True


def test_tab_alive_false_for_unregistered(tabs_and_mgr):
    _, mgr = tabs_and_mgr
    tab = FakeTab()
    assert mgr._tab_alive(tab) is False


def test_tab_alive_false_for_none(tabs_and_mgr):
    _, mgr = tabs_and_mgr
    assert mgr._tab_alive(None) is False


def test_tab_alive_false_after_removed(tabs_and_mgr):
    tabs, mgr = tabs_and_mgr
    tab = FakeTab()
    tabs.addTab(tab, "X")
    tabs.removeTab(0)
    assert mgr._tab_alive(tab) is False


# ══════════════════════════════════════════════════════════════════════
#  D. `_has_unsaved_form` — JS bridge (incl. fail-safe None)
# ══════════════════════════════════════════════════════════════════════
def test_has_unsaved_form_passes_dirty_true(tabs_and_mgr):
    tabs, mgr = tabs_and_mgr
    _, target = _two_tabs(tabs)
    target.view.page_obj.js_result = True

    results = []
    mgr._has_unsaved_form(target, lambda d: results.append(d))
    assert results == [True]
    assert len(target.view.page_obj.js_calls) == 1


def test_has_unsaved_form_passes_dirty_false(tabs_and_mgr):
    tabs, mgr = tabs_and_mgr
    _, target = _two_tabs(tabs)
    target.view.page_obj.js_result = False

    results = []
    mgr._has_unsaved_form(target, lambda d: results.append(d))
    assert results == [False]


def test_has_unsaved_form_none_tab_yields_none(tabs_and_mgr):
    """Tab None → callback(None) — not False, since status is unknown."""
    _, mgr = tabs_and_mgr
    results = []
    mgr._has_unsaved_form(None, lambda d: results.append(d))
    assert results == [None]


def test_has_unsaved_form_js_exception_yields_none(tabs_and_mgr, caplog):
    """JS bridge error → callback(None) — fail-safe, not False."""
    tabs, mgr = tabs_and_mgr
    _, target = _two_tabs(tabs)
    target.view.page_obj.js_raise = RuntimeError

    results = []
    with caplog.at_level(logging.DEBUG, logger="frame"):
        mgr._has_unsaved_form(target, lambda d: results.append(d))

    assert results == [None]
    assert any(
        "runJavaScript form-dirty failed" in r.message
        for r in caplog.records
    )


# ══════════════════════════════════════════════════════════════════════
#  E. `suspend_tab` / `_do_suspend_tab` — edge cases & rollback
# ══════════════════════════════════════════════════════════════════════
def test_suspend_tab_by_reference(tabs_and_mgr):
    tabs, mgr = tabs_and_mgr
    _, target = _two_tabs(tabs)
    res = mgr.suspend_tab(target, manual=True)
    assert res is not None
    assert mgr.is_suspended(target) is True


def test_suspend_tab_after_reorder(tabs_and_mgr):
    tabs, mgr = tabs_and_mgr
    t0 = FakeTab(url="https://a.com")
    t1 = FakeTab(url="https://b.com")
    tabs.addTab(t0, "A")
    tabs.addTab(t1, "B")
    tabs.setCurrentIndex(0)
    tabs.tabBar().moveTab(1, 0)

    res = mgr.suspend_tab(t1, manual=True)
    assert res is not None
    assert res[0] == "https://b.com"
    assert mgr.is_suspended(t1) is True
    assert mgr.is_suspended(t0) is False


def test_suspend_tab_dead_tab_returns_none(tabs_and_mgr):
    _, mgr = tabs_and_mgr
    orphan = FakeTab()
    assert mgr.suspend_tab(orphan, manual=True) is None
    assert mgr.is_suspended(orphan) is False


def test_suspend_tab_rollback_if_seturl_fails(tabs_and_mgr):
    tabs, mgr = tabs_and_mgr
    _, target = _two_tabs(tabs)
    target.view.setUrl_raise = RuntimeError("C++ object deleted")

    res = mgr.suspend_tab(target, manual=True)
    assert res is None
    assert mgr.is_suspended(target) is False
    assert mgr.suspended_url(target) is None


def test_suspend_idx_compat_still_works(tabs_and_mgr):
    tabs, mgr = tabs_and_mgr
    _, target = _two_tabs(tabs)
    assert mgr.suspend(1, manual=True) is not None
    assert mgr.is_suspended(target) is True


def test_suspend_idx_out_of_range_returns_none(tabs_and_mgr):
    _, mgr = tabs_and_mgr
    assert mgr.suspend(999, manual=True) is None


# ══════════════════════════════════════════════════════════════════════
#  F. `check_dirty_and_suspend` — happy path + fail-safe
# ══════════════════════════════════════════════════════════════════════
def test_check_dirty_suspends_when_clean(tabs_and_mgr):
    tabs, mgr = tabs_and_mgr
    _, target = _two_tabs(tabs)
    target.view.page_obj.js_result = False

    results = []
    mgr.check_dirty_and_suspend(target, on_done=lambda ok, d: results.append((ok, d)))

    assert len(results) == 1
    ok, data = results[0]
    assert ok is True
    assert data is not None
    assert data[0] == "https://example.com/x"
    assert mgr.is_suspended(target) is True
    assert len(target.view.page_obj.js_calls) == 1


def test_check_dirty_skips_when_dirty(tabs_and_mgr):
    tabs, mgr = tabs_and_mgr
    _, target = _two_tabs(tabs)
    target.view.page_obj.js_result = True

    results = []
    mgr.check_dirty_and_suspend(target, on_done=lambda ok, d: results.append((ok, d)))

    assert results == [(False, None)]
    assert mgr.is_suspended(target) is False
    assert target.view.setUrl_calls == []


def test_check_dirty_setting_disabled_skips_js(tabs_and_mgr, fake_store):
    tabs, mgr = tabs_and_mgr
    _, target = _two_tabs(tabs)
    fake_store.settings["suspend_skip_dirty_form"] = False

    results = []
    mgr.check_dirty_and_suspend(target, on_done=lambda ok, d: results.append((ok, d)))

    assert results[0][0] is True
    assert mgr.is_suspended(target) is True
    assert target.view.page_obj.js_calls == []


def test_check_dirty_rejects_current_tab(tabs_and_mgr):
    tabs, mgr = tabs_and_mgr
    tab = FakeTab(url="https://example.com/x")
    tabs.addTab(tab, "Ex")
    tabs.setCurrentIndex(0)

    results = []
    mgr.check_dirty_and_suspend(tab, on_done=lambda ok, d: results.append((ok, d)))

    assert results == [(False, None)]
    assert mgr.is_suspended(tab) is False
    assert tab.view.page_obj.js_calls == []


def test_check_dirty_rejects_dead_tab(tabs_and_mgr):
    _, mgr = tabs_and_mgr
    orphan = FakeTab()

    results = []
    mgr.check_dirty_and_suspend(orphan, on_done=lambda ok, d: results.append((ok, d)))

    assert results == [(False, None)]
    assert orphan.view.page_obj.js_calls == []


def test_check_dirty_rejects_whitelisted(tabs_and_mgr):
    tabs, mgr = tabs_and_mgr
    t_cur = FakeTab(url="https://other.com")
    t_wl = FakeTab(url="https://mail.google.com/x")
    tabs.addTab(t_cur, "Cur")
    tabs.addTab(t_wl, "Wl")
    tabs.setCurrentIndex(0)

    results = []
    mgr.check_dirty_and_suspend(t_wl, on_done=lambda ok, d: results.append((ok, d)))

    assert results == [(False, None)]
    assert t_wl.view.page_obj.js_calls == []


def test_check_dirty_always_calls_callback(tabs_and_mgr):
    tabs, mgr = tabs_and_mgr
    _, target = _two_tabs(tabs)
    calls = []
    mgr.check_dirty_and_suspend(target, on_done=lambda ok, d: calls.append(1))
    assert len(calls) == 1


def test_check_dirty_works_without_callback(tabs_and_mgr):
    tabs, mgr = tabs_and_mgr
    _, target = _two_tabs(tabs)
    mgr.check_dirty_and_suspend(target)
    assert mgr.is_suspended(target) is True


def test_check_dirty_failsafe_when_js_unavailable(tabs_and_mgr, caplog):
    """Fail-safe: JS bridge error → skip suspend, do not sleep tab."""
    tabs, mgr = tabs_and_mgr
    _, target = _two_tabs(tabs)
    target.view.page_obj.js_raise = RuntimeError

    results = []
    with caplog.at_level(logging.DEBUG, logger="frame"):
        mgr.check_dirty_and_suspend(
            target, on_done=lambda ok, d: results.append((ok, d))
        )

    assert results == [(False, None)]
    assert mgr.is_suspended(target) is False
    assert target.view.setUrl_calls == []
    assert any(
        "form-dirty status unverifiable" in r.message
        for r in caplog.records
    )


# ══════════════════════════════════════════════════════════════════════
#  G. Race scenarios — tab state changes while JS is running
# ══════════════════════════════════════════════════════════════════════
def test_race_aborts_if_tab_closed_during_js(tabs_and_mgr):
    tabs, mgr = tabs_and_mgr
    _, target = _two_tabs(tabs)

    def close_then_callback(script, callback):
        idx = tabs.indexOf(target)
        if idx >= 0:
            tabs.removeTab(idx)
        callback(False)

    target.view.page_obj.js_override = close_then_callback

    results = []
    mgr.check_dirty_and_suspend(target, on_done=lambda ok, d: results.append((ok, d)))

    assert results == [(False, None)]
    assert mgr.is_suspended(target) is False


def test_race_aborts_if_tab_becomes_current(tabs_and_mgr):
    tabs, mgr = tabs_and_mgr
    _, target = _two_tabs(tabs)

    def make_current_then_callback(script, callback):
        idx = tabs.indexOf(target)
        if idx >= 0:
            tabs.setCurrentIndex(idx)
        callback(False)

    target.view.page_obj.js_override = make_current_then_callback

    results = []
    mgr.check_dirty_and_suspend(target, on_done=lambda ok, d: results.append((ok, d)))

    assert results == [(False, None)]
    assert mgr.is_suspended(target) is False


def test_race_aborts_if_tab_becomes_whitelisted(tabs_and_mgr, fake_store):
    tabs, mgr = tabs_and_mgr
    _, target = _two_tabs(tabs)

    def whitelist_then_callback(script, callback):
        fake_store.settings["suspend_whitelist"].append("example.com")
        callback(False)

    target.view.page_obj.js_override = whitelist_then_callback

    results = []
    mgr.check_dirty_and_suspend(target, on_done=lambda ok, d: results.append((ok, d)))

    assert results == [(False, None)]
    assert mgr.is_suspended(target) is False


def test_race_aborts_if_tab_becomes_pinned(tabs_and_mgr):
    tabs, mgr = tabs_and_mgr
    _, target = _two_tabs(tabs)

    def pin_then_callback(script, callback):
        mgr.pin(target)
        callback(False)

    target.view.page_obj.js_override = pin_then_callback

    results = []
    mgr.check_dirty_and_suspend(target, on_done=lambda ok, d: results.append((ok, d)))

    assert results == [(False, None)]
    assert mgr.is_suspended(target) is False


def test_race_aborts_if_already_suspended(tabs_and_mgr):
    tabs, mgr = tabs_and_mgr
    _, target = _two_tabs(tabs)

    def suspend_then_callback(script, callback):
        mgr.suspend_tab(target, manual=True)
        callback(False)

    target.view.page_obj.js_override = suspend_then_callback

    results = []
    mgr.check_dirty_and_suspend(target, on_done=lambda ok, d: results.append((ok, d)))

    assert results == [(False, None)]
    assert mgr.is_suspended(target) is True
    assert len(target.view.setUrl_calls) == 1


def test_race_reordered_tab_target_correct(tabs_and_mgr):
    tabs, mgr = tabs_and_mgr
    t_cur, target = _two_tabs(tabs)

    def reorder_then_callback(script, callback):
        idx = tabs.indexOf(target)
        if idx > 0:
            tabs.tabBar().moveTab(idx, 0)
        callback(False)

    target.view.page_obj.js_override = reorder_then_callback

    results = []
    mgr.check_dirty_and_suspend(target, on_done=lambda ok, d: results.append((ok, d)))

    assert results[0][0] is True
    assert mgr.is_suspended(target) is True
    assert mgr.is_suspended(t_cur) is False


def test_race_js_raises_during_check_aborts(tabs_and_mgr, caplog):
    """JS bridge error → fail-safe skip, not suspend."""
    tabs, mgr = tabs_and_mgr
    _, target = _two_tabs(tabs)
    target.view.page_obj.js_raise = RuntimeError

    results = []
    with caplog.at_level(logging.DEBUG, logger="frame"):
        mgr.check_dirty_and_suspend(
            target, on_done=lambda ok, d: results.append((ok, d))
        )

    assert results == [(False, None)]
    assert mgr.is_suspended(target) is False


def test_race_multiple_pending_checks_same_tab(tabs_and_mgr):
    """Two auto-suspends for the same tab (overlapping timers)."""
    tabs, mgr = tabs_and_mgr
    _, target = _two_tabs(tabs)

    callbacks = []

    def slow_callback(script, cb):
        callbacks.append(cb)

    target.view.page_obj.js_override = slow_callback

    results_1, results_2 = [], []
    mgr.check_dirty_and_suspend(target, on_done=lambda ok, d: results_1.append((ok, d)))
    mgr.check_dirty_and_suspend(target, on_done=lambda ok, d: results_2.append((ok, d)))

    assert len(callbacks) == 2
    callbacks[0](False)
    callbacks[1](False)

    assert results_1[0][0] is True
    assert results_2 == [(False, None)]
    assert mgr.is_suspended(target) is True
    assert len(target.view.setUrl_calls) == 1


def test_race_callback_called_once_per_invocation(tabs_and_mgr):
    tabs, mgr = tabs_and_mgr
    _, target = _two_tabs(tabs)

    counter = {"n": 0}
    def cb(ok, d):
        counter["n"] += 1

    mgr.check_dirty_and_suspend(target, on_done=cb)
    assert counter["n"] == 1

    mgr.check_dirty_and_suspend(target, on_done=cb)
    assert counter["n"] == 2


# ══════════════════════════════════════════════════════════════════════
#  H. idle_tabs / suspendable_now / suspendable
# ══════════════════════════════════════════════════════════════════════
def test_idle_tabs_skips_current(tabs_and_mgr):
    tabs, mgr = tabs_and_mgr
    for i in range(3):
        tabs.addTab(FakeTab(url=f"https://s{i}.com"), f"T{i}")
    tabs.setCurrentIndex(1)
    for i in range(3):
        mgr.touch(tabs.widget(i))

    assert mgr.idle_tabs(3600) == []

    idle = mgr.idle_tabs(0)
    assert tabs.widget(1) not in idle
    assert len(idle) == 2


def test_idle_tabs_skips_pinned_and_whitelisted(tabs_and_mgr):
    tabs, mgr = tabs_and_mgr
    t0 = FakeTab(url="https://a.com")
    t1 = FakeTab(url="https://mail.google.com/x")
    t2 = FakeTab(url="https://b.com")
    tabs.addTab(t0, "A")
    tabs.addTab(t1, "Mail")
    tabs.addTab(t2, "B")
    tabs.setCurrentIndex(0)
    mgr.pin(t2)
    for i in range(3):
        mgr.touch(tabs.widget(i))

    assert mgr.idle_tabs(0) == []


def test_idle_tabs_returns_objects_not_indices(tabs_and_mgr):
    tabs, mgr = tabs_and_mgr
    t_cur = FakeTab(url="https://cur.com")
    t_idle = FakeTab(url="https://idle.com")
    tabs.addTab(t_cur, "Cur")
    tabs.addTab(t_idle, "Idle")
    tabs.setCurrentIndex(0)
    mgr.touch(t_cur)
    mgr.touch(t_idle)

    idle = mgr.idle_tabs(0)
    assert len(idle) == 1
    assert idle[0] is t_idle


def test_suspendable_now_counts_skipped(tabs_and_mgr):
    tabs, mgr = tabs_and_mgr
    t0 = FakeTab(url="https://a.com")
    t1 = FakeTab(url="https://mail.google.com/x")
    t2 = FakeTab(url="https://b.com")
    t3 = FakeTab(url="https://c.com")
    for t, name in [(t0, "A"), (t1, "M"), (t2, "B"), (t3, "C")]:
        tabs.addTab(t, name)
    tabs.setCurrentIndex(0)
    mgr.pin(t2)

    indices, skipped = mgr.suspendable_now()
    assert skipped == 2
    assert set(indices) == {3}