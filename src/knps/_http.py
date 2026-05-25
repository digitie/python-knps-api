"""KNPS 파일 다운로드용 비동기 HTTP helper."""

from __future__ import annotations

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
        api_key: str,
        *,
        timeout: float = 10.0,
        session: AsyncSessionLike | None = None,
        service_key_param: str = "serviceKey",
        max_rps: float | None = 5.0,
    ) -> None:
        api_key = "".join(str(api_key).split())
        if not api_key:
            raise KnpsAuthError("api_key is required", failure_kind="auth")
        if not service_key_param:
            raise ValueError("service_key_param must not be empty")
        self.api_key = api_key
        self.timeout = timeout
        self.session = session or _new_session(timeout)
        self._owns_session = session is None
        self.service_key_param = service_key_param
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
        try:
            response = await self.session.get(url, timeout=self.timeout)
        except httpx.HTTPError as exc:
            message = _redact_secret(str(exc), self.api_key)
            raise KnpsRequestError(
                f"request failed: {message}",
                provider=provider,
                endpoint=endpoint or url,
                failure_kind="network",
            ) from exc
        _raise_for_status(
            response,
            provider=provider,
            endpoint=endpoint or url,
            api_key=self.api_key,
        )
        data = getattr(response, "content", b"")
        return data if max_bytes is None else data[:max_bytes]


def _raise_for_status(
    response: ResponseLike,
    *,
    provider: str,
    endpoint: str,
    api_key: str,
) -> None:
    status = response.status_code
    if status < 400:
        return
    message = _redact_secret(response.text[:300], api_key)
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


def _redact_secret(text: str, secret: str) -> str:
    if not secret:
        return text
    return text.replace(secret, "***")
