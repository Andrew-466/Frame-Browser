"""Uji PermissionManager — decision logic, persistence, private mode.

Kategori:
  A. `_origin_key` — normalisasi origin
  B. `_feature_name` — mapping enum → string
  C. `handle_request` — always-deny, no-memory, remembered
  D. Dialog lifecycle — user Allow / Deny / remember
  E. Serialisasi — request kedua saat dialog terbuka
  F. Persistence — normal vs private mode
  G. Store permission methods — get/set/clear/sanitize
"""
from __future__ import annotations

import json

import pytest
from PyQt6.QtCore import QUrl
from PyQt6.QtWebEngineCore import QWebEnginePage
from PyQt6.QtWidgets import QDialog, QWidget

from frame.permissions import (
    ALWAYS_DENY,
    FEATURE_NAMES,
    PermissionManager,
    _feature_name,
    _origin_key,
)


# ══════════════════════════════════════════════════════════════════════
#  Fakes
# ══════════════════════════════════════════════════════════════════════
class FakePage:
    """Page minimal — cukup punya setFeaturePermission."""

    def __init__(self) -> None:
        self.calls: list = []
        self.raise_error = None

    def setFeaturePermission(self, origin, feature, policy):  # noqa: N802
        if self.raise_error is not None:
            raise self.raise_error
        self.calls.append((origin, feature, policy))


class _FakeSignal:
    def __init__(self) -> None:
        self._handlers = []

    def connect(self, h):
        self._handlers.append(h)

    def emit(self, *args):
        for h in list(self._handlers):
            h(*args)


class _FakeCheckbox:
    def __init__(self, checked: bool) -> None:
        self._checked = checked

    def isChecked(self) -> bool:
        return self._checked


class FakeDialog:
    """Dialog tiruan yang bisa diselesaikan secara manual dari test."""

    def __init__(self, remember_default: bool = True) -> None:
        self.finished = _FakeSignal()
        self.remember = _FakeCheckbox(remember_default)

    def open(self) -> None:
        pass  # test memanggil `finish()` secara eksplisit

    def finish(self, result: int) -> None:
        self.finished.emit(result)


class FakeDialogFactory:
    def __init__(self, remember_default: bool = True) -> None:
        self.instances: list[FakeDialog] = []
        self._remember = remember_default

    def __call__(self, origin, feature_display, parent):
        dlg = FakeDialog(self._remember)
        dlg.origin = origin
        dlg.feature_display = feature_display
        self.instances.append(dlg)
        return dlg


# ══════════════════════════════════════════════════════════════════════
#  Fixtures
# ══════════════════════════════════════════════════════════════════════
@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setattr("frame.store.data_dir", lambda: tmp_path)
    from frame.store import Store
    s = Store()
    yield s
    s._timer.stop()


@pytest.fixture
def manager(store):
    parent = QWidget()
    factory = FakeDialogFactory()
    mgr = PermissionManager(
        store, parent, persist=True, dialog_factory=factory,
    )
    mgr._test_factory = factory  # type: ignore[attr-defined]
    yield mgr
    parent.deleteLater()


@pytest.fixture
def private_manager(store):
    """PermissionManager dengan persist=False (mode penyamaran)."""
    parent = QWidget()
    factory = FakeDialogFactory()
    mgr = PermissionManager(
        store, parent, persist=False, dialog_factory=factory,
    )
    mgr._test_factory = factory  # type: ignore[attr-defined]
    yield mgr
    parent.deleteLater()


# ══════════════════════════════════════════════════════════════════════
#  A. _origin_key
# ══════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("url,expected", [
    ("https://example.com/",        "https://example.com"),
    ("https://example.com:443/x",   "https://example.com"),
    ("https://example.com:8443/x",  "https://example.com:8443"),
    ("http://example.com",          "http://example.com"),
    ("http://example.com:80/x",     "http://example.com"),
    ("http://example.com:8080/x",   "http://example.com:8080"),
    ("https://EXAMPLE.COM/",        "https://example.com"),
    ("https://Sub.Example.Com/",    "https://sub.example.com"),
])
def test_origin_key(url, expected):
    assert _origin_key(QUrl(url)) == expected


@pytest.mark.parametrize("url", [
    "about:blank",
    "data:text/html,<p>x</p>",
    "",
])
def test_origin_key_invalid_url(url):
    assert _origin_key(QUrl(url)) == ""


def test_origin_key_none():
    assert _origin_key(None) == ""


# ══════════════════════════════════════════════════════════════════════
#  B. _feature_name
# ══════════════════════════════════════════════════════════════════════
def test_feature_name_known():
    # Semua anggota Qt Feature yang kita harapkan terdaftar.
    for attr, key in [
        ("MediaAudioCapture", "media_audio_capture"),
        ("MediaVideoCapture", "media_video_capture"),
        ("Geolocation", "geolocation"),
        ("Notifications", "notifications"),
    ]:
        member = getattr(QWebEnginePage.Feature, attr, None)
        if member is None:
            pytest.skip(f"Feature {attr} tidak ada di Qt versi ini")
        assert _feature_name(member) == key


