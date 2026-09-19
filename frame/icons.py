"""SVG icons + renderer ke QIcon dengan cache. DPI-aware."""
from __future__ import annotations

import hashlib
from functools import lru_cache

from PyQt6.QtCore import QByteArray, QRectF, Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QApplication

from .core import data_dir, log

SVG_BACK = """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" fill="currentColor" viewBox="0 0 24 24"><path d="M16.46 4.11a1 1 0 0 0-1.04.07l-10 7a.997.997 0 0 0 0 1.64l10 7c.17.12.37.18.57.18a.997.997 0 0 0 1-1V5c0-.37-.21-.71-.54-.89ZM15 17.08 7.74 12 15 6.92z"/></svg>"""
SVG_FORWARD = """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" fill="currentColor" viewBox="0 0 24 24"><path d="m18.57 11.18-10-7c-.31-.21-.7-.24-1.04-.07-.33.17-.54.51-.54.89v14c0 .37.21.71.54.89.15.08.3.11.46.11.2 0 .4-.06.57-.18l10-7a.997.997 0 0 0 0-1.64ZM9 17.08V6.92L16.26 12z"/></svg>"""
SVG_RELOAD = """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" fill="currentColor" viewBox="0 0 24 24"><path d="M21.21 8.11c-.25-.59-.56-1.16-.92-1.7-.36-.53-.77-1.03-1.22-1.48s-.95-.86-1.48-1.22c-.54-.36-1.11-.67-1.7-.92-.6-.26-1.24-.45-1.88-.58-1.32-.27-2.71-.27-4.03 0-.64.13-1.27.33-1.88.58-.59.25-1.16.56-1.7.92-.53.36-1.03.77-1.48 1.22-.17.17-.32.35-.48.52L1.99 3v6h6L5.86 6.87c.15-.18.31-.36.48-.52.36-.36.76-.69 1.18-.98.43-.29.89-.54 1.36-.74.48-.2.99-.36 1.5-.47a8 8 0 0 1 4.73.47c.47.2.93.45 1.36.74.42.29.82.62 1.18.98s.69.76.98 1.18c.29.43.54.89.74 1.36.2.48.36.99.47 1.5.11.53.16 1.07.16 1.61a7.85 7.85 0 0 1-.63 3.11c-.2.47-.45.93-.74 1.36-.29.42-.62.82-.98 1.18s-.76.69-1.18.98c-.43.29-.89.54-1.36.74-.48.2-.99.36-1.5.47a8 8 0 0 1-4.73-.47c-.47-.2-.93-.45-1.36-.74-.42-.29-.82-.62-1.18-.98s-.69-.76-.98-1.18c-.29-.43-.54-.89-.74-1.36-.2-.48-.36-.99-.47-1.5A8 8 0 0 1 3.99 12h-2c0 .68.07 1.36.2 2.01.13.64.33 1.27.58 1.88.25.59.56 1.16.92 1.7.36.53.77 1.03 1.22 1.48s.95.86 1.48 1.22c.54.36 1.11.67 1.7.92.6.26 1.24.45 1.88.58.66.13 1.34.2 2.01.2s1.35-.07 2.01-.2c.64-.13 1.27-.33 1.88-.58.59-.25 1.16-.56 1.7-.92.53-.36 1.03-.77 1.48-1.22s.86-.95 1.22-1.48c.36-.54.67-1.11.92-1.7.26-.6.45-1.24.58-1.88.13-.66.2-1.33.2-2.01s-.07-1.36-.2-2.01c-.13-.64-.33-1.27-.58-1.88Z"/></svg>"""
SVG_HOME = """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" fill="currentColor" viewBox="0 0 24 24"><path d="M3 13h1v7c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2v-7h1c.4 0 .77-.24.92-.62.15-.37.07-.8-.22-1.09l-8.99-9a.996.996 0 0 0-1.41 0l-9.01 9c-.29.29-.37.72-.22 1.09s.52.62.92.62Zm9-8.59 6 6V20H6v-9.59z"/></svg>"""
SVG_ENTER = """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" fill="currentColor" viewBox="0 0 24 24"><path d="M18 12c0 1.65-1.35 3-3 3H9v-3l-5 4 5 4v-3h6c2.76 0 5-2.24 5-5V4h-2z"/></svg>"""
SVG_NEW = """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" fill="currentColor" viewBox="0 0 24 24"><path d="M3 13h8v8h2v-8h8v-2h-8V3h-2v8H3z"/></svg>"""
SVG_STAR_OUTLINE = """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" fill="currentColor" viewBox="0 0 24 24"><path d="M22 9.24l-7.19-.62L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21 12 17.27 18.18 21l-1.63-7.03L22 9.24zM12 15.4l-3.76 2.27 1-4.28-3.32-2.88 4.38-.38L12 6.1l1.71 4.04 4.38.38-3.32 2.88 1 4.28L12 15.4z"/></svg>"""
SVG_STAR_FILLED = """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" fill="currentColor" viewBox="0 0 24 24"><path d="M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z"/></svg>"""
SVG_DOWNLOAD = """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" fill="currentColor" viewBox="0 0 24 24"><path d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z"/></svg>"""
SVG_MENU = """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" fill="currentColor" viewBox="0 0 24 24"><path d="M3 6h18v2H3zM3 11h18v2H3zM3 16h18v2H3z"/></svg>"""
SVG_SEARCH = """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" fill="currentColor" viewBox="0 0 24 24"><path d="M15.5 14h-.79l-.28-.27A6.47 6.47 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0A4.5 4.5 0 1 1 14 9.5 4.5 4.5 0 0 1 9.5 14z"/></svg>"""
SVG_LOCK = """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" fill="currentColor" viewBox="0 0 24 24"><path d="M12 1C9.24 1 7 3.24 7 6v3H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V11c0-1.1-.9-2-2-2h-1V6c0-2.76-2.24-5-5-5zm-3 5c0-1.66 1.34-3 3-3s3 1.34 3 3v3H9V6zm3 8c1.1 0 2 .9 2 2 0 .74-.4 1.38-1 1.72V19c0 .55-.45 1-1 1s-1-.45-1-1v-1.28c-.6-.35-1-.98-1-1.72 0-1.1.9-2 2-2z"/></svg>"""
SVG_INSECURE = """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" fill="currentColor" viewBox="0 0 24 24"><path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z"/></svg>"""
SVG_INFO = """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" fill="currentColor" viewBox="0 0 24 24"><path d="M11 7h2v2h-2zm0 4h2v6h-2zm1-9C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8z"/></svg>"""
SVG_CLOSE = """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" fill="currentColor" viewBox="0 0 24 24"><path d="M19 6.41 17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>"""
SVG_MINIMIZE = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 12 12"><rect x="1.5" y="5.5" width="9" height="1" fill="currentColor"/></svg>"""
SVG_MAXIMIZE = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 12 12"><rect x="1.5" y="1.5" width="9" height="9" fill="none" stroke="currentColor" stroke-width="1.2"/></svg>"""
SVG_RESTORE = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 12 12"><rect x="1.5" y="3" width="7.5" height="7.5" fill="none" stroke="currentColor" stroke-width="1.2"/><path d="M3.5 3V1.5h7v7H9" fill="none" stroke="currentColor" stroke-width="1.2"/></svg>"""
SVG_ARROW_UP = """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" fill="currentColor" viewBox="0 0 24 24"><path d="M7.41 15.41 12 10.83l4.59 4.58L18 14l-6-6-6 6z"/></svg>"""
SVG_ARROW_DOWN = """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" fill="currentColor" viewBox="0 0 24 24"><path d="M7.41 8.59 12 13.17l4.59-4.58L18 10l-6 6-6-6z"/></svg>"""
SVG_PIN = """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" fill="currentColor" viewBox="0 0 24 24"><path d="M14 4v5c0 1.12.37 2.16 1 3H9c.65-.86 1-1.9 1-3V4h4m3-2H7c-.55 0-1 .45-1 1s.45 1 1 1h1v5c0 1.66-1.34 3-3 3v2h5.97v7l1 1 1-1v-7H19v-2c-1.66 0-3-1.34-3-3V4h1c.55 0 1-.45 1-1s-.45-1-1-1z"/></svg>"""
SVG_CHEVRON_RIGHT = """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" fill="currentColor" viewBox="0 0 24 24"><path d="M10 6 8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z"/></svg>"""
SVG_GLOBE = """<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>"""

