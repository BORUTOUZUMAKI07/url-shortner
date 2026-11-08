import pytest

from src.shared.core.safe_url import is_safe_url


class _FakeAddrInfo:
    def __init__(self, ip):
        self._ip = ip

    def __getitem__(self, idx):
        # (family, type, proto, canonname, sockaddr)
        if idx == 4:
            return (self._ip, 0)
        raise IndexError


class _FakeLoop:
    def __init__(self, mapping):
        self._mapping = mapping

    async def getaddrinfo(self, host, port, *args, **kwargs):
        return [_FakeAddrInfo(self._mapping.get(host, "93.184.216.34"))]


@pytest.mark.asyncio
async def test_rejects_private_and_loopback(monkeypatch):
    mapping = {
        "127.0.0.1": "127.0.0.1",
        "localhost": "127.0.0.1",
        "private.test": "10.0.0.5",
        "metadata.test": "169.254.169.254",
    }

    monkeypatch.setattr(
        "src.shared.core.safe_url.asyncio.get_running_loop",
        lambda: _FakeLoop(mapping),
    )
    assert await is_safe_url("http://127.0.0.1/") is False
    assert await is_safe_url("http://localhost/") is False
    assert await is_safe_url("https://private.test/") is False
    assert await is_safe_url("https://metadata.test/latest/meta-data/") is False
    assert await is_safe_url("https://example.com/") is True


@pytest.mark.asyncio
async def test_rejects_unsafe_schemes_and_credentials():
    assert await is_safe_url("ftp://example.com/file") is False
    assert await is_safe_url("file:///etc/passwd") is False
    assert await is_safe_url("http://user@example.com/") is False
    assert await is_safe_url("http://user:pass@internal.test/") is False
    assert await is_safe_url("https://example.com/") is True