def test_feature_name_unknown_returns_none():
    assert _feature_name(object()) is None


def test_feature_names_are_strings():
    for member, key in FEATURE_NAMES.items():
        assert isinstance(key, str)
        assert key  # tidak boleh kosong


# ══════════════════════════════════════════════════════════════════════
#  C. handle_request — decision logic tanpa dialog
# ══════════════════════════════════════════════════════════════════════
def test_handle_request_always_deny_desktop(manager):
    page = FakePage()
    origin = QUrl("https://example.com")
    feature = QWebEnginePage.Feature.DesktopVideoCapture

    manager.handle_request(page, origin, feature)

    assert len(page.calls) == 1
    _, _, policy = page.calls[0]
    assert policy == QWebEnginePage.PermissionPolicy.PermissionDeniedByUser
    # Dialog tidak boleh muncul
    assert manager._test_factory.instances == []


def test_handle_request_no_origin_denies(manager):
    page = FakePage()
    manager.handle_request(
        page, QUrl("about:blank"),
        QWebEnginePage.Feature.MediaAudioCapture,
    )
    assert len(page.calls) == 1
    assert page.calls[0][2] == (
        QWebEnginePage.PermissionPolicy.PermissionDeniedByUser
    )


def test_handle_request_remembered_granted(manager):
    manager.store.set_permission(
        "https://example.com", "media_audio_capture", "granted",
    )
    page = FakePage()
    manager.handle_request(
        page, QUrl("https://example.com"),
        QWebEnginePage.Feature.MediaAudioCapture,
    )
    assert len(page.calls) == 1
    assert page.calls[0][2] == (
        QWebEnginePage.PermissionPolicy.PermissionGrantedByUser
    )
    assert manager._test_factory.instances == []


def test_handle_request_remembered_denied(manager):
    manager.store.set_permission(
        "https://example.com", "media_video_capture", "denied",
    )
    page = FakePage()
    manager.handle_request(
        page, QUrl("https://example.com"),
        QWebEnginePage.Feature.MediaVideoCapture,
    )
    assert len(page.calls) == 1
    assert page.calls[0][2] == (
        QWebEnginePage.PermissionPolicy.PermissionDeniedByUser
    )
    assert manager._test_factory.instances == []


def test_handle_request_unknown_shows_dialog(manager):
    page = FakePage()
    manager.handle_request(
        page, QUrl("https://example.com"),
        QWebEnginePage.Feature.MediaAudioCapture,
    )
    # Dialog muncul, belum apply
    assert len(manager._test_factory.instances) == 1
    assert page.calls == []


# ══════════════════════════════════════════════════════════════════════
#  D. Dialog lifecycle
# ══════════════════════════════════════════════════════════════════════
def test_dialog_allow_persists(manager):
    page = FakePage()
    manager.handle_request(
        page, QUrl("https://example.com"),
        QWebEnginePage.Feature.MediaAudioCapture,
    )
    dlg = manager._test_factory.instances[0]
    dlg.finish(QDialog.DialogCode.Accepted)

    assert len(page.calls) == 1
    assert page.calls[0][2] == (
        QWebEnginePage.PermissionPolicy.PermissionGrantedByUser
    )
    assert manager.store.get_permission(
        "https://example.com", "media_audio_capture"
    ) == "granted"


def test_dialog_deny_persists(manager):
    page = FakePage()
    manager.handle_request(
        page, QUrl("https://example.com"),
        QWebEnginePage.Feature.MediaVideoCapture,
    )
    dlg = manager._test_factory.instances[0]
    dlg.finish(QDialog.DialogCode.Rejected)

    assert len(page.calls) == 1
    assert page.calls[0][2] == (
        QWebEnginePage.PermissionPolicy.PermissionDeniedByUser
    )
    assert manager.store.get_permission(
        "https://example.com", "media_video_capture"
    ) == "denied"


def test_dialog_allow_without_remember(store):
    """User memilih Allow tapi uncheck "Remember"."""
    parent = QWidget()
    factory = FakeDialogFactory(remember_default=False)
    mgr = PermissionManager(
        store, parent, persist=True, dialog_factory=factory,
    )
    page = FakePage()
    mgr.handle_request(
        page, QUrl("https://example.com"),
        QWebEnginePage.Feature.MediaAudioCapture,
    )
    dlg = factory.instances[0]
    dlg.finish(QDialog.DialogCode.Accepted)

    # Keputusan diterapkan tapi TIDAK disimpan
    assert page.calls[0][2] == (
        QWebEnginePage.PermissionPolicy.PermissionGrantedByUser
    )
    assert store.get_permission(
        "https://example.com", "media_audio_capture"
    ) is None
    parent.deleteLater()


