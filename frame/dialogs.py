"""All dialogs: Bookmarks, History, Downloads, Settings."""
from __future__ import annotations

from collections import deque
from pathlib import Path

from PyQt6.QtCore import QEvent, Qt, QUrl, QTimer, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWebEngineCore import (
    QWebEngineDownloadRequest,
    QWebEngineProfile,
)
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
    QFormLayout, QFrame, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMessageBox, QPlainTextEdit,
    QProgressBar, QPushButton, QScrollArea, QSizePolicy, QSlider,
    QSpinBox, QVBoxLayout, QWidget,
)

from .core import (
    DEFAULT_HOME, SEARCH_ENGINES, detect_total_ram_gb, fmt_time,
    human_size, human_speed, log,
)
from .theme import apply_theme


# Neutral secondary text color — readable on dark (#202124) and light (#f1f3f4).
_MUTED = "#808080"


# ══════════════════════════════════════════════════════════════════════
#  Wheel-safe slider
# ══════════════════════════════════════════════════════════════════════
class _WheelSafeSlider(QSlider):
    """QSlider yang tidak responsif terhadap scroll touchpad kecuali fokus.

    Saat tidak fokus: wheel event di-continue ke parent (QScrollArea) supaya
    scroll halaman tetap jalan — user tidak "kehilangan" scroll-nya.
    Saat fokus (user klik dulu): wheel berfungsi normal untuk adjust nilai.
    """

    def wheelEvent(self, event) -> None:
        if self.hasFocus():
            super().wheelEvent(event)
        else:
            # Teruskan ke parent (QScrollArea) secara eksplisit —
            # event.ignore() saja tidak selalu propagate di PyQt6.
            event.ignore()
            parent = self.parent()
            if parent is not None:
                parent.event(event)


# ══════════════════════════════════════════════════════════════════════
#  Bookmarks
# ══════════════════════════════════════════════════════════════════════
class BookmarksDialog(QDialog):
    open_requested = pyqtSignal(QUrl)

    def __init__(self, store, parent=None) -> None:
        super().__init__(parent)
        self.store = store
        self.setWindowTitle("Bookmarks")
        self.resize(620, 460)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search bookmarks…")
        self.search.textChanged.connect(self.refresh)
        lay.addWidget(self.search)

        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(self._open_item)
        lay.addWidget(self.list, 1)

        row = QHBoxLayout()
        open_btn = QPushButton("Open"); open_btn.clicked.connect(self._open_selected)
        del_btn = QPushButton("Delete"); del_btn.clicked.connect(self._delete_selected)
        close_btn = QPushButton("Close"); close_btn.clicked.connect(self.close)
        row.addWidget(open_btn); row.addWidget(del_btn)
        row.addStretch(1); row.addWidget(close_btn)
        lay.addLayout(row)

        self.store.bookmarks_changed.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        needle = self.search.text().strip().lower()
        self.list.clear()
        for bm in reversed(self.store.bookmarks):
            if needle and needle not in bm["title"].lower() and needle not in bm["url"].lower():
                continue
            item = QListWidgetItem(f"{bm['title']}\n{bm['url']}")
            item.setData(Qt.ItemDataRole.UserRole, bm["url"])
            item.setToolTip(bm["url"])
            self.list.addItem(item)
        if self.list.count() == 0:
            self.list.addItem(QListWidgetItem("No bookmarks yet."))

    def _open_item(self, item):
        url = item.data(Qt.ItemDataRole.UserRole)
        if url:
            self.open_requested.emit(QUrl(url))

    def _open_selected(self):
        item = self.list.currentItem()
        if item:
            self._open_item(item)

    def _delete_selected(self):
        item = self.list.currentItem()
        if not item:
            return
        url = item.data(Qt.ItemDataRole.UserRole)
        if url:
            self.store.remove_bookmark(url)


