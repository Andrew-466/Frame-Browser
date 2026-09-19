"""Per-origin permission prompts dengan persistensi.

Menangani `featurePermissionRequested` dari `QWebEnginePage`:

  - Feature yang selalu ditolak (screen capture) → deny + log.
  - Feature yang punya keputusan tersimpan → langsung apply.
  - Feature yang belum diputuskan → tampilkan dialog.

Keputusan disimpan per-origin (`scheme://host[:port]`). Untuk jendela
penyamaran, keputusan disimpan di memori saja — tidak persisten.

Kenapa origin (bukan hostname): kamera/mikrofon/lokasi adalah izin
yang sensitif terhadap skema dan port. `http://example.com:8080`
secara teknis bukan origin yang sama dengan `https://example.com`.
Chromium sendiri memakai origin sebagai unit keputusan; kita ikuti.

Kenapa Desktop* selalu ditolak tanpa dialog: screen capture bisa
merekam seluruh layar user — tab lain, password manager, notifikasi.
Itu bukan sesuatu yang layak diberikan lewat satu klik "Allow".
Kalau nanti ada use case jelas (mis. web meeting app), buka kembali
secara eksplisit — jangan buka seluruh kategori.
"""
from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import QObject, Qt, QUrl
from PyQt6.QtWebEngineCore import QWebEnginePage
from PyQt6.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QMessageBox, QPushButton,
    QVBoxLayout, QWidget,
)

from .core import log
from .store import Store


# ── Feature mapping ─────────────────────────────────────────────────
# Qt enum → string stabil untuk persistensi JSON. Nama enum bisa
# berbeda antar versi PyQt6; gunakan getattr untuk kompatibilitas
# (kalau tidak ada, feature-nya tinggal tidak terdaftar → deny).
_FEATURE_KEYS = [
    ("MediaAudioCapture",         "media_audio_capture"),
    ("MediaVideoCapture",         "media_video_capture"),
    ("MediaAudioVideoCapture",    "media_audio_video_capture"),
    ("Geolocation",               "geolocation"),
    ("MouseLock",                 "mouse_lock"),
    ("Notifications",             "notifications"),
    ("ClipboardReadWrite",        "clipboard_read_write"),
    ("DesktopVideoCapture",       "desktop_video_capture"),
    ("DesktopAudioVideoCapture",  "desktop_audio_video_capture"),
]

FEATURE_NAMES: dict = {}
for _attr, _key in _FEATURE_KEYS:
    _member = getattr(QWebEnginePage.Feature, _attr, None)
    if _member is not None:
        FEATURE_NAMES[_member] = _key
del _attr, _key, _member


# Feature yang selalu ditolak tanpa dialog — lihat docstring modul.
ALWAYS_DENY: frozenset[str] = frozenset({
    "desktop_video_capture",
    "desktop_audio_video_capture",
})


# Label user-facing.
FEATURE_DISPLAY: dict[str, str] = {
    "media_audio_capture":         "microphone",
    "media_video_capture":         "camera",
    "media_audio_video_capture":   "camera and microphone",
    "geolocation":                 "location",
    "mouse_lock":                  "mouse pointer lock",
    "notifications":               "notifications",
    "clipboard_read_write":        "clipboard",
    "desktop_video_capture":       "screen recording",
    "desktop_audio_video_capture": "screen recording with audio",
}


# ── Helpers ─────────────────────────────────────────────────────────
def _feature_name(feature) -> str | None:
    """Map Qt Feature enum → string stabil. None kalau tidak dikenal."""
    return FEATURE_NAMES.get(feature)


def _origin_key(url: QUrl) -> str:
    """Normalize origin untuk key penyimpanan.

    - Skema dan host di-lowercase.
    - Port default (80 http / 443 https) dihilangkan supaya
      `https://example.com` dan `https://example.com:443` jadi satu key.
    - Return "" kalau URL tidak punya host (about:blank, data:, dll.).
    """
    if url is None:
        return ""
    try:
        scheme = url.scheme().lower()
        host = url.host().lower()
        port = url.port()
    except (AttributeError, RuntimeError):
        return ""
    if not scheme or not host:
        return ""
    if port in (-1, None):
        return f"{scheme}://{host}"
    if (scheme == "http" and port == 80) or (scheme == "https" and port == 443):
        return f"{scheme}://{host}"
    return f"{scheme}://{host}:{port}"