def test_dialog_closed_without_choice_denies(manager):
    """User klik X → dialog.finished(Rejected) → deny."""
    page = FakePage()
    manager.handle_request(
        page, QUrl("https://example.com"),
        QWebEnginePage.Feature.Geolocation,
    )
    dlg = manager._test_factory.instances[0]
    dlg.finish(QDialog.DialogCode.Rejected)

    assert page.calls[0][2] == (
        QWebEnginePage.PermissionPolicy.PermissionDeniedByUser
    )


def test_dialog_active_cleared_after_finish(manager):
    page = FakePage()
    manager.handle_request(
        page, QUrl("https://example.com"),
        QWebEnginePage.Feature.MediaAudioCapture,
    )
    assert manager._active_dialog is not None
    manager._test_factory.instances[0].finish(
        QDialog.DialogCode.Accepted
    )
    assert manager._active_dialog is None


# ══════════════════════════════════════════════════════════════════════
#  E. Serialisasi — request kedua saat dialog terbuka
# ══════════════════════════════════════════════════════════════════════
def test_second_request_during_open_dialog_is_denied(manager):
    page1 = FakePage()
    page2 = FakePage()

    # Request pertama → dialog terbuka
    manager.handle_request(
        page1, QUrl("https://a.example.com"),
        QWebEnginePage.Feature.MediaAudioCapture,
    )
    assert len(manager._test_factory.instances) == 1

    # Request kedua → langsung deny tanpa dialog baru
    manager.handle_request(
        page2, QUrl("https://b.example.com"),
        QWebEnginePage.Feature.MediaAudioCapture,
    )
    assert len(manager._test_factory.instances) == 1  # masih satu
    assert page2.calls[0][2] == (
        QWebEnginePage.PermissionPolicy.PermissionDeniedByUser
    )
    assert page1.calls == []  # page1 masih menunggu


def test_request_accepted_after_first_dialog_closes(manager):
    """Setelah dialog pertama ditutup, request baru boleh prompt lagi."""
    page1 = FakePage()
    manager.handle_request(
        page1, QUrl("https://a.example.com"),
        QWebEnginePage.Feature.MediaAudioCapture,
    )
    manager._test_factory.instances[0].finish(
        QDialog.DialogCode.Accepted
    )

    page2 = FakePage()
    manager.handle_request(
        page2, QUrl("https://b.example.com"),
        QWebEnginePage.Feature.MediaAudioCapture,
    )
    assert len(manager._test_factory.instances) == 2


# ══════════════════════════════════════════════════════════════════════
#  F. Persistence — normal vs private
# ══════════════════════════════════════════════════════════════════════
def test_private_manager_does_not_persist(private_manager):
    page = FakePage()
    private_manager.handle_request(
        page, QUrl("https://example.com"),
        QWebEnginePage.Feature.MediaAudioCapture,
    )
    dlg = private_manager._test_factory.instances[0]
    dlg.finish(QDialog.DialogCode.Accepted)

    # Tidak ada tulisan ke store
    assert private_manager.store.get_permission(
        "https://example.com", "media_audio_capture"
    ) is None
    # Tapi keputusan tetap diingat dalam sesi ini
    page2 = FakePage()
    private_manager.handle_request(
        page2, QUrl("https://example.com"),
        QWebEnginePage.Feature.MediaAudioCapture,
    )
    assert page2.calls[0][2] == (
        QWebEnginePage.PermissionPolicy.PermissionGrantedByUser
    )
    assert private_manager._test_factory.instances == [
        private_manager._test_factory.instances[0]  # tidak ada dialog baru
    ]


def test_private_managers_do_not_share_memory(store):
    parent_a = QWidget()
    parent_b = QWidget()
    mgr_a = PermissionManager(
        store, parent_a, persist=False,
        dialog_factory=FakeDialogFactory(),
    )
    mgr_b = PermissionManager(
        store, parent_b, persist=False,
        dialog_factory=FakeDialogFactory(),
    )
    mgr_a._memory[("https://example.com", "media_audio_capture")] = "granted"

    page = FakePage()
    mgr_b.handle_request(
        page, QUrl("https://example.com"),
        QWebEnginePage.Feature.MediaAudioCapture,
    )
    # mgr_b tidak tahu apa-apa tentang keputusan mgr_a → dialog
    assert page.calls == []
    parent_a.deleteLater()
    parent_b.deleteLater()