# ══════════════════════════════════════════════════════════════════════
#  History
# ══════════════════════════════════════════════════════════════════════
class HistoryDialog(QDialog):
    open_requested = pyqtSignal(QUrl)

    def __init__(self, store, parent=None) -> None:
        super().__init__(parent)
        self.store = store
        self.setWindowTitle("Browsing History")
        self.resize(680, 500)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search history…")
        self.search.textChanged.connect(self.refresh)
        lay.addWidget(self.search)

        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(self._open_item)
        lay.addWidget(self.list, 1)

        row = QHBoxLayout()
        open_btn = QPushButton("Open"); open_btn.clicked.connect(self._open_selected)
        del_btn = QPushButton("Delete selected"); del_btn.clicked.connect(self._delete_selected)
        clear_btn = QPushButton("Delete all"); clear_btn.clicked.connect(self._clear_all)
        close_btn = QPushButton("Close"); close_btn.clicked.connect(self.close)
        row.addWidget(open_btn); row.addWidget(del_btn); row.addWidget(clear_btn)
        row.addStretch(1); row.addWidget(close_btn)
        lay.addLayout(row)

        self.refresh()

    def refresh(self) -> None:
        needle = self.search.text().strip().lower()
        self.list.clear()
        shown = 0
        for h in reversed(self.store.history):
            if needle and needle not in h["title"].lower() and needle not in h["url"].lower():
                continue
            item = QListWidgetItem(f"{h['title']}\n{h['url']}\n{fmt_time(h['time'])}")
            item.setData(Qt.ItemDataRole.UserRole, h["url"])
            self.list.addItem(item)
            shown += 1
            if shown >= 1000:
                break
        if shown == 0:
            self.list.addItem(QListWidgetItem("No history."))

    def _open_item(self, item):
        url = item.data(Qt.ItemDataRole.UserRole)
        if url:
            self.open_requested.emit(QUrl(url))

    def _open_selected(self):
        item = self.list.currentItem()
        if item:
            self._open_item(item)

    def _delete_selected(self):
        item = self.list.currentItem()
        if not item:
            return
        url = item.data(Qt.ItemDataRole.UserRole)
        if not url:
            return
        self.store.history = deque(
            (h for h in self.store.history if h["url"] != url),
            maxlen=self.store.MAX_HISTORY,
        )
        self.store.save()
        self.refresh()

    def _clear_all(self):
        if QMessageBox.question(
            self, "Delete history", "Delete all browsing history?"
        ) == QMessageBox.StandardButton.Yes:
            self.store.clear_history()
            self.refresh()


# ══════════════════════════════════════════════════════════════════════
#  Downloads
# ══════════════════════════════════════════════════════════════════════
class DownloadItemWidget(QFrame):
    def __init__(self, req: QWebEngineDownloadRequest, parent=None) -> None:
        super().__init__(parent)
        import time
        self.req = req
        self._last_bytes = req.receivedBytes()
        self._last_time = time.monotonic()
        self.speed = 0.0
        self._finished = False

        self.setFrameShape(QFrame.Shape.StyledPanel)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(6)

        top = QHBoxLayout()
        self.name = QLabel(req.downloadFileName())
        self.name.setStyleSheet("font-weight: 600;")
        self.name.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        top.addWidget(self.name, 1)

        self.pause_btn = QPushButton("Pause"); self.pause_btn.setFixedWidth(64)
        self.pause_btn.clicked.connect(self._toggle_pause)
        top.addWidget(self.pause_btn)

        self.cancel_btn = QPushButton("Cancel"); self.cancel_btn.setFixedWidth(64)
        self.cancel_btn.clicked.connect(self._cancel)
        top.addWidget(self.cancel_btn)
        lay.addLayout(top)

        self.bar = QProgressBar(); self.bar.setFixedHeight(8)
        self.bar.setTextVisible(False); self.bar.setRange(0, 100)
        lay.addWidget(self.bar)

        bottom = QHBoxLayout()
        self.status = QLabel("Waiting…")
        self.status.setStyleSheet(f"font-size: 11px; color: {_MUTED};")
        bottom.addWidget(self.status, 1)

        self.open_btn = QPushButton("Open"); self.open_btn.setFixedWidth(64)
        self.open_btn.setEnabled(False); self.open_btn.clicked.connect(self._open_file)
        bottom.addWidget(self.open_btn)

        self.folder_btn = QPushButton("Folder"); self.folder_btn.setFixedWidth(64)
        self.folder_btn.clicked.connect(self._open_folder)
        bottom.addWidget(self.folder_btn)
        lay.addLayout(bottom)

        self.req.receivedBytesChanged.connect(self._on_progress)
        self.req.totalBytesChanged.connect(self._on_progress)
        self.req.stateChanged.connect(self._on_state)
        self.req.isPausedChanged.connect(self._on_progress)
        self._on_state()

    def path(self) -> Path:
        return Path(self.req.downloadDirectory()) / self.req.downloadFileName()

    def _on_progress(self):
        total = self.req.totalBytes()
        got = self.req.receivedBytes()
        if total > 0:
            self.bar.setRange(0, 100)
            self.bar.setValue(int(got * 100 / total))
        else:
            self.bar.setRange(0, 0)
        self._update_status()

    def _update_status(self):
        state = self.req.state()
        got = self.req.receivedBytes()
        total = self.req.totalBytes()
        if state == QWebEngineDownloadRequest.DownloadState.DownloadCompleted:
            self.status.setText(f"Done · {human_size(got)}"); return
        if state == QWebEngineDownloadRequest.DownloadState.DownloadCancelled:
            self.status.setText("Cancelled"); return
        if state == QWebEngineDownloadRequest.DownloadState.DownloadInterrupted:
            self.status.setText(f"Failed: {self.req.interruptReasonString()}"); return
        if self.req.isPaused():
            self.status.setText(f"PAUSED · {human_size(got)} / {human_size(total)}"); return
        size_txt = f"{human_size(got)} / {human_size(total)}" if total > 0 else human_size(got)
        self.status.setText(f"{size_txt} · {human_speed(self.speed)}")

    def _on_state(self):
        state = self.req.state()
        if state == QWebEngineDownloadRequest.DownloadState.DownloadCompleted:
            self._finished = True
            self.bar.setRange(0, 100); self.bar.setValue(100)
            self.pause_btn.setEnabled(False); self.cancel_btn.setEnabled(False)
            self.open_btn.setEnabled(True)
        elif state in (
            QWebEngineDownloadRequest.DownloadState.DownloadCancelled,
            QWebEngineDownloadRequest.DownloadState.DownloadInterrupted,
        ):
            self.pause_btn.setEnabled(False); self.cancel_btn.setEnabled(False)
            self.bar.setRange(0, 100); self.bar.setValue(0)
        self._update_status()

    def tick(self):
        import time
        if self._finished or self.req.isPaused():
            return
        now = time.monotonic()
        dt = now - self._last_time
        if dt < 0.35:
            return
        got = self.req.receivedBytes()
        self.speed = max(0.0, (got - self._last_bytes) / dt)
        self._last_bytes = got
        self._last_time = now
        self._on_progress()

    def _toggle_pause(self):
        if self.req.isPaused():
            self.req.resume(); self.pause_btn.setText("Pause")
        else:
            self.req.pause(); self.pause_btn.setText("Resume")

    def _cancel(self):
        self.req.cancel()

    def _open_file(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.path())))

    def _open_folder(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.req.downloadDirectory()))


class DownloadsDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Downloads")
        self.resize(560, 440)
        self.items: list[DownloadItemWidget] = []

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("Downloads")
        title.setStyleSheet("font-size: 15px; font-weight: 600;")
        header.addWidget(title); header.addStretch(1)
        clear_btn = QPushButton("Clear finished")
        clear_btn.clicked.connect(self.clear_finished)
        header.addWidget(clear_btn)
        lay.addLayout(header)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        container = QWidget()
        self.vbox = QVBoxLayout(container)
        self.vbox.setContentsMargins(0, 0, 8, 0)
        self.vbox.setSpacing(8); self.vbox.addStretch(1)
        self.scroll.setWidget(container)
        lay.addWidget(self.scroll, 1)

        self.empty_label = QLabel("No downloads yet.")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setStyleSheet(f"color: {_MUTED};")
        self.vbox.insertWidget(0, self.empty_label)

        self._timer = QTimer(self)
        self._timer.setInterval(600)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def add_download(self, req, show: bool = True) -> None:
        self.empty_label.hide()
        w = DownloadItemWidget(req)
        self.vbox.insertWidget(self.vbox.count() - 1, w)
        self.items.append(w)
        if show:
            self.show(); self.raise_(); self.activateWindow()

    def _tick(self):
        for w in list(self.items):
            w.tick()

    def clear_finished(self):
        for w in list(self.items):
            if w._finished or w.req.state() in (
                QWebEngineDownloadRequest.DownloadState.DownloadCancelled,
                QWebEngineDownloadRequest.DownloadState.DownloadInterrupted,
            ):
                self.vbox.removeWidget(w)
                w.setParent(None); w.deleteLater()
                self.items.remove(w)
        if not self.items:
            self.empty_label.show()


