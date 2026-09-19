"""Uji AdBlocker — pencocokan host & parser filter."""
from __future__ import annotations

import pytest

from frame.adblock import AdBlocker


@pytest.fixture
def blocker():
    """Instance AdBlocker tanpa QObject.__init__ (butuh QApplication)."""
    b = AdBlocker.__new__(AdBlocker)
    b.enabled = True
    b.blocked_count = 0
    b._hosts = {"doubleclick.net", "googlesyndication.com", "tracker.example"}
    return b


# ── Pencocokan host ──────────────────────────────────────────────────
@pytest.mark.parametrize("host,blocked", [
    ("doubleclick.net", True),
    ("ad.doubleclick.net", True),
    ("sub.ad.doubleclick.net", True),

    # Tidak boleh cocok di subdomain yang salah
    ("notdoubleclick.net", False),
    ("doubleclick.net.evil.com", False),

    ("googlesyndication.com", True),
    ("www.googlesyndication.com", True),
    ("tracker.example", True),
    ("x.tracker.example", True),

    ("example.com", False),
    ("", False),
])
def test_matches(blocker, host, blocked):
    assert blocker._matches(host) is blocked


def test_matches_case_insensitive(blocker):
    assert blocker._matches("DOUBLECLICK.NET") is True
    assert blocker._matches("Ad.DoubleClick.Net") is True


# ── Daftar bawaan ────────────────────────────────────────────────────
def test_builtin_hosts_loaded():
    hosts = AdBlocker._load_builtin()
    assert hosts, "Daftar host bawaan tidak boleh kosong"
    assert "doubleclick.net" in hosts
    assert "googleadservices.com" in hosts
    assert "scorecardresearch.com" in hosts


def test_builtin_hosts_normalized():
    hosts = AdBlocker._load_builtin()
    for h in hosts:
        assert h == h.lower(), f"host {h!r} tidak lowercase"
        assert h == h.strip(), f"host {h!r} punya whitespace"
        assert not h.startswith("#"), "baris komentar ikut masuk"
        assert "." in h, f"host {h!r} tidak punya titik"


# ── Parser file filter eksternal ─────────────────────────────────────
def test_load_external_rules(tmp_path):
    b = AdBlocker.__new__(AdBlocker)
    b._hosts = set()
    f = tmp_path / "filters.txt"
    f.write_text(
        "# komentar\n"
        "! adblock comment\n"
        "||ads.example.com^\n"
        "tracker.test/path/abc\n"
        "plain.example.com\n"
        "\n"
        "[Adblock Plus 2.0]\n",
        "utf-8",
    )
    b._load_external(f)
    assert "ads.example.com" in b._hosts
    assert "tracker.test" in b._hosts
    assert "plain.example.com" in b._hosts
    assert "" not in b._hosts


def test_load_external_missing_file_is_noop(tmp_path):
    b = AdBlocker.__new__(AdBlocker)
    b._hosts = {"existing.com"}
    b._load_external(tmp_path / "tidak-ada.txt")
    assert b._hosts == {"existing.com"}