# ══════════════════════════════════════════════════════════════════════
#  Permission request dialog
# ══════════════════════════════════════════════════════════════════════
class PermissionRequestDialog(QDialog):
    """Tanya user: izinkan <origin> pakai <feature>?

    Expose `remember` (QCheckBox) — caller membaca nilainya setelah
    dialog closed. Bukan bagian dari public API Qt, tapi kita butuh
    cara untuk menyampaikan preferensi "remember" ke caller tanpa
    subclassing signal.
    """

    def __init__(
        self,
        origin: str,
        feature_display: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Permission Request")
        self.setModal(True)
        self.setMinimumWidth(420)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 16)
        lay.setSpacing(12)

        header = QLabel(f"<b>{origin}</b>")
        header.setWordWrap(True)
        header.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        lay.addWidget(header)

        body = QLabel(
            f"This site is requesting access to your "
            f"<b>{feature_display}</b>."
        )
        body.setWordWrap(True)
        lay.addWidget(body)

        self.remember = QCheckBox(
            "Remember this decision for this site"
        )
        self.remember.setChecked(True)
        lay.addWidget(self.remember)

        lay.addStretch(1)

        buttons = QDialogButtonBox()
        self.deny_btn = buttons.addButton(
            "Deny", QDialogButtonBox.ButtonRole.RejectRole
        )
        self.allow_btn = buttons.addButton(
            "Allow", QDialogButtonBox.ButtonRole.AcceptRole
        )
        self.allow_btn.setDefault(True)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)


# ══════════════════════════════════════════════════════════════════════
#  Permission manager
# ══════════════════════════════════════════════════════════════════════
class PermissionManager(QObject):
    """Handles `featurePermissionRequested` dengan persistensi per-origin.

    Public API: `handle_request(page, origin, feature)`.

    Thread safety: semua dipanggil dari main thread via Qt signal,
    jadi tidak perlu lock.

    `persist=False` → keputusan disimpan di memori saja. Dipakai
    oleh jendela penyamaran (PrivateWindow). Setiap instance punya
    memori sendiri — dua private window tidak saling berbagi.

    `dialog_factory` adalah hook untuk test — produksi memakai
    `PermissionRequestDialog`. Signature: `(origin, feature_display,
    parent) -> dialog` di mana dialog harus punya `.finished` (signal
    dengan satu argumen int) dan `.remember.isChecked()`.
    """

    def __init__(
        self,
        store: Store,
        parent_window: QWidget,
        *,
        persist: bool = True,
        dialog_factory: Callable[..., PermissionRequestDialog] | None = None,
    ) -> None:
        super().__init__(parent_window)
        self.store = store
        self.window = parent_window
        self.persist = persist
        self._memory: dict[tuple[str, str], str] = {}
        self._dialog_factory = dialog_factory or PermissionRequestDialog
        self._active_dialog: PermissionRequestDialog | None = None

    # ── Public API ──────────────────────────────────────────────────
    def handle_request(self, page, origin: QUrl, feature) -> None:
        origin_str = _origin_key(origin)
        feature_name = _feature_name(feature)

        if not origin_str:
            log.warning(
                "Permission request dari origin tak dikenal — ditolak "
                "(origin=%s)",
                origin.toString()[:120] if origin else "?",
            )
            self._apply(page, origin, feature, granted=False)
            return

        if feature_name is None:
            log.warning(
                "Permission feature tidak dikenal — ditolak "
                "(feature=%s origin=%s)",
                feature, origin_str,
            )
            self._apply(page, origin, feature, granted=False)
            return

        if feature_name in ALWAYS_DENY:
            log.warning(
                "Permission %s dari %s — ditolak (kategori selalu-tolak)",
                feature_name, origin_str,
            )
            self._apply(page, origin, feature, granted=False)
            return

        remembered = self._lookup(origin_str, feature_name)
        if remembered is not None:
            log.info(
                "Permission %s untuk %s: %s (dari memori)",
                feature_name, origin_str, remembered,
            )
            self._apply(
                page, origin, feature,
                granted=(remembered == "granted"),
            )
            return

        self._show_dialog(page, origin, feature, origin_str, feature_name)

    # ── Storage ─────────────────────────────────────────────────────
    def _lookup(self, origin: str, feature: str) -> str | None:
        if self.persist:
            return self.store.get_permission(origin, feature)
        return self._memory.get((origin, feature))

    def _remember(self, origin: str, feature: str, granted: bool) -> None:
        policy = "granted" if granted else "denied"
        if self.persist:
            self.store.set_permission(origin, feature, policy)
        else:
            self._memory[(origin, feature)] = policy

    # ── Qt glue ─────────────────────────────────────────────────────
    def _apply(self, page, origin: QUrl, feature, *, granted: bool) -> None:
        policy = (
            QWebEnginePage.PermissionPolicy.PermissionGrantedByUser
            if granted else
            QWebEnginePage.PermissionPolicy.PermissionDeniedByUser
        )
        try:
            page.setFeaturePermission(origin, feature, policy)
        except RuntimeError as exc:
            # Page sudah dihapus di sisi C++ (mis. tab ditutup saat
            # dialog terbuka). Tidak ada yang bisa dilakukan — decision
            # tetap tersimpan kalau user mencentang remember.
            log.debug("setFeaturePermission gagal (page sudah mati?): %s", exc)

    def _show_dialog(
        self,
        page,
        origin: QUrl,
        feature,
        origin_str: str,
        feature_name: str,
    ) -> None:
        # Serialize: kalau dialog lain masih terbuka, tolak yang baru
        # daripada membuka dialog bertumpuk. Keputusan user yang
        # belum diambil tidak hilang — dia akan ditanya lagi nanti.
        if self._active_dialog is not None:
            log.warning(
                "Permission request kedua datang saat dialog masih "
                "terbuka — ditolak sementara (feature=%s origin=%s)",
                feature_name, origin_str,
            )
            self._apply(page, origin, feature, granted=False)
            return

        display = FEATURE_DISPLAY.get(feature_name, feature_name)
        try:
            dlg = self._dialog_factory(origin_str, display, self.window)
        except Exception as exc:  # noqa: BLE001 — fail-safe deny
            log.error("Gagal membuat permission dialog: %s", exc)
            self._apply(page, origin, feature, granted=False)
            return

        self._active_dialog = dlg

        def _on_finished(result: int) -> None:
            self._active_dialog = None
            granted = (result == QDialog.DialogCode.Accepted)
            self._apply(page, origin, feature, granted=granted)
            try:
                remember = bool(dlg.remember.isChecked())
            except (RuntimeError, AttributeError):
                remember = False
            if remember:
                self._remember(origin_str, feature_name, granted)

        dlg.finished.connect(_on_finished)
        dlg.open()


