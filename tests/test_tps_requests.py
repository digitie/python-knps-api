"""일반 응답과 스트리밍 재시도의 TPS 예산을 검증한다."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx

from knps._http import KnpsHttp


async def test_fake_session_retry_takes_a_token_per_attempt(monkeypatch):
    session = SimpleNamespace(
        get=AsyncMock(
            side_effect=[
                SimpleNamespace(status_code=503, text="retry", content=b""),
                SimpleNamespace(status_code=200, text="ok", content=b"data"),
            ]
        )
    )
    client = KnpsHttp(session=session)
    acquire = AsyncMock(wraps=client._rate_limiter.acquire)
    monkeypatch.setattr(client._rate_limiter, "acquire", acquire)
    assert await client.get_bytes("https://example.invalid/file") == b"data"
    assert acquire.await_count == session.get.await_count == 2


async def test_streaming_retry_takes_a_token_per_attempt(monkeypatch):
    attempts = 0
    acquisitions = []

    async def handler(request):
        nonlocal attempts
        attempts += 1
        acquisitions.append(acquire.await_count)
        return httpx.Response(503 if attempts == 1 else 200, content=b"data")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as session:
        client = KnpsHttp(session=session)
        acquire = AsyncMock(wraps=client._rate_limiter.acquire)
        monkeypatch.setattr(client._rate_limiter, "acquire", acquire)
        assert await client.get_bytes("https://example.invalid/file") == b"data"
    assert attempts == acquire.await_count == 2
    assert acquisitions == [1, 2]


async def test_streaming_redirect_takes_another_token(monkeypatch):
    acquisitions = []
    responses = []

    async def handler(request):
        acquisitions.append(acquire.await_count)
        response = (
            httpx.Response(302, headers={"location": "/final"})
            if len(acquisitions) == 1
            else httpx.Response(200, content=b"data")
        )
        responses.append(response)
        return response

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), follow_redirects=True
    ) as session:
        client = KnpsHttp(session=session, max_rps=1000)
        acquire = AsyncMock(wraps=client._rate_limiter.acquire)
        monkeypatch.setattr(client._rate_limiter, "acquire", acquire)
        assert await client.get_bytes("https://example.invalid/file") == b"data"
    assert acquisitions == [1, 2]
    assert all(response.is_closed for response in responses)
