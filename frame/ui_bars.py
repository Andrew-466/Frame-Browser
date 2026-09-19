"""FindBar, BookmarkBar (dengan overflow chevron), DownloadShelf."""
from __future__ import annotations

from PyQt6.QtCore import Qt, QUrl, pyqtSignal, QTimer, QEvent
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWebEngineCore import QWebEngineDownloadRequest
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMenu,
    QProgressBar, QPushButton, QSizePolicy, QToolButton, QVBoxLayout,
    QWidget,
)

from .core import human_size
from .icons import (
    SVG_ARROW_DOWN, SVG_ARROW_UP, SVG_CHEVRON_RIGHT, SVG_CLOSE,
    icon_from_svg,
)
from .theme import THEMES


def _theme_colors(store):
    name = store.settings.get("theme", "dark")
    return THEMES.get(name, THEMES["dark"])


class FindBar(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 6, 14, 0)
        lay.setSpacing(6)

        self.edit = QLineEdit()
        self.edit.setPlaceholderText("Find in this page…")
        self.edit.setMaximumWidth(340)
        self.edit.textChanged.connect(lambda _: self._find(False))
        self.edit.returnPressed.connect(lambda: self._find(False))

        prev_btn = QToolButton()
        prev_btn.setToolTip("Previous")
        prev_btn.setAutoRaise(True)
        prev_btn.setFixedSize(28, 28)
        prev_btn.setIcon(icon_from_svg(SVG_ARROW_UP, color="#888888", size=18))
        prev_btn.clicked.connect(lambda: self._find(True))

        next_btn = QToolButton()
        next_btn.setToolTip("Next")
        next_btn.setAutoRaise(True)
        next_btn.setFixedSize(28, 28)
        next_btn.setIcon(icon_from_svg(SVG_ARROW_DOWN, color="#888888", size=18))
        next_btn.clicked.connect(lambda: self._find(False))

        close_btn = QToolButton()
        close_btn.setToolTip("Close")
        close_btn.setAutoRaise(True)
        close_btn.setFixedSize(28, 28)
        close_btn.setIcon(icon_from_svg(SVG_CLOSE, color="#888888", size=16))
        close_btn.clicked.connect(self.hide_bar)

        lay.addWidget(self.edit)
        lay.addWidget(prev_btn)
        lay.addWidget(next_btn)
        lay.addWidget(close_btn)
        lay.addStretch(1)

        self._view = None
        sc = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        sc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        sc.activated.connect(self.hide_bar)

    def set_view(self, view) -> None:
        self._view = view

    def open_bar(self, view) -> None:
        self.set_view(view)
        self.show()
        self.edit.setFocus()
        self.edit.selectAll()
        if self.edit.text():
            self._find(False)

    def hide_bar(self) -> None:
        if self._view is not None:
            self._view.page().findText("")
        self.hide()

    def _find(self, backward: bool) -> None:
        if self._view is None:
            return
        text = self.edit.text()
        if not text:
            self._view.page().findText("")
            return
        from PyQt6.QtWebEngineCore import QWebEnginePage
        f = QWebEnginePage.FindFlag(0)
        if backward:
            f |= QWebEnginePage.FindFlag.FindBackward
        self._view.page().findText(text, f)


