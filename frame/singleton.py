"""Single-instance IPC untuk Frame — pakai QLocalServer/QLocalSocket.

Skema:
  1. Saat startup, coba connect ke socket existing.
  2. Kalau connect berhasil → ada instance lain → kirim URL ke sana,
     return True (caller exit tanpa membuat MainWindow).
  3. Kalau connect gagal → tidak ada instance → caller buat MainWindow,
     lalu panggil `start_server()` untuk listen di socket.

Batasan: import QtWebEngine tetap terjadi sebelum pengecekan (wajib
sebelum QApplication), jadi "exit instan" belum bisa dicapai. Ini
overhead ~200ms — diterima sebagai trade-off kesederhanaan.
"""
from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtNetwork import QLocalServer, QLocalSocket

from .core import log

SOCKET_NAME = "frame-browser-single-instance-v1"
CONNECT_TIMEOUT_MS = 400
READ_TIMEOUT_MS = 500


def try_forward_to_existing(urls: list[str]) -> bool:
    """Coba kirim URLs ke instance yang sudah berjalan.

    Return True kalau ada instance lain dan URLs berhasil dikirim —
    caller harus exit tanpa membuat MainWindow.
    Return False kalau tidak ada instance (caller harus buat window baru).
    """
    sock = QLocalSocket()
    sock.connectToServer(SOCKET_NAME)
    if not sock.waitForConnected(CONNECT_TIMEOUT_MS):
        return False

    payload = "\n".join(urls).encode("utf-8")
    if payload:
        sock.write(payload)
        sock.waitForBytesWritten(READ_TIMEOUT_MS)
    sock.disconnectFromServer()
    return True


class _Server(QObject):
    """QLocalServer wrapper — emit `urls_received` saat ada payload masuk."""

    urls_received = pyqtSignal(list)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        # Bersihkan socket basi (mis. instance sebelumnya crash).
        QLocalServer.removeServer(SOCKET_NAME)
        self._server = QLocalServer(self)
        if not self._server.listen(SOCKET_NAME):
            log.warning(
                "Tidak bisa listen di %s: %s",
                SOCKET_NAME, self._server.errorString(),
            )
        else:
            log.debug("Single-instance server listening di %s", SOCKET_NAME)
        self._server.newConnection.connect(self._on_connection)

    def _on_connection(self) -> None:
        sock = self._server.nextPendingConnection()
        if sock is None:
            return
        try:
            if sock.waitForReadyRead(READ_TIMEOUT_MS):
                data = bytes(sock.readAll()).decode("utf-8", errors="ignore")
            else:
                data = ""
        except RuntimeError:
            data = ""
        finally:
            try:
                sock.disconnectFromServer()
            except RuntimeError:
                pass
        urls = [u for u in data.splitlines() if u]
        if urls:
            self.urls_received.emit(urls)

    def close(self) -> None:
        try:
            self._server.close()
        except RuntimeError:
            pass
        QLocalServer.removeServer(SOCKET_NAME)


def start_server(on_urls: Callable[[list[str]], None]) -> _Server:
    """Jalankan IPC server. Callback dipanggil saat ada URL dari instance lain."""
    server = _Server()
    server.urls_received.connect(on_urls)
    return server