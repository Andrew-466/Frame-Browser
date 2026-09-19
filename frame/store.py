"""Persistence: bookmarks, history, session, settings, permissions."""
from __future__ import annotations

import json
import re
import time
from collections import deque
from pathlib import Path

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from .core import data_dir, log


# Valid policy values for permission entries. Anything else is treated
# as invalid and dropped (both on set and on load — see
# `_sanitize_permissions`).
_PERMISSION_POLICIES = {"granted", "denied"}


def _load_json_tolerant(text: str):
    """Parse JSON, tolerating `#` comments and trailing commas.

    `frame_data.json` is user-editable. Some users add comments or
    leave trailing commas — Python's `json` module rejects both, which
    would silently wipe every setting on load. We strip them and retry.

    Raises json.JSONDecodeError if the text still cannot be parsed.
    """
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 1. Strip `#` line comments (naive — doesn't handle `#` inside a
    #    string, but sufficient for the common hand-edited case).
    cleaned = re.sub(r"(?m)#.*$", "", text)
    # 2. Remove trailing commas before `}` or `]`.
    cleaned = re.sub(r",(\s*[}\]])", r"\1", cleaned)
    return json.loads(cleaned)


class Store(QObject):
    """Single JSON store for all application state."""

    bookmarks_changed = pyqtSignal()
    MAX_HISTORY: int = 5000

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.dir: Path = data_dir()
        self.path: Path = self.dir / "frame_data.json"

        self.bookmarks: list[dict] = []
        self.history: deque[dict] = deque(maxlen=self.MAX_HISTORY)
        self.session: list[str] = []
        # origin -> {feature -> policy}
        self.permissions: dict[str, dict[str, str]] = {}
        self.settings: dict = {
            "search_engine": "Google",
            "homepage": "https://www.google.com",
            "download_dir": str(Path.home() / "Downloads"),
            "theme": "dark",
            "save_history": True,
            "restore_session": True,
            "clear_on_exit": False,
            "show_bookmark_bar": True,
            "adblock_enabled": True,
            "low_end_mode": False,
            "max_tabs": 30,
            "auto_suspend_tabs": True,
            "suspend_after_sec": 180,
            "first_run_done": False,
            "suspend_whitelist": [
                "mail.google.com", "docs.google.com", "drive.google.com",
                "notion.so", "figma.com", "trello.com", "github.com",
                "stackoverflow.com", "arxiv.org", "scholar.google.com",
                "jstor.org", "sciencedirect.com",
            ],
            "restore_scroll": True,
            "suspend_skip_dirty_form": True,
            "aggressive_process_mode": True,
            "restore_eager_count": 2,

            # ── Window glow ────────────────────────────────────────
            # "off" | "static" | "rgb"
            "window_glow": "rgb",
            # Fraction of window height where the tapered glow ends:
            # 0.25 → only top quarter, 0.50 → half, 1.0 → full height.
            "window_glow_taper": 0.4,
            "window_glow_width": 1,
            # Light mode glow style:
            #   "rgb"
            #   "solid"
            "window_glow_light_style": "solid",
            "window_glow_light_sat": 0.95,
            "window_glow_light_lightness": 0.32,
        }

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(1200)
        self._timer.timeout.connect(self.flush)

        self.load()

    # ── Disk I/O ────────────────────────────────────────────────────
    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            text = self.path.read_text("utf-8")
        except OSError as exc:
            log.warning("Failed to read %s: %s", self.path, exc)
            return
        try:
            raw = _load_json_tolerant(text)
        except json.JSONDecodeError as exc:
            log.warning("Failed to parse %s: %s", self.path, exc)
            return
        if not isinstance(raw, dict):
            log.warning("frame_data.json root is not an object — ignoring")
            return

        self.bookmarks = raw.get("bookmarks", []) or []
        self.history = deque(
            raw.get("history", []) or [], maxlen=self.MAX_HISTORY
        )
        self.session = raw.get("session", []) or []

        # Settings: copy so we can mutate without touching `raw`.
        settings_blob = raw.get("settings")
        if not isinstance(settings_blob, dict):
            settings_blob = {}
        else:
            settings_blob = dict(settings_blob)

        # Permissions: prefer top-level. Some hand-edited configs (and
        # test fixtures) place `permissions` inside `settings` — accept
        # that as a fallback and remove it from settings so it doesn't
        # leak into the settings UI.
        raw_perms = raw.get("permissions")
        nested_perms = settings_blob.pop("permissions", None)
        if not isinstance(raw_perms, dict) and isinstance(nested_perms, dict):
            raw_perms = nested_perms

        self.settings.update(settings_blob)
        self.permissions = self._sanitize_permissions(raw_perms or {})

    def save(self) -> None:
        self._timer.start()

    def flush(self) -> None:
        self._timer.stop()
        payload = {
            "bookmarks": self.bookmarks,
            "history": list(self.history),
            "session": self.session,
            "settings": self.settings,
            "permissions": self.permissions,
        }
        try:
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(payload, indent=2), "utf-8")
            tmp.replace(self.path)
        except OSError as exc:
            log.error("Failed to save data to %s: %s", self.path, exc)

    # ── Bookmarks ───────────────────────────────────────────────────
    def is_bookmarked(self, url: str) -> bool:
        return any(b["url"] == url for b in self.bookmarks)

    def add_bookmark(self, title: str | None, url: str) -> bool:
        if not url or self.is_bookmarked(url):
            return False
        self.bookmarks.append({
            "title": (title or url).strip(),
            "url": url,
            "added": time.time(),
        })
        self.save()
        self.bookmarks_changed.emit()
        return True

    def remove_bookmark(self, url: str) -> bool:
        before = len(self.bookmarks)
        self.bookmarks = [b for b in self.bookmarks if b["url"] != url]
        if len(self.bookmarks) != before:
            self.save()
            self.bookmarks_changed.emit()
            return True
        return False

    def toggle_bookmark(self, title: str | None, url: str) -> bool:
        if self.is_bookmarked(url):
            self.remove_bookmark(url)
            return False
        return self.add_bookmark(title, url)

    # ── History ─────────────────────────────────────────────────────
    def add_history(self, title: str | None, url: str) -> None:
        if not self.settings.get("save_history", True):
            return
        if not url or url.startswith("frame://") or url == "about:blank":
            return
        self.history.append({
            "title": (title or url).strip(),
            "url": url,
            "time": time.time(),
        })
        self.save()

    def clear_history(self) -> None:
        self.history.clear()
        self.save()

    def top_sites(self, limit: int = 8) -> list[dict]:
        counts: dict[str, dict] = {}
        for h in self.history:
            url = h["url"]
            if not url.startswith("http"):
                continue
            entry = counts.setdefault(url, {"url": url, "title": h["title"], "n": 0})
            entry["n"] += 1
            if h["title"]:
                entry["title"] = h["title"]
        return sorted(counts.values(), key=lambda x: -x["n"])[:limit]

    # ── Permissions ─────────────────────────────────────────────────
    @staticmethod
    def _sanitize_permissions(raw) -> dict[str, dict[str, str]]:
        """Drop invalid origins, features, or policies from a raw blob.

        Called on load so a corrupted or hand-edited frame_data.json
        cannot poison the permissions table. Accepts only plain
        `{origin: {feature: policy}}` shaped data; anything else is
        discarded silently.
        """
        if not isinstance(raw, dict):
            return {}
        clean: dict[str, dict[str, str]] = {}
        for origin, feats in raw.items():
            if not isinstance(origin, str) or not origin.strip():
                continue
            if not isinstance(feats, dict):
                continue
            bucket: dict[str, str] = {}
            for feature, policy in feats.items():
                if not isinstance(feature, str) or not feature.strip():
                    continue
                if not isinstance(policy, str):
                    continue
                if policy not in _PERMISSION_POLICIES:
                    continue
                bucket[feature] = policy
            if bucket:
                clean[origin] = bucket
        return clean

    def get_permission(self, origin: str, feature: str) -> str | None:
        """Return 'granted' / 'denied' / None (unknown)."""
        if not origin or not feature:
            return None
        bucket = self.permissions.get(origin)
        if not isinstance(bucket, dict):
            return None
        value = bucket.get(feature)
        return value if value in _PERMISSION_POLICIES else None

    def set_permission(self, origin: str, feature: str, policy: str) -> bool:
        """Persist a permission decision. Return True if the store changed.

        Rejects empty origin/feature and policies outside {granted, denied}.
        No-op (returns False) if the value was already that policy.
        """
        if not origin or not feature:
            return False
        if policy not in _PERMISSION_POLICIES:
            return False
        bucket = self.permissions.setdefault(origin, {})
        if bucket.get(feature) == policy:
            return False
        bucket[feature] = policy
        self.save()
        return True

    def clear_permission(self, origin: str, feature: str | None = None) -> bool:
        """Remove a permission decision.

        - `clear_permission(origin, feature)` — clears one entry.
        - `clear_permission(origin)` — clears every feature for that
          origin (equivalent to `clear_origin`).

        Return True if anything was removed.
        """
        if not origin:
            return False
        if feature is None:
            return self.clear_origin(origin)
        bucket = self.permissions.get(origin)
        if not isinstance(bucket, dict) or feature not in bucket:
            return False
        del bucket[feature]
        if not bucket:
            del self.permissions[origin]
        self.save()
        return True

    def clear_origin(self, origin: str) -> bool:
        """Remove every feature decision for one origin."""
        if origin not in self.permissions:
            return False
        del self.permissions[origin]
        self.save()
        return True

    def clear_all_permissions(self) -> bool:
        """Wipe the entire permissions table."""
        if not self.permissions:
            return False
        self.permissions.clear()
        self.save()
        return True

    def all_permissions(self) -> dict[str, dict[str, str]]:
        """Return a deep copy so callers can't mutate internal state."""
        return {o: dict(f) for o, f in self.permissions.items()}