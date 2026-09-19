"""Simple host-based AdBlocker."""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtWebEngineCore import (
    QWebEngineUrlRequestInfo,
    QWebEngineUrlRequestInterceptor,
)

from .core import log


def _builtin_hosts_path() -> Path:
    return Path(__file__).parent / "data" / "adblock_hosts.txt"


class AdBlocker(QWebEngineUrlRequestInterceptor):
    """Blocks requests from hosts in the blacklist."""

    def __init__(self, data_dir: Path, parent=None) -> None:
        super().__init__(parent)
        self.enabled: bool = True
        self.blocked_count: int = 0
        self._hosts: set[str] = self._load_builtin()
        self._load_external(data_dir / "filters.txt")

    @staticmethod
    def _load_builtin() -> set[str]:
        hosts: set[str] = set()
        p = _builtin_hosts_path()
        if not p.exists():
            log.warning("Built-in host list not found: %s", p)
            return hosts
        try:
            for raw in p.read_text("utf-8").splitlines():
                line = raw.strip().lower()
                if not line or line.startswith("#"):
                    continue
                hosts.add(line)
        except OSError as exc:
            log.warning("Failed to read %s: %s", p, exc)
        return hosts

    def _load_external(self, path: Path) -> None:
        if not path.exists():
            return
        try:
            for raw in path.read_text("utf-8", errors="ignore").splitlines():
                line = raw.strip()
                if not line or line.startswith(("#", "!", "[")):
                    continue
                if line.startswith("||"):
                    line = line[2:]
                if line.endswith("^"):
                    line = line[:-1]
                if "/" in line:
                    line = line.split("/", 1)[0]
                if not line or "." not in line:
                    continue
                self._hosts.add(line.lower())
        except OSError as exc:
            log.warning("Failed to read %s: %s", path, exc)

    def _matches(self, host: str) -> bool:
        host = host.lower()
        if not host:
            return False
        parts = host.split(".")
        for i in range(len(parts) - 1):
            if ".".join(parts[i:]) in self._hosts:
                return True
        return host in self._hosts

    def interceptRequest(self, info: QWebEngineUrlRequestInfo) -> None:
        """Block secondary resources (script/img/iframe) from blacklisted hosts.

        Known limitation: main-frame/sub-frame navigation is **not** blocked
        here — if the user clicks a link that leads directly to an ad
        domain, the page still opens. This is a design choice shared with
        most adblockers: blocking main-frame would make sites hosted on
        blacklisted domains (rare but possible) completely inaccessible.
        Selective navigation blocking can be added in
        `WebView.acceptNavigationRequest` if needed, ideally with a
        "continue?" interstitial.
        """
        if not self.enabled:
            return
        rtype = info.resourceType()
        if rtype in (
            QWebEngineUrlRequestInfo.ResourceType.ResourceTypeMainFrame,
            QWebEngineUrlRequestInfo.ResourceType.ResourceTypeSubFrame,
        ):
            return
        if self._matches(info.requestUrl().host()):
            info.block(True)
            self.blocked_count += 1