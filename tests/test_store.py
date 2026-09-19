"""Uji Store — bookmark, riwayat (deque), top_sites, I/O JSON."""
from __future__ import annotations

import json
from collections import deque

import pytest


@pytest.fixture
def store(tmp_path, monkeypatch):
    """Store dengan data_dir diarahkan ke tmp_path."""
    monkeypatch.setattr("frame.store.data_dir", lambda: tmp_path)
    from frame.store import Store
    s = Store()
    yield s
    s._timer.stop()


# ── Riwayat ──────────────────────────────────────────────────────────
def test_history_is_deque_with_maxlen(store):
    from frame.store import Store
    assert isinstance(store.history, deque)
    assert store.history.maxlen == Store.MAX_HISTORY


def test_history_trimmed_at_maxlen(store):
    from frame.store import Store
    n = Store.MAX_HISTORY
    for i in range(n + 500):
        store.add_history(f"T{i}", f"https://e{i}.com")
    assert len(store.history) == n
    # Entri paling lama sudah terbuang
    assert store.history[0]["url"] == "https://e500.com"
    assert store.history[-1]["url"] == f"https://e{n + 499}.com"


def test_history_skips_internal_urls(store):
    store.add_history("New Tab", "frame://newtab")
    store.add_history("Blank", "about:blank")
    store.add_history("Empty", "")
    assert len(store.history) == 0


def test_history_respects_setting(store):
    store.settings["save_history"] = False
    store.add_history("X", "https://example.com")
    assert len(store.history) == 0


def test_clear_history(store):
    store.add_history("A", "https://a.com")
    assert len(store.history) == 1
    store.clear_history()
    assert len(store.history) == 0


# ── Bookmark ─────────────────────────────────────────────────────────
def test_bookmark_add_and_is_bookmarked(store):
    assert store.add_bookmark("Example", "https://example.com") is True
    assert store.is_bookmarked("https://example.com") is True


def test_bookmark_duplicate_rejected(store):
    store.add_bookmark("A", "https://a.com")
    assert store.add_bookmark("A lagi", "https://a.com") is False
    assert len(store.bookmarks) == 1


def test_bookmark_empty_url_rejected(store):
    assert store.add_bookmark("X", "") is False
    assert len(store.bookmarks) == 0


def test_bookmark_remove(store):
    store.add_bookmark("A", "https://a.com")
    assert store.remove_bookmark("https://a.com") is True
    assert store.remove_bookmark("https://a.com") is False


def test_bookmark_toggle(store):
    assert store.toggle_bookmark("A", "https://a.com") is True
    assert store.is_bookmarked("https://a.com")
    assert store.toggle_bookmark("A", "https://a.com") is False
    assert not store.is_bookmarked("https://a.com")


# ── top_sites ────────────────────────────────────────────────────────
def test_top_sites_ranking(store):
    for _ in range(3):
        store.add_history("A", "https://a.com")
    store.add_history("B", "https://b.com")
    store.add_history("B", "https://b.com")
    store.add_history("C", "https://c.com")

    top = store.top_sites(2)
    assert len(top) == 2
    assert top[0]["url"] == "https://a.com"
    assert top[0]["n"] == 3
    assert top[1]["url"] == "https://b.com"
    assert top[1]["n"] == 2


def test_top_sites_skips_non_http(store):
    store.add_history("F", "file:///tmp/a")
    store.add_history("Frame", "frame://newtab")
    store.add_history("H", "https://h.com")
    top = store.top_sites(10)
    assert [s["url"] for s in top] == ["https://h.com"]


def test_top_sites_uses_latest_title(store):
    store.add_history("Old Title", "https://a.com")
    store.add_history("New Title", "https://a.com")
    top = store.top_sites(1)
    assert top[0]["title"] == "New Title"


# ── I/O JSON ─────────────────────────────────────────────────────────
def test_flush_writes_json(store):
    store.add_bookmark("X", "https://x.com")
    store.add_history("Y", "https://y.com")
    store.flush()

    assert store.path.exists()
    raw = json.loads(store.path.read_text("utf-8"))
    assert raw["bookmarks"][0]["url"] == "https://x.com"
    assert isinstance(raw["history"], list)
    assert raw["history"][0]["url"] == "https://y.com"


def test_load_restores_deque(tmp_path, monkeypatch):
    data = {
        "bookmarks": [{"title": "B", "url": "https://b.com", "added": 0}],
        "history": [{"title": "H", "url": "https://h.com", "time": 0}],
        "session": ["https://s.com"],
        "settings": {"theme": "light", "custom_key": 42},
    }
    (tmp_path / "frame_data.json").write_text(json.dumps(data), "utf-8")
    monkeypatch.setattr("frame.store.data_dir", lambda: tmp_path)

    from frame.store import Store
    s = Store()
    try:
        assert isinstance(s.history, deque)
        assert s.history.maxlen == Store.MAX_HISTORY
        assert len(s.history) == 1
        assert s.bookmarks[0]["url"] == "https://b.com"
        assert s.session == ["https://s.com"]
        assert s.settings["theme"] == "light"
        assert s.settings["custom_key"] == 42
    finally:
        s._timer.stop()


def test_load_tolerates_corrupt_json(tmp_path, monkeypatch):
    (tmp_path / "frame_data.json").write_text("{rusak", "utf-8")
    monkeypatch.setattr("frame.store.data_dir", lambda: tmp_path)

    from frame.store import Store
    s = Store()
    try:
        # Tetap dapat diinisialisasi dengan default
        assert s.bookmarks == []
        assert len(s.history) == 0
    finally:
        s._timer.stop()