class BookmarkBar(QFrame):
    open_requested = pyqtSignal(QUrl)

    def __init__(self, store, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("BookmarkBar")
        self.store = store
        self._user_wants_visible = True
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )

        self.setMinimumHeight(28)
        self.setMaximumHeight(48)
        self.setFixedHeight(36)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(6, 2, 6, 2)
        outer.setSpacing(2)

        self._buttons_wrap = QWidget()
        self._buttons_layout = QHBoxLayout(self._buttons_wrap)
        self._buttons_layout.setContentsMargins(0, 0, 0, 0)
        self._buttons_layout.setSpacing(2)
        outer.addWidget(self._buttons_wrap, 1)

        self._overflow_btn = QToolButton()
        self._overflow_btn.setAutoRaise(True)
        self._overflow_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._overflow_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._overflow_btn.setToolTip("More bookmarks")
        self._overflow_btn.hide()
        outer.addWidget(self._overflow_btn, 0)

        self._overflow_menu = QMenu(self._overflow_btn)
        self._overflow_btn.setMenu(self._overflow_menu)

        self._all_buttons: list[QToolButton] = []
        self.store.bookmarks_changed.connect(self.refresh)
        self.installEventFilter(self)
        self._apply_icon_colors()
        self.refresh()

    def set_user_visible(self, visible: bool) -> None:
        self._user_wants_visible = visible
        self._update_visibility()

    def _update_visibility(self) -> None:
        self.setVisible(self._user_wants_visible and len(self.store.bookmarks) > 0)

    def _apply_icon_colors(self) -> None:
        c = _theme_colors(self.store)
        self._overflow_btn.setIcon(
            icon_from_svg(SVG_CHEVRON_RIGHT, color=c["text"], size=18)
        )

    def eventFilter(self, obj, event):
        if obj is self and event.type() == QEvent.Type.Resize:
            self._reflow()
        return super().eventFilter(obj, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reflow()

    def refresh(self) -> None:
        while self._buttons_layout.count():
            item = self._buttons_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        self._all_buttons = []
        for bm in self.store.bookmarks:
            btn = QToolButton()
            btn.setText(bm["title"][:24] + ("…" if len(bm["title"]) > 24 else ""))
            btn.setToolTip(f"{bm['title']}\n{bm['url']}")
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            btn.setSizePolicy(
                QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
            )
            url_str = bm["url"]
            btn.clicked.connect(
                lambda _, u=url_str: self.open_requested.emit(QUrl(u))
            )
            btn.customContextMenuRequested.connect(
                lambda pos, u=url_str, b=btn: self._context_menu(b, pos, u)
            )
            self._buttons_layout.addWidget(btn)
            self._all_buttons.append(btn)

        self._apply_icon_colors()
        self._update_visibility()
        QTimer.singleShot(0, self._reflow)

    def _reflow(self) -> None:
        if not getattr(self, "_all_buttons", None):
            self._overflow_btn.hide()
            return

        total = self.width() - 12
        overflow_w = self._overflow_btn.sizeHint().width() + 4
        avail = total

        used = 0
        fit_count = 0
        for btn in self._all_buttons:
            w = btn.sizeHint().width() + 2
            if used + w > avail:
                break
            used += w
            fit_count += 1

        if fit_count < len(self._all_buttons):
            avail -= overflow_w
            used = 0
            fit_count = 0
            for btn in self._all_buttons:
                w = btn.sizeHint().width() + 2
                if used + w > avail:
                    break
                used += w
                fit_count += 1

        for i, btn in enumerate(self._all_buttons):
            btn.setVisible(i < fit_count)

        overflow = self._all_buttons[fit_count:]
        if overflow:
            self._overflow_menu.clear()
            for btn in overflow:
                url_str = None
                label = ""
                for bm in self.store.bookmarks:
                    tip = bm["title"] + "\n" + bm["url"]
                    if btn.toolTip() == tip:
                        url_str = bm["url"]
                        label = bm["title"]
                        break
                if url_str is None:
                    continue
                act = self._overflow_menu.addAction(label or url_str)
                act.triggered.connect(
                    lambda _, u=url_str: self.open_requested.emit(QUrl(u))
                )
            self._overflow_btn.show()
        else:
            self._overflow_btn.hide()

    def _context_menu(self, btn: QToolButton, pos, url: str) -> None:
        m = QMenu(self)
        act_open = m.addAction("Open")
        act_open_new = m.addAction("Open in new tab")
        m.addSeparator()
        act_edit = m.addAction("Edit…")
        act_del = m.addAction("Delete")

        chosen = m.exec(btn.mapToGlobal(pos))
        if chosen is act_del:
            self.store.remove_bookmark(url)
        elif chosen is act_open:
            self.open_requested.emit(QUrl(url))
        elif chosen is act_open_new:
            win = self.window()
            if hasattr(win, "add_new_tab"):
                win.add_new_tab(QUrl(url), "New Tab")
        elif chosen is act_edit:
            self._edit(url)

    def _edit(self, url: str) -> None:
        bm = next((b for b in self.store.bookmarks if b["url"] == url), None)
        if not bm:
            return
        nt, ok = QInputDialog.getText(self, "Edit bookmark", "Title:", text=bm["title"])
        if not ok:
            return
        nu, ok = QInputDialog.getText(self, "Edit bookmark", "URL:", text=bm["url"])
        if not ok:
            return
        bm["title"] = nt.strip() or bm["url"]
        bm["url"] = nu.strip() or bm["url"]
        self.store.save()
        self.store.bookmarks_changed.emit()


class ShelfItem(QFrame):
    def __init__(self, req: QWebEngineDownloadRequest, parent=None) -> None:
        super().__init__(parent)
        self.req = req
        self.setFrameShape(QFrame.Shape.NoFrame)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 4, 10, 4)
        lay.setSpacing(3)

        top = QHBoxLayout()
        top.setSpacing(8)
        self.name = QLabel(req.downloadFileName())
        self.name.setStyleSheet("font-size: 12px; font-weight: 600;")
        self.name.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        top.addWidget(self.name, 1)

        self.info = QLabel("")
        self.info.setStyleSheet("font-size: 11px; color: #888888;")
        top.addWidget(self.info)

        self.cancel = QToolButton()
        self.cancel.setToolTip("Cancel")
        self.cancel.setAutoRaise(True)
        self.cancel.setFixedSize(22, 22)
        self.cancel.setIcon(icon_from_svg(SVG_CLOSE, color="#888888", size=14))
        self.cancel.clicked.connect(req.cancel)
        top.addWidget(self.cancel)

        lay.addLayout(top)
        self.bar = QProgressBar()
        self.bar.setFixedHeight(4)
        self.bar.setTextVisible(False)
        self.bar.setRange(0, 100)
        lay.addWidget(self.bar)

        req.receivedBytesChanged.connect(self._upd)
        req.totalBytesChanged.connect(self._upd)
        req.stateChanged.connect(self._upd)
        self._upd()

    def _upd(self):
        total = self.req.totalBytes()
        got = self.req.receivedBytes()
        if total > 0:
            self.bar.setRange(0, 100)
            self.bar.setValue(int(got * 100 / total))
            self.info.setText(f"{human_size(got)} / {human_size(total)}")
        else:
            self.bar.setRange(0, 0)
            self.info.setText(human_size(got))
        state = self.req.state()
        if state == QWebEngineDownloadRequest.DownloadState.DownloadCompleted:
            self.bar.setRange(0, 100); self.bar.setValue(100)
            self.info.setText("Done")
            self.cancel.setEnabled(False)
            self.cancel.setIcon(icon_from_svg(SVG_CLOSE, color="#4caf50", size=14))
        elif state in (
            QWebEngineDownloadRequest.DownloadState.DownloadCancelled,
            QWebEngineDownloadRequest.DownloadState.DownloadInterrupted,
        ):
            self.info.setText("Failed / cancelled")
            self.cancel.setEnabled(False)