# ══════════════════════════════════════════════════════════════════════
#  Settings
# ══════════════════════════════════════════════════════════════════════
class SettingsDialog(QDialog):
    settings_saved = pyqtSignal()

    def __init__(self, store, profile: QWebEngineProfile, parent=None) -> None:
        super().__init__(parent)
        self.store = store
        self.profile = profile
        self.setWindowTitle("Settings")

        screen = self.screen()
        if screen is not None:
            avail = screen.availableGeometry()
            w = min(780, max(580, avail.width() - 100))
            h = min(860, max(520, avail.height() - 120))
            self.resize(w, h)
        else:
            self.resize(780, 760)
        self.setMinimumSize(580, 520)

        self._old_low_end = store.settings.get("low_end_mode", False)

        s = store.settings
        glow_mode = s.get("window_glow", "rgb")
        self._initial_theme = s.get("theme", "dark")
        self._initial_glow = {
            "enabled": glow_mode != "off",
            "mode": glow_mode if glow_mode in ("rgb", "static") else "rgb",
            "width": s.get("window_glow_width", 1),
            "taper": s.get("window_glow_taper", 0.4),
            "light_style": s.get("window_glow_light_style", "solid"),
            "light_sat": s.get("window_glow_light_sat", 0.95),
            "light_lightness": s.get("window_glow_light_lightness", 0.32),
        }
        self._dirty = False

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        inner = QWidget()
        inner_lay = QVBoxLayout(inner)
        inner_lay.setContentsMargins(4, 4, 12, 4)
        inner_lay.setSpacing(14)

        # ── General ────────────────────────────────────────────────
        gb_general = QGroupBox("General")
        form_general = QFormLayout(gb_general)
        form_general.setContentsMargins(14, 18, 14, 14)
        form_general.setHorizontalSpacing(14)
        form_general.setVerticalSpacing(10)
        form_general.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )
        form_general.setLabelAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        form_general.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)

        self.engine = QComboBox()
        self.engine.addItems(list(SEARCH_ENGINES.keys()))
        self.engine.setCurrentText(s.get("search_engine", "Google"))
        self.engine.setMinimumWidth(180)
        self.engine.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        form_general.addRow("Search engine", self.engine)

        self.homepage = QLineEdit(s.get("homepage", DEFAULT_HOME))
        self.homepage.setMinimumWidth(180)
        self.homepage.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        form_general.addRow("Homepage", self.homepage)

        dl_wrap = QWidget()
        dl_row = QHBoxLayout(dl_wrap)
        dl_row.setContentsMargins(0, 0, 0, 0)
        dl_row.setSpacing(6)
        self.dl_dir = QLineEdit(s.get("download_dir", ""))
        self.dl_dir.setMinimumWidth(120)
        dl_row.addWidget(self.dl_dir, 1)
        browse = QPushButton("Choose…")
        browse.setFixedWidth(90)
        browse.clicked.connect(self._pick_dir)
        dl_row.addWidget(browse, 0)
        form_general.addRow("Download folder", dl_wrap)

        self.theme = QComboBox()
        self.theme.addItems(["dark", "light"])
        self.theme.setCurrentText(s.get("theme", "dark"))
        self.theme.setMinimumWidth(180)
        self.theme.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        form_general.addRow("Theme", self.theme)

        self.theme.currentTextChanged.connect(self._preview_theme)

        inner_lay.addWidget(gb_general)

        # ── Privacy ────────────────────────────────────────────────
        gb_priv = QGroupBox("Privacy")
        pv = QVBoxLayout(gb_priv)
        pv.setContentsMargins(14, 18, 14, 14)
        pv.setSpacing(8)

        self.chk_history = QCheckBox("Save browsing history")
        self.chk_history.setChecked(s.get("save_history", True))
        pv.addWidget(self.chk_history)

        self.chk_restore = QCheckBox("Restore last session on start")
        self.chk_restore.setChecked(s.get("restore_session", True))
        pv.addWidget(self.chk_restore)

        self.chk_clear = QCheckBox(
            "Clear cache, cookies & history on exit"
        )
        self.chk_clear.setChecked(s.get("clear_on_exit", False))
        pv.addWidget(self.chk_clear)

        self.chk_adblock = QCheckBox(
            "Enable AdBlocker (block ads & trackers)"
        )
        self.chk_adblock.setChecked(s.get("adblock_enabled", True))
        pv.addWidget(self.chk_adblock)

        data_row = QHBoxLayout()
        data_row.setSpacing(6)
        clear_cache = QPushButton("Clear cache")
        clear_cache.clicked.connect(self._clear_cache)
        clear_cookies = QPushButton("Clear cookies")
        clear_cookies.clicked.connect(self._clear_cookies)
        clear_hist = QPushButton("Clear history")
        clear_hist.clicked.connect(self._clear_history)
        data_row.addWidget(clear_cache)
        data_row.addWidget(clear_cookies)
        data_row.addWidget(clear_hist)
        data_row.addStretch(1)
        pv.addLayout(data_row)

        inner_lay.addWidget(gb_priv)

        # ── Performance ────────────────────────────────────────────
        gb_perf = QGroupBox("Performance & Resources")
        pf = QVBoxLayout(gb_perf)
        pf.setContentsMargins(14, 18, 14, 14)
        pf.setSpacing(8)

        ram_gb = detect_total_ram_gb()
        info_text = (
            f"Detected RAM: <b>{ram_gb:.1f} GB</b>"
            if ram_gb is not None
            else "RAM cannot be detected automatically."
        )
        lbl_info = QLabel(info_text)
        lbl_info.setStyleSheet(f"font-size: 11px; color: {_MUTED};")
        pf.addWidget(lbl_info)

        self.chk_low_end = QCheckBox("Low Power Mode (requires restart)")
        self.chk_low_end.setChecked(s.get("low_end_mode", False))
        pf.addWidget(self.chk_low_end)

        lbl_hint = QLabel(
            "Reduces RAM and CPU usage on low-spec laptops. "
            "Effects: WebGL and PDF viewer disabled, renderer processes limited."
        )
        lbl_hint.setWordWrap(True)
        lbl_hint.setStyleSheet(
            f"font-size: 11px; color: {_MUTED}; margin-left: 22px;"
        )
        pf.addWidget(lbl_hint)

        self.chk_show_bookmarks = QCheckBox("Show bookmark bar")
        self.chk_show_bookmarks.setChecked(s.get("show_bookmark_bar", True))
        pf.addWidget(self.chk_show_bookmarks)

        row_tabs = QHBoxLayout()
        row_tabs.setSpacing(10)
        row_tabs.addWidget(QLabel("Max tabs:"))
        self.spin_max_tabs = QSpinBox()
        self.spin_max_tabs.setRange(1, 100)
        self.spin_max_tabs.setValue(s.get("max_tabs", 30))
        self.spin_max_tabs.setFixedWidth(110)
        row_tabs.addWidget(self.spin_max_tabs)
        row_tabs.addStretch(1)
        pf.addLayout(row_tabs)

        inner_lay.addWidget(gb_perf)

        # ── Window Glow ────────────────────────────────────────────
        gb_glow = QGroupBox("Window Glow")
        gl = QVBoxLayout(gb_glow)
        gl.setContentsMargins(14, 18, 14, 14)
        gl.setSpacing(10)

        self.chk_glow = QCheckBox("Enable glow border")
        self.chk_glow.setChecked(self._initial_glow["enabled"])
        gl.addWidget(self.chk_glow)

        # Mode
        row_mode = QHBoxLayout()
        row_mode.setSpacing(10)
        row_mode.addWidget(QLabel("Mode:"))
        self.cmb_glow_mode = QComboBox()
        self.cmb_glow_mode.addItems(["rgb", "static"])
        self.cmb_glow_mode.setCurrentText(self._initial_glow["mode"])
        self.cmb_glow_mode.setFixedWidth(140)
        row_mode.addWidget(self.cmb_glow_mode)
        row_mode.addStretch(1)
        gl.addLayout(row_mode)

        # Thickness (glow width)
        row_width = QHBoxLayout()
        row_width.setSpacing(10)
        lbl_width = QLabel("Thickness:")
        lbl_width.setFixedWidth(90)
        row_width.addWidget(lbl_width)
        self.sld_width = _WheelSafeSlider(Qt.Orientation.Horizontal)
        self.sld_width.setRange(1, 6)
        self.sld_width.setValue(int(self._initial_glow["width"]))
        self.sld_width.setTickInterval(1)
        self.sld_width.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.sld_width.setToolTip(
            "Ketebalan garis glow di tepi atas (1-6 px)."
        )
        self.lbl_width_val = QLabel(f"{self.sld_width.value()} px")
        self.lbl_width_val.setFixedWidth(48)
        self.lbl_width_val.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        row_width.addWidget(self.sld_width, 1)
        row_width.addWidget(self.lbl_width_val)
        gl.addLayout(row_width)

        # Length (taper)
        row_taper = QHBoxLayout()
        row_taper.setSpacing(10)
        lbl_taper = QLabel("Length:")
        lbl_taper.setFixedWidth(90)
        row_taper.addWidget(lbl_taper)
        self.sld_taper = _WheelSafeSlider(Qt.Orientation.Horizontal)
        self.sld_taper.setRange(5, 100)
        self.sld_taper.setValue(int(self._initial_glow["taper"] * 100))
        self.sld_taper.setToolTip(
            "Seberapa jauh glow turun dari atas (dalam persen tinggi window)."
        )
        self.lbl_taper_val = QLabel(f"{self.sld_taper.value()}%")
        self.lbl_taper_val.setFixedWidth(48)
        self.lbl_taper_val.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        row_taper.addWidget(self.sld_taper, 1)
        row_taper.addWidget(self.lbl_taper_val)
        gl.addLayout(row_taper)

        # Light mode section
        lbl_light_section = QLabel("Light mode:")
        lbl_light_section.setStyleSheet(
            f"color: {_MUTED}; font-size: 11px; margin-top: 4px;"
        )
        gl.addWidget(lbl_light_section)

        # Light style
        row_lstyle = QHBoxLayout()
        row_lstyle.setSpacing(10)
        lbl_lstyle = QLabel("Style:")
        lbl_lstyle.setFixedWidth(90)
        row_lstyle.addWidget(lbl_lstyle)
        self.cmb_light_style = QComboBox()
        self.cmb_light_style.addItems(["rgb", "solid"])
        self.cmb_light_style.setCurrentText(self._initial_glow["light_style"])
        self.cmb_light_style.setFixedWidth(140)
        self.cmb_light_style.setToolTip(
            "'rgb' = warna-warni, 'solid' = warna accent tema"
        )
        row_lstyle.addWidget(self.cmb_light_style)
        row_lstyle.addStretch(1)
        gl.addLayout(row_lstyle)

        # Light saturation
        row_lsat = QHBoxLayout()
        row_lsat.setSpacing(10)
        lbl_lsat = QLabel("Saturation:")
        lbl_lsat.setFixedWidth(90)
        row_lsat.addWidget(lbl_lsat)
        self.sld_light_sat = _WheelSafeSlider(Qt.Orientation.Horizontal)
        self.sld_light_sat.setRange(0, 100)
        self.sld_light_sat.setValue(int(self._initial_glow["light_sat"] * 100))
        self.sld_light_sat.setToolTip("Tinggi = warna kuat, rendah = pastel.")
        self.lbl_light_sat_val = QLabel(f"{self.sld_light_sat.value()}%")
        self.lbl_light_sat_val.setFixedWidth(48)
        self.lbl_light_sat_val.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        row_lsat.addWidget(self.sld_light_sat, 1)
        row_lsat.addWidget(self.lbl_light_sat_val)
        gl.addLayout(row_lsat)

        # Light lightness
        row_llight = QHBoxLayout()
        row_llight.setSpacing(10)
        lbl_llight = QLabel("Brightness:")
        lbl_llight.setFixedWidth(90)
        row_llight.addWidget(lbl_llight)
        self.sld_light_light = _WheelSafeSlider(Qt.Orientation.Horizontal)
        self.sld_light_light.setRange(0, 100)
        self.sld_light_light.setValue(
            int(self._initial_glow["light_lightness"] * 100)
        )
        self.sld_light_light.setToolTip(
            "Rendah = gelap & kontras, tinggi = terang (bisa menyatu "
            "dengan background putih)."
        )
        self.lbl_light_light_val = QLabel(f"{self.sld_light_light.value()}%")
        self.lbl_light_light_val.setFixedWidth(48)
        self.lbl_light_light_val.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        row_llight.addWidget(self.sld_light_light, 1)
        row_llight.addWidget(self.lbl_light_light_val)
        gl.addLayout(row_llight)

        # Hint
        lbl_glow_hint = QLabel(
            "Perubahan langsung terlihat. Klik Cancel untuk revert."
        )
        lbl_glow_hint.setWordWrap(True)
        lbl_glow_hint.setStyleSheet(
            f"font-size: 11px; color: {_MUTED}; margin-top: 4px;"
        )
        gl.addWidget(lbl_glow_hint)

        # Wire live preview
        self.chk_glow.stateChanged.connect(self._on_glow_control_changed)
        self.cmb_glow_mode.currentTextChanged.connect(self._on_glow_control_changed)
        self.cmb_light_style.currentTextChanged.connect(self._on_glow_control_changed)
        self.sld_width.valueChanged.connect(self._on_glow_control_changed)
        self.sld_taper.valueChanged.connect(self._on_glow_control_changed)
        self.sld_light_sat.valueChanged.connect(self._on_glow_control_changed)
        self.sld_light_light.valueChanged.connect(self._on_glow_control_changed)

        inner_lay.addWidget(gb_glow)

        # ── Sleeping tabs ──────────────────────────────────────────
        gb_susp = QGroupBox("Sleeping Tabs (Auto-Suspend)")
        sp = QVBoxLayout(gb_susp)
        sp.setContentsMargins(14, 18, 14, 14)
        sp.setSpacing(8)

        self.chk_autosuspend = QCheckBox(
            "Automatically sleep inactive tabs"
        )
        self.chk_autosuspend.setChecked(s.get("auto_suspend_tabs", True))
        sp.addWidget(self.chk_autosuspend)

        row_susp = QHBoxLayout()
        row_susp.setSpacing(10)
        row_susp.addWidget(QLabel("After idle for:"))
        self.spin_suspend = QSpinBox()
        self.spin_suspend.setRange(30, 3600)
        self.spin_suspend.setSingleStep(30)
        self.spin_suspend.setValue(s.get("suspend_after_sec", 180))
        self.spin_suspend.setSuffix(" sec")
        self.spin_suspend.setFixedWidth(130)
        row_susp.addWidget(self.spin_suspend)
        row_susp.addStretch(1)
        sp.addLayout(row_susp)

        self.chk_restore_scroll = QCheckBox(
            "Restore scroll position on wake"
        )
        self.chk_restore_scroll.setChecked(s.get("restore_scroll", True))
        sp.addWidget(self.chk_restore_scroll)

        self.chk_skip_dirty = QCheckBox(
            "Skip sleep for tabs with unsaved forms"
        )
        self.chk_skip_dirty.setChecked(s.get("suspend_skip_dirty_form", True))
        self.chk_skip_dirty.setToolTip(
            "Detects input/textarea/select with values different from defaults.\n"
            "Useful to prevent losing drafts on sites not in the whitelist."
        )
        sp.addWidget(self.chk_skip_dirty)

        sp.addWidget(QLabel(
            "Pinned tabs and domains below are never slept."
        ))

        sp.addWidget(QLabel(
            "Domain whitelist (one per line, never slept):"
        ))
        self.wl_edit = QPlainTextEdit()
        self.wl_edit.setFixedHeight(110)
        self.wl_edit.setPlaceholderText(
            "mail.google.com\ndocs.google.com\narxiv.org"
        )
        self.wl_edit.setPlainText("\n".join(s.get("suspend_whitelist", [])))
        sp.addWidget(self.wl_edit)

        inner_lay.addWidget(gb_susp)
        inner_lay.addStretch(1)

        scroll.setWidget(inner)
        lay.addWidget(scroll, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        save_btn = buttons.button(QDialogButtonBox.StandardButton.Save)
        if save_btn is not None:
            save_btn.setText("Save")
        cancel_btn = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_btn is not None:
            cancel_btn.setText("Cancel")
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

        self._connect_dirty_tracking()
        self._update_glow_controls_enabled()

    # ── Glow helpers ───────────────────────────────────────────────
    def _glow_widget(self):
        parent = self.parent()
        return getattr(parent, "glow", None)

    def _update_glow_controls_enabled(self) -> None:
        enabled = self.chk_glow.isChecked()
        for w in (
            self.cmb_glow_mode,
            self.sld_width,
            self.lbl_width_val,
            self.sld_taper,
            self.lbl_taper_val,
            self.cmb_light_style,
            self.sld_light_sat,
            self.lbl_light_sat_val,
            self.sld_light_light,
            self.lbl_light_light_val,
        ):
            w.setEnabled(enabled)

    def _on_glow_control_changed(self, *args) -> None:
        self._update_glow_controls_enabled()
        self._update_glow_labels()
        self._preview_glow()
        self._mark_dirty()

    def _update_glow_labels(self) -> None:
        self.lbl_width_val.setText(f"{self.sld_width.value()} px")
        self.lbl_taper_val.setText(f"{self.sld_taper.value()}%")
        self.lbl_light_sat_val.setText(f"{self.sld_light_sat.value()}%")
        self.lbl_light_light_val.setText(f"{self.sld_light_light.value()}%")

    def _preview_glow(self) -> None:
        glow = self._glow_widget()
        if glow is None:
            return

        if self.chk_glow.isChecked():
            mode = self.cmb_glow_mode.currentText()
        else:
            mode = "off"

        try:
            glow.set_mode(mode)
            glow.set_glow_width(self.sld_width.value())
            glow.set_taper_ratio(self.sld_taper.value() / 100.0)
            glow.set_light_style(self.cmb_light_style.currentText())
            glow.set_light_rgb_params(
                self.sld_light_sat.value() / 100.0,
                self.sld_light_light.value() / 100.0,
            )
        except (AttributeError, RuntimeError) as exc:
            log.debug("Glow preview failed: %s", exc)

    # ── Dirty tracking ─────────────────────────────────────────────
    def _connect_dirty_tracking(self) -> None:
        for chk in self.findChildren(QCheckBox):
            chk.stateChanged.connect(self._mark_dirty)
        for cmb in self.findChildren(QComboBox):
            cmb.currentTextChanged.connect(self._mark_dirty)
        for spn in self.findChildren(QSpinBox):
            spn.valueChanged.connect(self._mark_dirty)
        self.homepage.textChanged.connect(self._mark_dirty)
        self.dl_dir.textChanged.connect(self._mark_dirty)
        self.wl_edit.textChanged.connect(self._mark_dirty)

    def _mark_dirty(self, *args) -> None:
        self._dirty = True

    def _preview_theme(self, name: str) -> None:
        if name:
            apply_theme(name)

    def reject(self) -> None:
        if self._dirty:
            res = QMessageBox.question(
                self,
                "Discard changes?",
                "You have unsaved changes.\n\n"
                "Discard them?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if res != QMessageBox.StandardButton.Yes:
                return

        try:
            if self.theme.currentText() != self._initial_theme:
                apply_theme(self._initial_theme)
        except (AttributeError, RuntimeError) as exc:
            log.debug("Failed to revert theme on reject: %s", exc)

        glow = self._glow_widget()
        if glow is not None:
            try:
                init = self._initial_glow
                glow.set_mode(init["mode"] if init["enabled"] else "off")
                glow.set_glow_width(init["width"])
                glow.set_taper_ratio(init["taper"])
                glow.set_light_style(init["light_style"])
                glow.set_light_rgb_params(init["light_sat"], init["light_lightness"])
            except (AttributeError, RuntimeError) as exc:
                log.debug("Failed to revert glow on reject: %s", exc)

        super().reject()

    # ── Save / clear ───────────────────────────────────────────────
    def _pick_dir(self):
        start = self.dl_dir.text().strip() or str(Path.home())
        d = QFileDialog.getExistingDirectory(self, "Choose download folder", start)
        if d:
            self.dl_dir.setText(d)

    def _save(self):
        s = self.store.settings
        s["search_engine"] = self.engine.currentText()
        s["homepage"] = self.homepage.text().strip() or DEFAULT_HOME
        s["download_dir"] = self.dl_dir.text().strip()
        s["theme"] = self.theme.currentText()
        s["save_history"] = self.chk_history.isChecked()
        s["restore_session"] = self.chk_restore.isChecked()
        s["clear_on_exit"] = self.chk_clear.isChecked()
        s["adblock_enabled"] = self.chk_adblock.isChecked()
        s["show_bookmark_bar"] = self.chk_show_bookmarks.isChecked()
        s["low_end_mode"] = self.chk_low_end.isChecked()
        s["max_tabs"] = self.spin_max_tabs.value()
        s["auto_suspend_tabs"] = self.chk_autosuspend.isChecked()
        s["suspend_after_sec"] = self.spin_suspend.value()
        s["restore_scroll"] = self.chk_restore_scroll.isChecked()
        s["suspend_skip_dirty_form"] = self.chk_skip_dirty.isChecked()

        # Glow
        if self.chk_glow.isChecked():
            s["window_glow"] = self.cmb_glow_mode.currentText()
        else:
            s["window_glow"] = "off"
        s["window_glow_width"] = self.sld_width.value()
        s["window_glow_taper"] = self.sld_taper.value() / 100.0
        s["window_glow_light_style"] = self.cmb_light_style.currentText()
        s["window_glow_light_sat"] = self.sld_light_sat.value() / 100.0
        s["window_glow_light_lightness"] = (
            self.sld_light_light.value() / 100.0
        )

        wl_lines = self.wl_edit.toPlainText().splitlines()
        s["suspend_whitelist"] = [
            w.strip().lower() for w in wl_lines if w.strip()
        ]

        self.store.save()
        self.settings_saved.emit()

        self._dirty = False
        self._initial_theme = self.theme.currentText()
        glow_mode = s["window_glow"]
        self._initial_glow = {
            "enabled": glow_mode != "off",
            "mode": glow_mode if glow_mode in ("rgb", "static") else "rgb",
            "width": s["window_glow_width"],
            "taper": s["window_glow_taper"],
            "light_style": s["window_glow_light_style"],
            "light_sat": s["window_glow_light_sat"],
            "light_lightness": s["window_glow_light_lightness"],
        }

        if self.chk_low_end.isChecked() != self._old_low_end:
            QMessageBox.information(
                self, "Restart required",
                "Changes to <b>Low Power Mode</b> will take effect after "
                "restarting the browser.\n\n"
                "Please close and reopen Frame."
            )

        self.accept()

    def _clear_cache(self):
        self.profile.clearHttpCache()
        QMessageBox.information(self, "Done", "Cache cleared.")

    def _clear_cookies(self):
        self.profile.cookieStore().deleteAllCookies()
        QMessageBox.information(self, "Done", "Cookies cleared.")

    def _clear_history(self):
        self.store.clear_history()
        QMessageBox.information(self, "Done", "Browsing history cleared.")