"""Jendela penyamaran — wrapper tipis di atas MainWindow."""
from __future__ import annotations

from .main_window import MainWindow


class PrivateWindow(MainWindow):
    def __init__(self) -> None:
        super().__init__(private=True)

    def closeEvent(self, event) -> None:
        event.accept()