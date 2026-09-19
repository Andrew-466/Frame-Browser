"""Uji `is_safe_url` — daftar putih skema URL."""
from __future__ import annotations

import pytest

from frame.core import is_safe_url


@pytest.mark.parametrize("url,expected", [
    # Aman
    ("https://example.com", True),
    ("http://example.com", True),
    ("frame://newtab", True),
    ("about:blank", True),
    ("file:///tmp/a.html", True),
    ("view-source:https://example.com", True),

    # Skema berbahaya
    ("javascript:alert(1)", False),
    ("JAVASCRIPT:alert(1)", False),
    ("  javascript:alert(1)", False),
    ("data:text/html,<script>alert(1)</script>", False),
    ("vbscript:msgbox(1)", False),
    ("blob:https://example.com/uuid", False),
    ("chrome://settings", False),

    # Bukan URL
    ("", False),
    ("   ", False),
    ("notaurl", False),
    ("///nohost", False),
])
def test_is_safe_url(url, expected):
    assert is_safe_url(url) is expected


@pytest.mark.parametrize("url", [
    "HTTPS://example.com",
    "Http://example.com",
    "FRAME://newtab",
    "ABOUT:blank",
])
def test_is_safe_url_case_insensitive_scheme(url):
    # urlparse() menormalkan skema ke lowercase
    assert is_safe_url(url) is True