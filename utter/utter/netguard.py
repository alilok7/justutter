"""Proof of local processing: block and count every outbound network attempt at runtime.

Loopback traffic is allowed (nothing leaves the machine). Anything else raises
``NetworkBlockedError`` and is counted, and the count is shown in the UI.
"""

from __future__ import annotations

import ipaddress
import logging
import os
import socket
import threading
from collections.abc import Callable
from typing import Any

log = logging.getLogger(__name__)

_LOOPBACK_NAMES = {"localhost", "localhost.localdomain", "ip6-localhost", ""}


class NetworkBlockedError(OSError):
    """Raised instead of opening a non-local connection."""


def _is_loopback(host: object) -> bool:
    if host is None:
        return True
    if isinstance(host, bytes):
        host = host.decode(errors="replace")
    if not isinstance(host, str):
        return False
    name = host.strip("[]").lower()
    if name in _LOOPBACK_NAMES:
        return True
    try:
        return ipaddress.ip_address(name.split("%")[0]).is_loopback
    except ValueError:
        return False


class NetGuard:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.blocked: list[str] = []
        self._originals: dict[str, Callable[..., Any]] = {}

    @property
    def blocked_count(self) -> int:
        with self._lock:
            return len(self.blocked)

    def _record(self, target: str) -> None:
        with self._lock:
            self.blocked.append(target)
        log.warning("blocked outbound network attempt to %s", target)

    def install(self) -> None:
        if self._originals:
            return
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        self._originals = {
            "getaddrinfo": socket.getaddrinfo,
            "connect": socket.socket.connect,
            "connect_ex": socket.socket.connect_ex,
        }
        orig_getaddrinfo = self._originals["getaddrinfo"]
        orig_connect = self._originals["connect"]
        orig_connect_ex = self._originals["connect_ex"]
        guard = self

        def getaddrinfo(host: Any, *args: Any, **kwargs: Any) -> Any:
            if not _is_loopback(host):
                guard._record(f"dns:{host}")
                raise NetworkBlockedError(f"network disabled by Utter (lookup of {host})")
            return orig_getaddrinfo(host, *args, **kwargs)

        def _check(sock: socket.socket, address: Any) -> None:
            if sock.family in (socket.AF_INET, socket.AF_INET6):
                host = address[0] if isinstance(address, tuple) else address
                if not _is_loopback(host):
                    guard._record(f"connect:{host}")
                    raise NetworkBlockedError(f"network disabled by Utter (connect to {host})")

        def connect(sock: socket.socket, address: Any) -> None:
            _check(sock, address)
            orig_connect(sock, address)

        def connect_ex(sock: socket.socket, address: Any) -> int:
            _check(sock, address)
            result: int = orig_connect_ex(sock, address)
            return result

        socket.getaddrinfo = getaddrinfo
        socket.socket.connect = connect  # type: ignore[method-assign,assignment]
        socket.socket.connect_ex = connect_ex  # type: ignore[method-assign,assignment]
        log.info("network guard installed: non-loopback connections are blocked")

    def uninstall(self) -> None:
        if not self._originals:
            return
        socket.getaddrinfo = self._originals["getaddrinfo"]
        socket.socket.connect = self._originals["connect"]  # type: ignore[method-assign]
        socket.socket.connect_ex = self._originals["connect_ex"]  # type: ignore[method-assign]
        self._originals = {}
