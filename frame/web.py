"""WebView, BrowserTab, BrowserTabBar, FrameWebPage."""
from __future__ import annotations

from PyQt6.QtCore import Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWebEngineCore import (
    QWebEnginePage,
    QWebEngineProfile,
    QWebEngineSettings,
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import QTabBar, QVBoxLayout, QWidget

from .core import is_safe_url, log


class BrowserTabBar(QTabBar):
    middle_clicked = pyqtSignal(int)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            i = self.tabAt(event.position().toPoint())
            if i >= 0:
                self.middle_clicked.emit(i)
                return
        super().mouseReleaseEvent(event)


# Skema yang diserahkan ke aplikasi default OS, bukan dimuat sebagai
# halaman web. Kalau tidak ditangani, QWebEngine akan mencoba navigasi
# dan gagal dengan error "ERR_UNKNOWN_URL_SCHEME".
_OS_SCHEMES = frozenset({"mailto", "tel", "sms", "magnet", "bitcoin"})


class FrameWebPage(QWebEnginePage):
    """Page dengan certificate logging + OS-level scheme delegation.

    **Batasan penting**: `certificateError` hanya mencatat error ke
    stderr. Perilaku dialog & keputusan lanjut/tidak tetap milik
    Chromium. Ini **observability**, bukan enforcement.
    """

    def certificateError(self, error) -> bool:  # type: ignore[override]
        try:
            host = error.url().host()
        except (AttributeError, RuntimeError):
            host = "?"
        log.warning("Invalid certificate for %s: %s", host, error.description())
        return super().certificateError(error)

    def acceptNavigationRequest(self, url, nav_type, is_main_frame):  # type: ignore[override]
        """Delegasikan skema OS-level (mailto:, tel:, dst.) ke aplikasi default.

        QWebEngine tidak tahu cara handle skema non-web — kalau dibiarkan,
        navigasi gagal dan user dapat error page. Sebaliknya, kita serahkan
        ke QDesktopServices.openUrl() yang meneruskan ke handler OS default
        (mail client, phone dialer, torrent client, dst.).

        Hanya intercept di main-frame: sub-frame dengan skema ini hampir
        tidak pernah legit dan bisa disalahgunakan untuk spam handler OS.
        """
        if is_main_frame:
            scheme = url.scheme().lower()
            if scheme in _OS_SCHEMES:
                log.info("Delegasi skema %s ke aplikasi OS: %s",
                         scheme, url.toString()[:120])
                QDesktopServices.openUrl(url)
                return False
        return super().acceptNavigationRequest(url, nav_type, is_main_frame)


class WebView(QWebEngineView):
    def __init__(self, browser_window, parent=None) -> None:
        super().__init__(parent)
        self.browser_window = browser_window

    def createWindow(self, _type):
        return self.browser_window.add_new_tab(
            QUrl("about:blank"), "New Tab", switch=True
        ).view

    def acceptNavigationRequest(self, url, nav_type, is_main_frame):
        # Blokir navigasi main-frame dengan skema berbahaya.
        if is_main_frame and not is_safe_url(url.toString()):
            # Kalau skema ada di daftar OS-level, biarkan FrameWebPage
            # yang menangani (delegasi ke aplikasi sistem).
            scheme = url.scheme().lower()
            if scheme not in _OS_SCHEMES:
                log.warning("Navigation blocked: %s", url.toString()[:120])
                try:
                    self.browser_window.status.showMessage(
                        f"Navigation blocked: {url.toString()[:80]}", 4000
                    )
                except (AttributeError, RuntimeError):
                    pass
                return False
        return super().acceptNavigationRequest(url, nav_type, is_main_frame)


class BrowserTab(QWidget):
    def __init__(
        self,
        browser_window,
        profile: QWebEngineProfile | None = None,
    ) -> None:
        super().__init__()
        self.browser_window = browser_window

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.view = WebView(browser_window)
        # Bind ke profile — wajib untuk private mode, supaya halaman
        # tidak diam-diam memakai defaultProfile().
        if profile is not None:
            self.view.setPage(FrameWebPage(profile, self.view))
        self._configure_settings()

        layout.addWidget(self.view)

    def _configure_settings(self) -> None:
        """Set WebEngine settings dengan default yang lebih ketat.

        Prinsip: nyalakan seperlunya, matikan yang tidak diperlukan.
        Setiap attribute di bawah punya alasan eksplisit — jangan
        nyalakan kembali tanpa pertimbangan keamanan.
        """
        s = self.view.settings()

        # Wajib untuk web modern
        s.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.FullScreenSupportEnabled, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.ScrollAnimatorEnabled, True)

        # Dimatikan — permukaan serangan
        s.setAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled, False)
        s.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, False)
        s.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard, False)
        s.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, False)
        s.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, False)

        if self.browser_window.store.settings.get("low_end_mode", False):
            s.setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled, False)
            s.setAttribute(
                QWebEngineSettings.WebAttribute.Accelerated2dCanvasEnabled, False
            )
            s.setAttribute(QWebEngineSettings.WebAttribute.PdfViewerEnabled, False)