"""Entry point: python -m frame"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# ── MUST: import QtWebEngineWidgets BEFORE QApplication is created. ──
from PyQt6.QtWebEngineWidgets import QWebEngineView  # noqa: F401
from PyQt6.QtWebEngineCore import QWebEngineProfile  # noqa: F401

from PyQt6.QtCore import QTimer, Qt, QUrl
from PyQt6.QtWidgets import QApplication, QMessageBox

from .core import (
    APP_NAME, LOW_END_FLAGS, NORMAL_FLAGS, detect_total_ram_gb,
    i18n_load, log, pre_init_should_use_low_end, tr,
)
from .internal import register_scheme
from .singleton import start_server, try_forward_to_existing


# Module-level reference — jaga lifecycle QLocalServer supaya tidak
# di-GC saat main() return (server harus hidup selama event loop).
_singleton_server = None


def _extract_urls_from_argv() -> list[str]:
    """Ambil URL dari sys.argv[1:], filter flag Qt/Chromium.

    Windows: kalau Frame terdaftar sebagai handler URL, OS memanggil
    `frame.exe "https://..."` — URL jadi argv[1].
    """
    out: list[str] = []
    for arg in sys.argv[1:]:
        if not arg or arg.startswith("-"):
            continue
        out.append(arg)
    return out


def main() -> int:
    global _singleton_server

    low_end = pre_init_should_use_low_end()
    flags = LOW_END_FLAGS if low_end else NORMAL_FLAGS
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", flags)
    log.info("Mode: %s", "LOW POWER" if low_end else "Normal")

    urls_from_cli = _extract_urls_from_argv()

    # Coba teruskan ke instance yang sudah berjalan.
    # Overhead: QtWebEngine sudah di-import di atas (wajib sebelum
    # QApplication), jadi "exit instan" belum tercapai — tapi tetap
    # jauh lebih baik dari bikin window kedua.
    if try_forward_to_existing(urls_from_cli):
        log.info("URL diteruskan ke instance yang sudah berjalan.")
        return 0

    register_scheme()

    # Qt6 Hi-DPI rounding — pertahankan DPR non-integer (1.25, 1.5, dst.).
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)

    i18n_load("en", Path(__file__).parent / "data")

    if low_end:
        try:
            QApplication.setEffectEnabled(Qt.UIEffect.UI_AnimateMenu, False)
            QApplication.setEffectEnabled(Qt.UIEffect.UI_FadeMenu, False)
            QApplication.setEffectEnabled(Qt.UIEffect.UI_AnimateCombo, False)
            QApplication.setEffectEnabled(Qt.UIEffect.UI_AnimateTooltip, False)
        except (AttributeError, RuntimeError) as exc:
            log.debug("Cannot disable UI animations: %s", exc)

    from .main_window import MainWindow
    window = MainWindow(pre_init_low_end=low_end)

    # Kalau ada URL dari CLI, ganti new tab default dengan URL itu.
    if urls_from_cli:
        while window.tabs.count():
            window.tabs.removeTab(0)
        for u in urls_from_cli:
            window.add_new_tab(QUrl(u), "New Tab", switch=False, force=True)
        if window.tabs.count():
            window.tabs.setCurrentIndex(0)

    # Start IPC server — terima URL dari instance berikutnya.
    def _on_external_urls(new_urls: list[str]) -> None:
        for u in new_urls:
            window.add_new_tab(QUrl(u), "New Tab", switch=True)
        # Bawa window ke depan — user klik link dari aplikasi lain,
        # ekspektasinya Frame muncul.
        window.raise_()
        window.activateWindow()

    _singleton_server = start_server(_on_external_urls)

    if low_end:
        ram = detect_total_ram_gb()
        if ram is not None:
            QTimer.singleShot(400, lambda: QMessageBox.information(
                window, tr("low_end.title"), tr("low_end.body", ram=ram)
            ))

    window.show()

    exit_code = app.exec()

    # Cleanup IPC socket sebelum exit.
    if _singleton_server is not None:
        _singleton_server.close()
        _singleton_server = None

    return exit_code


if __name__ == "__main__":
    sys.exit(main())