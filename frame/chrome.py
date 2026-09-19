"""Frameless window chrome: custom title bar + tapered glow border."""
from __future__ import annotations

import colorsys
from typing import Callable, Literal

from PyQt6.QtCore import QEvent, QObject, QPoint, QPointF, Qt, QTimer
from PyQt6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPolygonF
from PyQt6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QSizePolicy,
    QToolButton, QVBoxLayout, QWidget,
)

from .theme import THEMES


GlowMode = Literal["off", "static", "rgb"]
LightGlowStyle = Literal["rgb", "solid"]


# ══════════════════════════════════════════════════════════════════════
#  GlowBorder
# ══════════════════════════════════════════════════════════════════════
class GlowBorder(QWidget):
    """Container dengan tapered glow border (atas tebal → memudar ke bawah)."""

    def __init__(
        self,
        theme_getter: Callable[[], str],
        mode: GlowMode = "rgb",
        glow_width: int = 3,
        radius: int = 8,
        taper_ratio: float = 0.5,
        light_style: str = "solid",
        light_sat: float = 0.95,
        light_lightness: float = 0.32,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._theme_getter = theme_getter
        self._mode = mode
        self._glow_width = glow_width
        self._radius = radius
        self._taper_ratio = max(0.05, min(1.0, taper_ratio))
        self._light_style = (
            light_style if light_style in ("rgb", "solid") else "solid"
        )
        self._light_sat = max(0.0, min(1.0, light_sat))
        self._light_lightness = max(0.0, min(1.0, light_lightness))
        self._phase = 0.0
        self._static_color = QColor("#7ea6ff")

        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAutoFillBackground(False)

        self._content_layout = QVBoxLayout(self)
        self._content_layout.setSpacing(0)
        self._apply_margins()

        self._timer = QTimer(self)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self._tick)

        self.refresh_theme()
        self._sync_timer()

    # ── Public API ─────────────────────────────────────────────────
    def content_layout(self) -> QVBoxLayout:
        return self._content_layout

    def glow_width(self) -> int:
        return self._glow_width

    def taper_ratio(self) -> float:
        return self._taper_ratio

    def set_taper_ratio(self, ratio: float) -> None:
        self._taper_ratio = max(0.05, min(1.0, ratio))
        self._apply_margins()
        self.update()

    def set_glow_width(self, width: int) -> None:
        """Ubah ketebalan glow (1-6 px)."""
        self._glow_width = max(0, min(8, int(width)))
        self._apply_margins()
        self.update()

    def glow_width_value(self) -> int:
        return self._glow_width

    def set_light_style(self, style: str) -> None:
        """Ubah gaya glow light mode: 'rgb' atau 'solid'."""
        if style not in ("rgb", "solid"):
            return
        self._light_style = style
        self.update()

    def set_light_rgb_params(self, sat: float, lightness: float) -> None:
        """Ubah saturation/lightness RGB glow untuk light mode."""
        self._light_sat = max(0.0, min(1.0, sat))
        self._light_lightness = max(0.0, min(1.0, lightness))
        self.update()

    def refresh_theme(self) -> None:
        c = THEMES.get(self._theme_getter(), THEMES["dark"])
        self._static_color = QColor(c["accent"])
        self.update()

    def set_mode(self, mode: GlowMode) -> None:
        self._mode = mode
        self._apply_margins()
        self._sync_timer()
        self.update()

    # ── Internal ───────────────────────────────────────────────────
    def _apply_margins(self) -> None:
        """Inset konten dari border."""
        if self._mode == "off":
            self._content_layout.setContentsMargins(0, 0, 0, 0)
            return
        top_glow = self._glow_width
        side = top_glow + 1
        self._content_layout.setContentsMargins(side, top_glow + 1, side, 0)

    def _sync_timer(self) -> None:
        if self._mode == "rgb" and self.isVisible():
            if not self._timer.isActive():
                self._timer.start()
        else:
            self._timer.stop()
            if self._mode != "rgb":
                self._phase = 0.0

    def _tick(self) -> None:
        self._phase = (self._phase + 0.003) % 1.0
        self.update()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._sync_timer()

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self._timer.stop()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        theme = self._theme_getter()
        c = THEMES.get(theme, THEMES["dark"])
        is_light = theme == "light"

        p.fillRect(self.rect(), QColor(c["bg"]))

        if self._mode == "off":
            p.end()
            return

        W = self.width()
        H = self.height()
        if W <= 0 or H <= 0:
            p.end()
            return

        top_glow = self._glow_width
        taper_end_y = max(top_glow + 2, int(H * self._taper_ratio))
        side_end = 0

        # ── Brush: solid atau gradient RGB ─────────────────────────
        if self._mode == "static":
            brush = QBrush(self._static_color)
        elif is_light and self._light_style == "solid":
            # Light mode + solid: warna accent tema (biru navy).
            brush = QBrush(self._static_color)
        else:
            grad = QLinearGradient(QPointF(0, 0), QPointF(W, H))
            if is_light:
                sat = self._light_sat
                lightness = self._light_lightness
            else:
                sat = 0.70
                lightness = 0.62
            base = self._phase
            for i, stop in enumerate((0.0, 0.25, 0.5, 0.75, 1.0)):
                hue = (base + i * 0.25) % 1.0
                r, g, b = colorsys.hls_to_rgb(hue, lightness, sat)
                grad.setColorAt(
                    stop, QColor(int(r * 255), int(g * 255), int(b * 255))
                )
            brush = QBrush(grad)

        p.setBrush(brush)
        p.setPen(Qt.PenStyle.NoPen)

        p.drawRect(0, 0, W, top_glow)

        left_poly = QPolygonF([
            QPointF(0, 0),
            QPointF(top_glow, 0),
            QPointF(side_end, taper_end_y),
            QPointF(0, taper_end_y),
        ])
        p.drawPolygon(left_poly)

        right_poly = QPolygonF([
            QPointF(W, 0),
            QPointF(W - top_glow, 0),
            QPointF(W - side_end, taper_end_y),
            QPointF(W, taper_end_y),
        ])
        p.drawPolygon(right_poly)

        p.end()


