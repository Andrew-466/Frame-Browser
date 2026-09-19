"""Toast notification — non-blocking feedback in the bottom-right corner."""
from __future__ import annotations

from PyQt6.QtCore import (
    QEasingCurve, QPropertyAnimation, Qt, QTimer, pyqtProperty,
)
from PyQt6.QtWidgets import (
    QGraphicsOpacityEffect, QHBoxLayout, QLabel, QWidget,
)

from .theme import THEMES


class Toast(QWidget):
    """Single toast that auto-hides after a few seconds.

    Anchored to the bottom-right of the parent widget. Multiple calls to
    `ToastHost.show_message` will coalesce to prevent spam.
    """

    def __init__(self, parent: QWidget, text: str, duration_ms: int = 3000) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setObjectName("Toast")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(0)

        self.label = QLabel(text)
        self.label.setWordWrap(True)
        self.label.setStyleSheet("font-size: 12px; background: transparent;")
        lay.addWidget(self.label)

        self._effect = QGraphicsOpacityEffect(self)
        self._effect.setOpacity(0.0)
        self.setGraphicsEffect(self._effect)

        self._anim = QPropertyAnimation(self._effect, b"opacity", self)
        self._anim.setDuration(180)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._fade_out)

        self._duration = duration_ms
        self.adjustSize()

    def set_text(self, text: str) -> None:
        self.label.setText(text)
        self.adjustSize()
        self._position()
        self._restart_timer()

    def appear(self) -> None:
        self._apply_style()
        self.adjustSize()
        self._position()
        self.show()
        self.raise_()
        self._fade_in()
        self._restart_timer()

    def _restart_timer(self) -> None:
        self._hide_timer.start(self._duration)

    def _apply_style(self) -> None:
        store = getattr(self.parent().window(), "store", None)
        theme_name = "dark"
        if store is not None:
            theme_name = store.settings.get("theme", "dark")
        c = THEMES.get(theme_name, THEMES["dark"])
        self.setStyleSheet(
            f"""
            QWidget#Toast {{
                background-color: {c['bg_light']};
                border: 1px solid {c['border']};
                border-radius: 10px;
            }}
            QWidget#Toast QLabel {{ color: {c['text']}; }}
            """
        )

    def _position(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        margin = 20
        x = parent.width() - self.width() - margin
        y = parent.height() - self.height() - margin
        self.move(max(margin, x), max(margin, y))

    def _fade_in(self) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._effect.opacity())
        self._anim.setEndValue(1.0)
        self._anim.start()

    def _fade_out(self) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._effect.opacity())
        self._anim.setEndValue(0.0)
        self._anim.finished.connect(self._cleanup_once)
        self._anim.start()

    def _cleanup_once(self) -> None:
        try:
            self._anim.finished.disconnect(self._cleanup_once)
        except TypeError:
            pass
        if self._effect.opacity() < 0.05:
            self.deleteLater()


class ToastHost:
    """One toast per window — coalescing to prevent spam.

    Usage:
        self.toast = ToastHost(self)
        self.toast.show_message("Bookmark added", key="bookmark")
    """

    def __init__(self, parent: QWidget) -> None:
        self._parent = parent
        self._toast: Toast | None = None
        self._pending_key: str | None = None

    def show_message(
        self, text: str, *, key: str | None = None, duration_ms: int = 3000
    ) -> None:
        # Coalesce: if the last toast with the same key is still visible,
        # update its text instead of creating a new toast.
        if (
            self._toast is not None
            and key is not None
            and self._pending_key == key
        ):
            try:
                self._toast.set_text(text)
                return
            except RuntimeError:
                self._toast = None

        self._dismiss()
        self._toast = Toast(self._parent, text, duration_ms=duration_ms)
        self._pending_key = key
        self._toast.appear()

    def _dismiss(self) -> None:
        if self._toast is not None:
            try:
                self._toast.deleteLater()
            except RuntimeError:
                pass
            self._toast = None