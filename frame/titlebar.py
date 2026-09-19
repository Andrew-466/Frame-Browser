"""Custom title bar for the frameless Frame window.

Handles drag-to-move, double-click-to-maximize, and edge resize. The
parent window (MainWindow) manages the actual frameless flag and resize
edge detection; this widget only renders the bar and its buttons.
"""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QPoint, QSize, Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QSizePolicy, QToolButton, QWidget,
)

from .icons import (
    SVG_CLOSE, SVG_MAXIMIZE, SVG_MINIMIZE, SVG_RESTORE, icon_from_svg,
)
from .theme import THEMES


class TitleBar(QWidget):
    """Unified title bar with app icon + title + window buttons."""

    def __init__(self, window) -> None:
        super().__init__(window)
        self._window = window
        self.setObjectName("CustomTitleBar")
        self.setFixedHeight(34)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )

        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 0, 0, 0)
        lay.setSpacing(0)

        # ── App icon (from frame/data/ikon.png) ────────────────────
        self._icon_label = QLabel()
        self._icon_label.setObjectName("TitleBarIcon")
        self._icon_label.setFixedSize(16, 16)
        self._icon_label.setStyleSheet("background: transparent;")

        icon_path = Path(__file__).parent / "data" / "ikon.png"
        if icon_path.exists():
            pix = QPixmap(str(icon_path))
            if not pix.isNull():
                pix = pix.scaled(
                    16, 16,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                # DPI-aware: kalau pixmap non-integer DPR, set ratio
                # supaya tidak blur di layar Hi-DPI.
                dpr = self.devicePixelRatioF()
                if dpr and dpr != 1.0:
                    physical = int(16 * dpr)
                    pix = QPixmap(str(icon_path)).scaled(
                        physical, physical,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    pix.setDevicePixelRatio(dpr)
                self._icon_label.setPixmap(pix)
        # Kalau file tidak ada, label kosong saja — tidak fatal.

        lay.addWidget(self._icon_label)
        lay.addSpacing(8)

        # ── Title text ─────────────────────────────────────────────
        self.title_label = QLabel(window.windowTitle())
        self.title_label.setObjectName("TitleBarText")
        self.title_label.setStyleSheet("font-size: 12px; font-weight: 500;")
        lay.addWidget(self.title_label)
        lay.addStretch(1)

        # ── Window buttons ─────────────────────────────────────────
        c = THEMES.get("dark", THEMES["dark"])
        icon_color = c["text"]

        self._btn_min = self._make_button(
            "winMin", "Minimize", SVG_MINIMIZE, window.showMinimized,
            icon_color,
        )
        self._btn_max = self._make_button(
            "winMax", "Maximize", SVG_MAXIMIZE, self._toggle_max,
            icon_color,
        )
        self._btn_close = self._make_button(
            "winClose", "Close", SVG_CLOSE, window.close,
            icon_color,
        )

        lay.addWidget(self._btn_min)
        lay.addWidget(self._btn_max)
        lay.addWidget(self._btn_close)

        self._drag_pos: QPoint | None = None

    def _make_button(
        self, name: str, tip: str, svg: str, slot, color: str
    ) -> QToolButton:
        btn = QToolButton()
        btn.setObjectName(name)
        btn.setToolTip(tip)
        btn.setFixedSize(44, 34)
        btn.setAutoRaise(True)
        btn.setCursor(Qt.CursorShape.ArrowCursor)
        btn.setIcon(icon_from_svg(svg, color=color, size=12))
        btn.clicked.connect(slot)
        return btn

    def refresh_icons(self, color: str) -> None:
        """Re-render icons in the given color (called on theme change)."""
        self._btn_min.setIcon(icon_from_svg(SVG_MINIMIZE, color=color, size=12))
        max_svg = SVG_RESTORE if self._window.isMaximized() else SVG_MAXIMIZE
        self._btn_max.setIcon(icon_from_svg(max_svg, color=color, size=12))
        self._btn_close.setIcon(icon_from_svg(SVG_CLOSE, color=color, size=12))

    def set_title(self, text: str) -> None:
        self.title_label.setText(text)

    def _toggle_max(self) -> None:
        if self._window.isMaximized():
            self._window.showNormal()
        else:
            self._window.showMaximized()
        self._refresh_max_icon()

    def _refresh_max_icon(self) -> None:
        theme_name = self._window.store.settings.get("theme", "dark")
        c = THEMES.get(theme_name, THEMES["dark"])
        svg = SVG_RESTORE if self._window.isMaximized() else SVG_MAXIMIZE
        self._btn_max.setIcon(icon_from_svg(svg, color=c["text"], size=12))

    # ── Drag to move ────────────────────────────────────────────────
    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = (
                event.globalPosition().toPoint()
                - self._window.frameGeometry().topLeft()
            )
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if (
            self._drag_pos is not None
            and event.buttons() & Qt.MouseButton.LeftButton
        ):
            if self._window.isMaximized():
                self._window.showNormal()
                self._drag_pos = QPoint(self.width() // 2, self.height() // 2)
            self._window.move(
                event.globalPosition().toPoint() - self._drag_pos
            )
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self._drag_pos = None
        event.accept()

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._toggle_max()