# ══════════════════════════════════════════════════════════════════════
#  CustomTitleBar
# ══════════════════════════════════════════════════════════════════════
class CustomTitleBar(QWidget):
    """Title bar minimal untuk window frameless.

    Progress bar kecil di sebelah kiri tombol minimize — pengganti
    status bar yang dihapus.
    """

    def __init__(self, window: QWidget) -> None:
        super().__init__(window)
        self._window = window
        self.setObjectName("CustomTitleBar")
        self.setFixedHeight(36)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 0, 8, 0)
        lay.setSpacing(10)

        self.icon_label = QLabel()
        self.icon_label.setObjectName("CustomTitleBarIcon")
        self.icon_label.setFixedSize(22, 22)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._refresh_icon()
        lay.addWidget(self.icon_label)

        self.title_label = QLabel(window.windowTitle() or "Frame")
        self.title_label.setObjectName("CustomTitleBarTitle")
        lay.addWidget(self.title_label)

        lay.addStretch(1)

        self.btn_min = self._make_btn("—", self._window.showMinimized, "Minimize")
        self.btn_max = self._make_btn("☐", self._toggle_max, "Maximize")
        self.btn_close = self._make_btn("✕", self._window.close, "Close")
        self.btn_close.setObjectName("CustomTitleBarClose")
        lay.addWidget(self.btn_min)
        lay.addWidget(self.btn_max)
        lay.addWidget(self.btn_close)

    def _make_btn(self, text: str, slot, tooltip: str) -> QToolButton:
        btn = QToolButton()
        btn.setText(text)
        btn.setToolTip(tooltip)
        btn.setAutoRaise(True)
        btn.setFixedSize(32, 24)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setObjectName("CustomTitleBarButton")
        btn.clicked.connect(slot)
        return btn

    def _refresh_icon(self) -> None:
        icon = self._window.windowIcon()
        if icon.isNull():
            return
        logical = self.icon_label.width() or 22
        screen = self._window.screen() or QApplication.primaryScreen()
        dpr = 1.0
        if screen is not None:
            try:
                dpr = max(1.0, float(screen.devicePixelRatio()))
            except (AttributeError, RuntimeError):
                dpr = 1.0
        physical = max(1, int(round(logical * dpr)))
        pm = icon.pixmap(physical, physical)
        if pm.isNull():
            return
        pm.setDevicePixelRatio(dpr)
        self.icon_label.setPixmap(pm)

    def _toggle_max(self) -> None:
        if self._window.isMaximized():
            self._window.showNormal()
            self.btn_max.setText("☐")
        else:
            self._window.showMaximized()
            self.btn_max.setText("❐")

    def set_title(self, text: str) -> None:
        self.title_label.setText(text)

    def refresh_icon(self) -> None:
        self._refresh_icon()

    # ── Drag & double-click ────────────────────────────────────────
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self._window.windowHandle()
            if handle is not None:
                handle.startSystemMove()
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._toggle_max()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


# ══════════════════════════════════════════════════════════════════════
#  FramelessHelper
# ══════════════════════════════════════════════════════════════════════
class FramelessHelper(QObject):
    """Detect mouse di tepi window → `startSystemResize`."""

    def __init__(
        self,
        window: QWidget,
        source_widget: QWidget,
        border: int = 6,
    ) -> None:
        super().__init__(window)
        self._window = window
        self._source = source_widget
        self._border = border
        source_widget.setMouseTracking(True)
        source_widget.installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj is not self._source:
            return False

        et = event.type()
        if et == QEvent.Type.MouseMove:
            edge = self._edge_at(event.position().toPoint())
            self._set_cursor(edge)
        elif et == QEvent.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.LeftButton:
                edge = self._edge_at(event.position().toPoint())
                if edge:
                    handle = self._window.windowHandle()
                    if handle is not None:
                        handle.startSystemResize(edge)
                        return True
        return False

    def _edge_at(self, pos: QPoint):
        if self._window.isMaximized() or self._window.isFullScreen():
            return Qt.Edge(0)
        w = self._window.width()
        h = self._window.height()
        x, y = pos.x(), pos.y()
        b = self._border
        edge = Qt.Edge(0)
        if x < b:
            edge |= Qt.Edge.LeftEdge
        if x > w - b:
            edge |= Qt.Edge.RightEdge
        if y < b:
            edge |= Qt.Edge.TopEdge
        if y > h - b:
            edge |= Qt.Edge.BottomEdge
        return edge

    def _set_cursor(self, edge) -> None:
        try:
            e = int(edge.value)
        except AttributeError:
            e = int(edge)
        L, R, T, B = 1, 2, 4, 8
        if (e & L) and (e & T):
            c = Qt.CursorShape.SizeFDiagCursor
        elif (e & R) and (e & B):
            c = Qt.CursorShape.SizeFDiagCursor
        elif (e & R) and (e & T):
            c = Qt.CursorShape.SizeBDiagCursor
        elif (e & L) and (e & B):
            c = Qt.CursorShape.SizeBDiagCursor
        elif e & (L | R):
            c = Qt.CursorShape.SizeHorCursor
        elif e & (T | B):
            c = Qt.CursorShape.SizeVerCursor
        else:
            self._source.unsetCursor()
            return
        self._source.setCursor(c)