"""UDP localhost transport — shares mesh frames across separate terminal processes."""

from __future__ import annotations

import socket
import threading
from typing import Callable

Receiver = Callable[[bytes, str], None]

HOST = "127.0.0.1"
PORT = 19987


class UdpTransport:
    """Send: unbound socket. Receive: bind PORT only when listen=True (operator node)."""

    _send_sock: socket.socket | None = None
    _recv_hub: UdpTransport | None = None
    _lock = threading.RLock()

    def __init__(self, node_id: str, *, listen: bool = False) -> None:
        self.node_id = node_id
        self._receiver: Receiver | None = None
        self._running = False
        self._recv_sock: socket.socket | None = None
        self._thread: threading.Thread | None = None

        with self._lock:
            if UdpTransport._send_sock is None:
                UdpTransport._send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        if listen:
            self._running = True
            self._recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._recv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                self._recv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except (AttributeError, OSError):
                pass
            self._recv_sock.bind((HOST, PORT))
            self._recv_sock.settimeout(0.5)
            self._thread = threading.Thread(target=self._loop, name="mesh-udp-recv", daemon=True)
            self._thread.start()
            UdpTransport._recv_hub = self

    @classmethod
    def get(cls, node_id: str, *, listen: bool = False) -> UdpTransport:
        with cls._lock:
            if listen:
                if cls._recv_hub is None:
                    cls._recv_hub = cls(node_id, listen=True)
                else:
                    cls._recv_hub.node_id = node_id
                return cls._recv_hub
            return cls(node_id, listen=False)

    def set_receiver(self, fn: Receiver | None) -> None:
        if not self._recv_sock:
            return
        self._receiver = fn

    def neighbours(self) -> list[str]:
        return ["drone_1", "drone_2", "drone_3", "operator"]

    def send(self, frame: bytes, *, broadcast: bool = True) -> int:
        assert UdpTransport._send_sock is not None
        UdpTransport._send_sock.sendto(frame, (HOST, PORT))
        return 1

    def _loop(self) -> None:
        assert self._recv_sock is not None
        while self._running:
            try:
                data, _addr = self._recv_sock.recvfrom(8192)
            except socket.timeout:
                continue
            except OSError:
                break
            if self._receiver:
                self._receiver(data, "mesh")

    def close(self) -> None:
        self._running = False
        if self._recv_sock:
            try:
                self._recv_sock.close()
            except OSError:
                pass