# ══════════════════════════════════════════════════════════════════════
#  Manage stored permissions (dipanggil dari Settings)
# ══════════════════════════════════════════════════════════════════════
class PermissionsDialog(QDialog):
    """List & revoke stored per-site permissions."""

    def __init__(self, store: Store, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.store = store
        self.setWindowTitle("Site Permissions")
        self.resize(600, 460)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)

        header = QLabel(
            "Sites you have granted or denied permissions to. "
            "Removing an entry will cause the prompt to appear again "
            "next time."
        )
        header.setWordWrap(True)
        lay.addWidget(header)

        self.list = QListWidget()
        lay.addWidget(self.list, 1)

        row = QHBoxLayout()
        revoke_btn = QPushButton("Revoke selected")
        revoke_btn.clicked.connect(self._revoke_selected)
        clear_btn = QPushButton("Clear all")
        clear_btn.clicked.connect(self._clear_all)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        row.addWidget(revoke_btn)
        row.addWidget(clear_btn)
        row.addStretch(1)
        row.addWidget(close_btn)
        lay.addLayout(row)

        self.refresh()

    def refresh(self) -> None:
        self.list.clear()
        data = self.store.all_permissions()
        for origin in sorted(data.keys()):
            for feature, policy in sorted(data[origin].items()):
                label = (
                    f"{origin}  —  "
                    f"{FEATURE_DISPLAY.get(feature, feature)}: "
                    f"{policy}"
                )
                item = QListWidgetItem(label)
                item.setData(
                    Qt.ItemDataRole.UserRole, (origin, feature)
                )
                self.list.addItem(item)
        if self.list.count() == 0:
            self.list.addItem(
                QListWidgetItem("No stored permissions.")
            )

    def _revoke_selected(self) -> None:
        item = self.list.currentItem()
        if not item:
            return
        data = item.data(Qt.ItemDataRole.UserRole)
        if not (isinstance(data, tuple) and len(data) == 2):
            return
        origin, feature = data
        self.store.clear_permission(origin, feature)
        self.refresh()

    def _clear_all(self) -> None:
        if not self.store.all_permissions():
            return
        if QMessageBox.question(
            self,
            "Clear all permissions",
            "Remove all stored site permission decisions?",
        ) == QMessageBox.StandardButton.Yes:
            self.store.clear_all_permissions()
            self.refresh()