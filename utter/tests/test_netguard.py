import os
import socket
from collections.abc import Iterator

import pytest

from utter.netguard import NetGuard, NetworkBlockedError


@pytest.fixture
def guard() -> Iterator[NetGuard]:
    g = NetGuard()
    g.install()
    yield g
    g.uninstall()


def test_blocks_and_counts_dns(guard: NetGuard) -> None:
    with pytest.raises(NetworkBlockedError):
        socket.getaddrinfo("huggingface.co", 443)
    assert guard.blocked_count == 1
    assert guard.blocked == ["dns:huggingface.co"]


def test_blocks_direct_ip_connect(guard: NetGuard) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s, pytest.raises(NetworkBlockedError):
        s.connect(("93.184.216.34", 80))
    assert guard.blocked_count == 1


def test_blocks_connect_ex(guard: NetGuard) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s, pytest.raises(NetworkBlockedError):
        s.connect_ex(("1.1.1.1", 443))


def test_create_connection_is_blocked(guard: NetGuard) -> None:
    with pytest.raises(OSError):
        socket.create_connection(("example.com", 80), timeout=1)
    assert guard.blocked_count >= 1


def test_loopback_allowed(guard: NetGuard) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        port = server.getsockname()[1]
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
            client.connect(("127.0.0.1", port))
        assert socket.getaddrinfo("localhost", port)
    assert guard.blocked_count == 0


def test_sets_offline_env(guard: NetGuard) -> None:
    assert os.environ["HF_HUB_OFFLINE"] == "1"


def test_uninstall_restores() -> None:
    original = socket.getaddrinfo
    g = NetGuard()
    g.install()
    assert socket.getaddrinfo is not original
    g.uninstall()
    assert socket.getaddrinfo is original
