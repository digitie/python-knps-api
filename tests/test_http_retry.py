"""``KnpsHttp._get_with_retry``의 재시도 정책 테스트."""

from __future__ import annotations

from typing import Any

import pytest

from knps._http import KnpsHttp
from knps.exceptions import KnpsRequestError, KnpsServerError


class _FakeResponse:
    def __init__(self, status_code: int, content: bytes = b"ok", text: str = "") -> None:
        self.status_code = status_code
        self.content = content
        self.text = text


class _ScriptedSession:
    """미리 정해진 status sequence를 차례로 돌려주는 fake session."""

    def __init__(self, statuses: list[int]) -> None:
        self._statuses = statuses
        self.calls = 0

    async def get(self, url: str, **kwargs: Any) -> _FakeResponse:  # noqa: ARG002
        idx = min(self.calls, len(self._statuses) - 1)
        self.calls += 1
        return _FakeResponse(status_code=self._statuses[idx])

    async def aclose(self) -> None:
        return None


async def _make_http(session: _ScriptedSession) -> KnpsHttp:
    return KnpsHttp(session=session, max_rps=None, timeout=1.0)  # type: ignore[arg-type]


async def test_get_bytes_retries_after_transient_5xx_then_succeeds() -> None:
    """첫 두 번 503, 세 번째 200이면 최종적으로 bytes를 받아온다."""

    session = _ScriptedSession([503, 503, 200])
    http = await _make_http(session)
    try:
        data = await http.get_bytes("https://example/test")
    finally:
        await http.aclose()

    assert data == b"ok"
    assert session.calls == 3


async def test_get_bytes_retries_after_429_then_succeeds() -> None:
    """일시적 429도 재시도 대상."""

    session = _ScriptedSession([429, 200])
    http = await _make_http(session)
    try:
        data = await http.get_bytes("https://example/test")
    finally:
        await http.aclose()

    assert data == b"ok"
    assert session.calls == 2


async def test_get_bytes_persistent_5xx_raises_server_error() -> None:
    """3회 모두 5xx면 마지막 응답을 raise_for_status가 ``KnpsServerError``로 변환한다."""

    session = _ScriptedSession([502, 502, 502])
    http = await _make_http(session)
    try:
        with pytest.raises(KnpsServerError):
            await http.get_bytes("https://example/test")
    finally:
        await http.aclose()

    assert session.calls == 3


async def test_get_bytes_does_not_retry_client_errors() -> None:
    """404 같은 client error는 재시도하지 않는다."""

    session = _ScriptedSession([404])
    http = await _make_http(session)
    try:
        with pytest.raises(KnpsRequestError):
            await http.get_bytes("https://example/test")
    finally:
        await http.aclose()

    assert session.calls == 1