class DownloadShelf(QFrame):
    show_all_requested = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setMinimumHeight(60)
        self.setMaximumHeight(100)
        self.setFixedHeight(70)
        self.items: list[ShelfItem] = []

        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 6, 10, 6)
        lay.setSpacing(8)

        left = QVBoxLayout(); left.setSpacing(2)
        title = QLabel("Downloads")
        title.setStyleSheet("font-size: 12px; font-weight: 600;")
        left.addWidget(title)
        self.show_all = QPushButton("Show all")
        self.show_all.setFixedHeight(22)
        self.show_all.setStyleSheet("font-size: 11px; padding: 2px 10px;")
        self.show_all.clicked.connect(self.show_all_requested.emit)
        left.addWidget(self.show_all)
        left.addStretch(1)
        left_wrap = QWidget(); left_wrap.setLayout(left); left_wrap.setFixedWidth(90)
        lay.addWidget(left_wrap)

        self.inner = QVBoxLayout(); self.inner.setSpacing(2); self.inner.addStretch(1)
        inner_wrap = QWidget(); inner_wrap.setLayout(self.inner)
        lay.addWidget(inner_wrap, 1)

        close_btn = QToolButton()
        close_btn.setToolTip("Hide")
        close_btn.setAutoRaise(True)
        close_btn.setFixedSize(22, 22)
        close_btn.setIcon(icon_from_svg(SVG_CLOSE, color="#888888", size=14))
        close_btn.clicked.connect(self.hide_shelf)
        lay.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignTop)

        self._auto_hide = QTimer(self)
        self._auto_hide.setSingleShot(True)
        self._auto_hide.setInterval(3500)
        self._auto_hide.timeout.connect(self._maybe_hide)

    def add_download(self, req: QWebEngineDownloadRequest) -> None:
        item = ShelfItem(req)
        self.inner.insertWidget(self.inner.count() - 1, item)
        self.items.append(item)
        self.show()
        self._auto_hide.stop()

        def _cleanup(*_):
            QTimer.singleShot(2000, self._maybe_hide)

        req.stateChanged.connect(_cleanup)

    def _maybe_hide(self) -> None:
        all_done = all(
            it.req.state() in (
                QWebEngineDownloadRequest.DownloadState.DownloadCompleted,
                QWebEngineDownloadRequest.DownloadState.DownloadCancelled,
                QWebEngineDownloadRequest.DownloadState.DownloadInterrupted,
            )
            for it in self.items
        )
        if all_done:
            self.hide_shelf()

    def hide_shelf(self) -> None:
        self.hide()
        for it in list(self.items):
            self.inner.removeWidget(it)
            it.setParent(None)
            it.deleteLater()
        self.items.clear()