def test_private_reads_not_from_store(store):
    """Store punya keputusan, tapi private manager mengabaikannya."""
    store.set_permission(
        "https://example.com", "media_audio_capture", "granted"
    )
    parent = QWidget()
    factory = FakeDialogFactory()
    mgr = PermissionManager(
        store, parent, persist=False, dialog_factory=factory,
    )
    page = FakePage()
    mgr.handle_request(
        page, QUrl("https://example.com"),
        QWebEnginePage.Feature.MediaAudioCapture,
    )
    # Harus muncul dialog, bukan langsung grant
    assert len(factory.instances) == 1
    assert page.calls == []
    parent.deleteLater()


# ══════════════════════════════════════════════════════════════════════
#  G. Store permission methods
# ══════════════════════════════════════════════════════════════════════
def test_store_get_permission_default_none(store):
    assert store.get_permission("https://example.com", "camera") is None


def test_store_set_and_get(store):
    store.set_permission("https://example.com", "camera", "granted")
    assert store.get_permission("https://example.com", "camera") == "granted"


def test_store_set_invalid_policy_ignored(store):
    store.set_permission("https://example.com", "camera", "maybe")
    assert store.get_permission("https://example.com", "camera") is None


def test_store_set_empty_origin_ignored(store):
    store.set_permission("", "camera", "granted")
    assert store.all_permissions() == {}


def test_store_clear_single_feature(store):
    store.set_permission("https://example.com", "camera", "granted")
    store.set_permission("https://example.com", "microphone", "denied")
    store.clear_permission("https://example.com", "camera")

    assert store.get_permission("https://example.com", "camera") is None
    assert store.get_permission(
        "https://example.com", "microphone"
    ) == "denied"


def test_store_clear_origin(store):
    store.set_permission("https://a.com", "camera", "granted")
    store.set_permission("https://a.com", "microphone", "denied")
    store.set_permission("https://b.com", "camera", "granted")

    store.clear_permission("https://a.com")

    assert store.get_permission("https://a.com", "camera") is None
    assert store.get_permission("https://a.com", "microphone") is None
    assert store.get_permission("https://b.com", "camera") == "granted"


def test_store_clear_all(store):
    store.set_permission("https://a.com", "camera", "granted")
    store.set_permission("https://b.com", "camera", "denied")
    store.clear_all_permissions()
    assert store.all_permissions() == {}


def test_store_all_permissions_returns_copy(store):
    store.set_permission("https://a.com", "camera", "granted")
    copy = store.all_permissions()
    copy["https://a.com"]["camera"] = "denied"
    copy["https://c.com"] = {"x": "granted"}

    # Mutasi pada copy tidak mempengaruhi store
    assert store.get_permission("https://a.com", "camera") == "granted"
    assert store.get_permission("https://c.com", "x") is None


def test_store_sanitizes_garbage_permissions(tmp_path, monkeypatch):
    (tmp_path / "frame_data.json").write_text(json.dumps({
        "settings": {
            "permissions": "ini bukan dict",
        },
    }), "utf-8")
    monkeypatch.setattr("frame.store.data_dir", lambda: tmp_path)

    from frame.store import Store
    s = Store()
    try:
        assert s.all_permissions() == {}
        # Bisa dipakai normal setelah sanitize
        s.set_permission("https://a.com", "camera", "granted")
        assert s.get_permission("https://a.com", "camera") == "granted"
    finally:
        s._timer.stop()


def test_store_sanitizes_bad_entry_values(tmp_path, monkeypatch):
    (tmp_path / "frame_data.json").write_text(json.dumps({
        "settings": {
            "permissions": {
                "https://a.com": {
                    "camera": "granted",
                    "microphone": "maybe",     # nilai invalid
                    "geolocation": 42,          # tipe invalid
                },
                "https://b.com": "bukan dict",     # entry invalid
                "https://c.com": {
                    "camera": "denied",
                },
            },
        },
    }), "utf-8")
    monkeypatch.setattr("frame.store.data_dir", lambda: tmp_path)

    from frame.store import Store
    s = Store()
    try:
        assert s.get_permission("https://a.com", "camera") == "granted"
        assert s.get_permission("https://a.com", "microphone") is None
        assert s.get_permission("https://a.com", "geolocation") is None
        assert s.get_permission("https://b.com", "camera") is None
        assert s.get_permission("https://c.com", "camera") == "denied"
    finally:
        s._timer.stop()


def test_store_permissions_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr("frame.store.data_dir", lambda: tmp_path)
    from frame.store import Store
    s1 = Store()
    s1.set_permission("https://example.com", "camera", "granted")
    s1.set_permission("https://other.com", "microphone", "denied")
    s1.flush()

    s2 = Store()
    try:
        assert s2.get_permission("https://example.com", "camera") == "granted"
        assert s2.get_permission("https://other.com", "microphone") == "denied"
    finally:
        s1._timer.stop()
        s2._timer.stop()