_icon_cache: dict = {}


def _current_dpr() -> float:
    """Device pixel ratio layar utama. Fallback ke 1.0 kalau QApplication
    belum ada."""
    app = QApplication.instance()
    if app is None:
        return 1.0
    screen = app.primaryScreen()
    if screen is None:
        return 1.0
    try:
        return max(1.0, float(screen.devicePixelRatio()))
    except (AttributeError, RuntimeError):
        return 1.0


def icon_from_svg(svg_code: str, color: str = "#000000", size: int = 24) -> QIcon:
    """Render SVG jadi QIcon, DPI-aware."""
    dpr = _current_dpr()
    key = (hash(svg_code), color, size, dpr)
    if key in _icon_cache:
        return _icon_cache[key]

    svg_code = svg_code.replace("currentColor", color)
    ba = QByteArray(svg_code.encode("utf-8"))
    renderer = QSvgRenderer(ba)

    physical = max(1, int(round(size * dpr)))
    pixmap = QPixmap(physical, physical)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(dpr)

    icon = QIcon(pixmap)
    _icon_cache[key] = icon
    return icon


@lru_cache(maxsize=16)
def spinner_frames(
    color: str = "#8ab4f8",
    size: int = 16,
    frame_count: int = 8,
) -> tuple:
    """Pre-render a rotating arc spinner as a tuple of QIcons.

    - `color` — accent color (biasanya THEMES[theme]["accent"])
    - `size`  — logical pixels (harus sama dengan setIconSize tab bar)
    - `frame_count` — number of rotation frames (8 = smooth enough)

    Returns a tuple (not list) so `@lru_cache` can hash the result.
    Each frame is a 270° arc rotated by `360/frame_count` degrees.
    """
    dpr = _current_dpr()
    physical = max(1, int(round(size * dpr)))
    stroke = max(2, int(round(2 * dpr)))
    margin = max(2, int(round(2.5 * dpr)))

    color_obj = QColor(color)
    rect = QRectF(
        margin, margin,
        physical - 2 * margin,
        physical - 2 * margin,
    )

    frames = []
    for i in range(frame_count):
        # Qt angles are in 1/16th of a degree, counterclockwise from
        # 3 o'clock. We sweep 270° and rotate the start clockwise.
        start_deg = 90 - (360 * i / frame_count)
        start_angle = int(start_deg * 16)
        span_angle = int(270 * 16)

        pix = QPixmap(physical, physical)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(color_obj)
        pen.setWidth(stroke)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawArc(rect, start_angle, span_angle)
        p.end()
        pix.setDevicePixelRatio(dpr)
        frames.append(QIcon(pix))

    return tuple(frames)

