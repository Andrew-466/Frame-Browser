"""Rotating spinner icon untuk indikator loading di tab.

Pengganti progress bar yang dihapus — spinner muncul di tab yang
sedang loading, berputar halus, lalu hilang begitu selesai.
"""
from __future__ import annotations

from PyQt6.QtCore import QByteArray, QObject, Qt, QTimer
from PyQt6.QtGui import QIcon, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QApplication


# SVG spinner: circle dengan dash pattern, dirotasi per frame.
# Circumference r=6.5 ≈ 40.8 unit; dasharray "10 14" memberi busur
# yang jelas tanpa menutup penuh.
_SPINNER_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" '
    'viewBox="0 0 16 16" width="16" height="16">'
    '<g transform="rotate({angle} 8 8)">'
    '<circle cx="8" cy="8" r="6.5" fill="none" '
    'stroke="{color}" stroke-width="1.8" '
    'stroke-linecap="round" stroke-dasharray="10 14" />'
    "</g></svg>"
)


def render_spinner(angle: float, color: str, size: int = 16) -> QIcon:
    """Render spinner frame pada sudut tertentu, DPI-aware."""
    app = QApplication.instance()
    dpr = 1.0
    if app is not None:
        screen = app.primaryScreen()
        if screen is not None:
            try:
                dpr = max(1.0, float(screen.devicePixelRatio()))
            except (AttributeError, RuntimeError):
                dpr = 1.0

    svg = _SPINNER_SVG.format(angle=angle, color=color)
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    physical = max(1, int(round(size * dpr)))
    pm = QPixmap(physical, physical)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    renderer.render(p)
    p.end()
    pm.setDevicePixelRatio(dpr)
    return QIcon(pm)


class TabSpinner(QObject):
    """Spinner per tab — start saat loading, stop saat selesai.

    Saat stop, favicon asli dari `tab.view.icon()` direstore. Kalau
    favicon belum tersedia (kadang `loadFinished` lebih dulu dari
    `iconChanged`), panggil `_update_tab_icon` di MainWindow setelahnya
    untuk update saat favicon tiba.
    """

    def __init__(self, main_window, tab) -> None:
        super().__init__(main_window)
        self._window = main_window
        self._tab = tab
        self._angle = 0.0
        self._color = "#808080"
        self._timer = QTimer(self)
        self._timer.setInterval(80)
        self._timer.timeout.connect(self._tick)

    def set_color(self, color: str) -> None:
        self._color = color

    def start(self) -> None:
        if not self._timer.isActive():
            self._timer.start()
            self._tick()

    def stop(self) -> None:
        self._timer.stop()
        self._restore_favicon()

    def is_running(self) -> bool:
        return self._timer.isActive()

    def _tick(self) -> None:
        self._angle = (self._angle + 30.0) % 360.0
        try:
            idx = self._window.tabs.indexOf(self._tab)
        except RuntimeError:
            return
        if idx < 0:
            return
        self._window.tabs.setTabIcon(
            idx, render_spinner(self._angle, self._color)
        )

    def _restore_favicon(self) -> None:
        try:
            idx = self._window.tabs.indexOf(self._tab)
        except RuntimeError:
            return
        if idx < 0:
            return
        try:
            icon = self._tab.view.icon()
        except RuntimeError:
            return
        if icon is not None and not icon.isNull():
            self._window.tabs.setTabIcon(idx, icon)
        else:
            self._window.tabs.setTabIcon(idx, QIcon())