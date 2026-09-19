"""Manager pairing a standalone QTabBar with a QStackedWidget.

QTabWidget ties its tab strip directly above its content, preventing
other widgets (like a toolbar) from sitting between them. This class
keeps the tab bar and content stack independent so the tab strip can be
placed at the very top of the window, above the toolbar — Chrome-style.

Order-sync guarantee: whenever the tab bar's order changes (drag-reorder
or programmatic moveTab), the content stack is rebuilt to match. This is
required because icon/title/URL updates use the stack's index to look up
widgets and then write them back to the tab bar — if the two orders drift,
those updates land on the wrong tab.
"""
from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QStackedWidget

from .web import BrowserTabBar


class TabContainer(QObject):
    """Keeps a QTabBar and QStackedWidget in sync; exposes a QTabWidget-
    like API so it can be a drop-in replacement in MainWindow."""

    tabCloseRequested = pyqtSignal(int)
    currentChanged = pyqtSignal(int)
    tabMoved = pyqtSignal(int, int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.tab_bar = BrowserTabBar()
        self.tab_bar.setTabsClosable(False)
        self.tab_bar.setMovable(True)
        self.stack = QStackedWidget()

        self._syncing = False

        self.tab_bar.currentChanged.connect(self._on_bar_changed)
        self.tab_bar.tabCloseRequested.connect(self.tabCloseRequested.emit)
        self.tab_bar.tabMoved.connect(self._on_tab_moved)

    # ── Sync ────────────────────────────────────────────────────────
    def _on_bar_changed(self, idx: int) -> None:
        if idx < 0:
            return
        if self.stack.currentIndex() != idx:
            self._syncing = True
            try:
                self.stack.setCurrentIndex(idx)
            finally:
                self._syncing = False
        self.currentChanged.emit(idx)

    def _on_stack_changed(self, idx: int) -> None:
        if self._syncing or idx < 0:
            return
        if self.tab_bar.currentIndex() != idx:
            self.tab_bar.blockSignals(True)
            self.tab_bar.setCurrentIndex(idx)
            self.tab_bar.blockSignals(False)

    def _on_tab_moved(self, from_idx: int, to_idx: int) -> None:
        """Rebuild the content stack to match the new tab-bar order.

        `QStackedWidget` has no `moveTab()`. We rebuild the entire order:
        collect widgets, remove them all, reinsert in the new sequence,
        then restore the previously-current widget.
        """
        if from_idx == to_idx:
            self.tabMoved.emit(from_idx, to_idx)
            return

        count = self.stack.count()
        if not (0 <= from_idx < count and 0 <= to_idx < count):
            self.tabMoved.emit(from_idx, to_idx)
            return

        widgets = [self.stack.widget(i) for i in range(count)]
        if any(w is None for w in widgets):
            self.tabMoved.emit(from_idx, to_idx)
            return

        moved = widgets.pop(from_idx)
        widgets.insert(to_idx, moved)

        prev_current = self.stack.currentWidget()

        self._syncing = True
        try:
            self.stack.blockSignals(True)
            for w in widgets:
                self.stack.removeWidget(w)
            for i, w in enumerate(widgets):
                self.stack.insertWidget(i, w)
            if prev_current is not None:
                new_idx = self.stack.indexOf(prev_current)
                if new_idx >= 0:
                    self.stack.setCurrentIndex(new_idx)
        finally:
            self.stack.blockSignals(False)
            self._syncing = False

        self.tabMoved.emit(from_idx, to_idx)

    # ── QTabWidget-like API ─────────────────────────────────────────
    def tabBar(self) -> BrowserTabBar:
        return self.tab_bar

    def addTab(self, widget, label: str) -> int:
        idx = self.stack.addWidget(widget)
        self.tab_bar.addTab(label)
        return idx

    def removeTab(self, idx: int) -> None:
        self.tab_bar.removeTab(idx)
        w = self.stack.widget(idx)
        if w is not None:
            self.stack.removeWidget(w)
            w.setParent(None)

    def widget(self, idx: int):
        return self.stack.widget(idx)

    def indexOf(self, widget) -> int:
        return self.stack.indexOf(widget)

    def count(self) -> int:
        return self.stack.count()

    def currentIndex(self) -> int:
        return self.stack.currentIndex()

    def setCurrentIndex(self, idx: int) -> None:
        self.tab_bar.setCurrentIndex(idx)
        self.stack.setCurrentIndex(idx)

    def currentWidget(self):
        return self.stack.currentWidget()

    def setTabText(self, idx: int, text: str) -> None:
        self.tab_bar.setTabText(idx, text)

    def tabText(self, idx: int) -> str:
        return self.tab_bar.tabText(idx)

    def setTabToolTip(self, idx: int, tip: str) -> None:
        self.tab_bar.setTabToolTip(idx, tip)

    def setTabIcon(self, idx: int, icon) -> None:
        self.tab_bar.setTabIcon(idx, icon)

    # ── Loading spinner (per-tab) ───────────────────────────────────
    def start_tab_spinner(self, widget, color: str) -> None:
        """Start the rotating spinner icon for the tab holding `widget`."""
        idx = self.stack.indexOf(widget)
        if idx >= 0:
            self.tab_bar.start_spinner(idx, color)

    def stop_tab_spinner(self, widget) -> None:
        """Stop the spinner and restore the correct favicon."""
        idx = self.stack.indexOf(widget)
        if idx >= 0:
            self.tab_bar.stop_spinner(idx)