# ══════════════════════════════════════════════════════════════════════
#  QSS image helpers — render SVG → PNG file path
# ══════════════════════════════════════════════════════════════════════
_CHECK_SVG_TPL = (
    '<svg xmlns="http://www.w3.org/2000/svg" '
    'viewBox="0 0 {size} {size}" width="{size}" height="{size}">'
    '<path fill="none" stroke="{color}" stroke-width="2.4" '
    'stroke-linecap="round" stroke-linejoin="round" '
    'd="M3.5 8.5 L6.5 11.5 L12.5 4.5"/></svg>'
)

_CLOSE_SVG_TPL = (
    '<svg xmlns="http://www.w3.org/2000/svg" '
    'viewBox="0 0 {size} {size}" width="{size}" height="{size}">'
    '<path fill="none" stroke="{color}" stroke-width="1.8" '
    'stroke-linecap="round" stroke-linejoin="round" '
    'd="M4 4 L12 12 M12 4 L4 12"/></svg>'
)


@lru_cache(maxsize=32)
def _svg_to_png_path(
    svg_template: str, color: str, size: int, prefix: str
) -> str:
    """Render SVG template → PNG file, return path dengan forward-slash.

    PNG di-render pada 2× resolusi supaya QSS scale-down tetap tajam
    di Hi-DPI. Cached per (template, color, size, prefix).
    """
    try:
        cache_dir = data_dir() / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        log.warning("Cannot create icon cache folder: %s", exc)
        return ""

    key = hashlib.md5(
        f"{prefix}:{color}:{size}".encode("utf-8")
    ).hexdigest()[:10]
    png_path = cache_dir / f"{prefix}_{key}.png"

    if not png_path.exists():
        svg = svg_template.format(color=color, size=size)
        renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
        scale = 2
        physical = size * scale
        pixmap = QPixmap(physical, physical)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        if not pixmap.save(str(png_path), "PNG"):
            log.warning("Failed to save %s PNG to %s", prefix, png_path)
            return ""

    return str(png_path).replace("\\", "/")


def check_png_path(color: str, size: int = 16) -> str:
    """Checkmark PNG untuk `QCheckBox::indicator:checked` `image:`."""
    return _svg_to_png_path(_CHECK_SVG_TPL, color, size, "check")


def close_png_path(color: str, size: int = 14) -> str:
    """Close (X) PNG untuk `QTabBar::close-button` `image:`."""
    return _svg_to_png_path(_CLOSE_SVG_TPL, color, size, "close")

def clear_icon_cache() -> None:
    _icon_cache.clear()
    spinner_frames.cache_clear()
    _svg_to_png_path.cache_clear()