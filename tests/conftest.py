"""Konfigurasi pytest untuk Frame.

Memastikan QApplication (platform offscreen) dibuat sekali sebelum
test yang membutuhkan QObject/QTimer berjalan.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(autouse=True, scope="session")
def _qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app