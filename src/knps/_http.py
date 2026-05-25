"""KNPS 파일 다운로드용 비동기 HTTP helper."""

from __future__ import annotations

import asyncio
from typing import Any, Protocol, cast

import httpx

from ._ratelimit import AsyncTokenBucket
from .exceptions import (
    KnpsAuthError,
    KnpsRateLimitError,
    KnpsRequestError,
    KnpsServerError,
)


class ResponseLike(Protocol):
    status_code: int
    text: str
    content: bytes


class AsyncSessionLike(Protocol):
    async def get(self, url: str, **kwargs: Any) -> ResponseLike: ...

    async def aclose(self) -> None: ...


def _new_session(timeout: float) -> AsyncSessionLike:
    return cast(
        AsyncSessionLike,
        httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (compatible; knps/0.1; "
                    "+https://github.com/digitie/python-knps-api)"
                )
            },
        ),
    )


class KnpsHttp:
    """파일 다운로드와 data.go.kr detail asset fetch를 처리하는 비동기 HTTP 클라이언트."""

    def __init__(
        self,
        *,
        timeout: float = 10.0,
        session: AsyncSessionLike | None = None,
        max_rps: float | None = 5.0,
    ) -> None:
        self.timeout = timeout
        self.session = session or _new_session(timeout)
        self._owns_session = session is None
        self._rate_limiter = AsyncTokenBucket(max_rps=max_rps) if max_rps is not None else None

    async def aclose(self) -> None:
        """내부에서 만든 HTTP 세션을 닫는다."""

        if self._owns_session:
            await self.session.aclose()

    async def get_bytes(
        self,
        url: str,
        *,
        max_bytes: int | None = None,
        provider: str = "data.go.kr",
        endpoint: str | None = None,
    ) -> bytes:
        if self._rate_limiter is not None:
            await self._rate_limiter.acquire()
        response = await self._get_with_retry(url, provider=provider, endpoint=endpoint or url)
        _raise_for_status(
            response,
            provider=provider,
            endpoint=endpoint or url,
        )
        data = getattr(response, "content", b"")
        return data if max_bytes is None else data[:max_bytes]

    async def _get_with_retry(
        self,
        url: str,
        *,
        provider: str,
        endpoint: str,
    ) -> ResponseLike:
        last_error: httpx.HTTPError | None = None
        for attempt in range(3):
            try:
                return await self.session.get(url, timeout=self.timeout)
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt == 2:
                    break
                await asyncio.sleep(0.25 * (attempt + 1))
        raise KnpsRequestError(
            f"request failed: {last_error}",
            provider=provider,
            endpoint=endpoint,
            failure_kind="network",
        ) from last_error


def _raise_for_status(
    response: ResponseLike,
    *,
    provider: str,
    endpoint: str,
) -> None:
    status = response.status_code
    if status < 400:
        return
    message = response.text[:300]
    error_cls: type[KnpsRequestError | KnpsAuthError | KnpsRateLimitError | KnpsServerError]
    if status in {401, 403}:
        error_cls = KnpsAuthError
        failure_kind = "auth"
    elif status == 429:
        error_cls = KnpsRateLimitError
        failure_kind = "rate_limit"
    elif status >= 500:
        error_cls = KnpsServerError
        failure_kind = "server"
    else:
        error_cls = KnpsRequestError
        failure_kind = "request"
    raise error_cls(
        f"http {status}: {message}",
        provider=provider,
        endpoint=endpoint,
        status_code=status,
        failure_kind=failure_kind,
    )
