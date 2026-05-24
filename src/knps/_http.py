"""KNPS와 data.go.kr API 비동기 HTTP helper."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol, cast

import httpx

from ._convert import (
    mask_params,
    normalize_items,
    public_params,
    redact_secret,
    to_int_or_none,
    without_none,
    xml_to_dict,
)
from ._ratelimit import AsyncTokenBucket
from .exceptions import (
    KnpsAuthError,
    KnpsParseError,
    KnpsRateLimitError,
    KnpsRequestError,
    KnpsServerError,
)
from .models import CallContext


class ResponseLike(Protocol):
    status_code: int
    text: str
    content: bytes

    def json(self) -> Any: ...


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


@dataclass(frozen=True, slots=True)
class NormalizedPayload:
    items: list[dict[str, Any]]
    page_no: int | None
    num_of_rows: int | None
    total_count: int | None
    raw: dict[str, Any]
    header: dict[str, Any]
    context: CallContext


class KnpsHttp:
    """data.go.kr 응답 envelope를 처리하는 비동기 HTTP 클라이언트."""

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

    async def get(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        *,
        provider: str,
        endpoint: str,
        response_format: str = "json",
        service_key_param: str | None = None,
        response_type_param: str | None = "_type",
    ) -> NormalizedPayload:
        key_param = service_key_param or self.service_key_param
        query: dict[str, Any] = {key_param: self.api_key}
        if provider == "data.go.kr" and response_format.lower() == "json":
            query[response_type_param or "_type"] = "json"
        if params:
            query.update(params)

        safe_context = CallContext(
            provider=provider,
            endpoint=endpoint,
            request_url=url,
            request_params=public_params(query),
            collected_at=datetime.now(UTC),
        )
        if self._rate_limiter is not None:
            await self._rate_limiter.acquire()
        try:
            response = await self.session.get(url, params=without_none(query), timeout=self.timeout)
        except httpx.HTTPError as exc:
            message = redact_secret(str(exc), self.api_key)
            raise KnpsRequestError(
                f"request failed: {message}",
                provider=provider,
                endpoint=endpoint,
                params=mask_params(query),
                failure_kind="network",
            ) from exc
        _raise_for_status(
            response,
            provider=provider,
            endpoint=endpoint,
            api_key=self.api_key,
            params=query,
        )

        payload = _decode_payload(
            response,
            provider=provider,
            endpoint=endpoint,
            api_key=self.api_key,
            response_format=response_format,
        )
        return _normalize_payload(
            payload,
            provider=provider,
            endpoint=endpoint,
            context=safe_context,
        )

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
            message = redact_secret(str(exc), self.api_key)
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
            params={},
        )
        data = getattr(response, "content", b"")
        return data if max_bytes is None else data[:max_bytes]


def _decode_payload(
    response: ResponseLike,
    *,
    provider: str,
    endpoint: str,
    api_key: str,
    response_format: str,
) -> dict[str, Any]:
    text = response.text.strip()
    try_json = response_format.lower() == "json" or text.startswith("{")
    if try_json:
        try:
            payload = response.json()
        except ValueError:
            if not text.startswith("<"):
                message = redact_secret(text[:300], api_key)
                raise KnpsParseError(
                    f"json parse failed: {message}",
                    provider=provider,
                    endpoint=endpoint,
                    failure_kind="parse",
                ) from None
        else:
            if isinstance(payload, dict):
                return payload
            raise KnpsParseError(
                "json root must be an object",
                provider=provider,
                endpoint=endpoint,
                failure_kind="parse",
            )
    try:
        return xml_to_dict(text)
    except Exception as exc:
        message = redact_secret(text[:300], api_key)
        raise KnpsParseError(
            f"xml parse failed: {message}",
            provider=provider,
            endpoint=endpoint,
            failure_kind="parse",
        ) from exc


def _normalize_payload(
    payload: dict[str, Any],
    *,
    provider: str,
    endpoint: str,
    context: CallContext,
) -> NormalizedPayload:
    root = payload.get("response", payload)
    if not isinstance(root, dict):
        root = payload
    header = root.get("header") if isinstance(root.get("header"), dict) else {}
    body = root.get("body") if isinstance(root.get("body"), dict) else root
    result_code = str(header.get("resultCode") or header.get("result_code") or "")
    result_message = str(header.get("resultMsg") or header.get("result_msg") or "")
    if result_code and result_code not in {"00", "0", "0000", "NORMAL_CODE"}:
        rate_limit_codes = {"22", "LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS_ERROR"}
        error_cls = KnpsRateLimitError if result_code in rate_limit_codes else KnpsRequestError
        raise error_cls(
            result_message or f"remote error resultCode={result_code}",
            provider=provider,
            endpoint=endpoint,
            result_code=result_code,
            response=payload,
            failure_kind="remote",
        )

    items = normalize_items(body.get("items") if isinstance(body, dict) else None)
    page_no = None
    if isinstance(body, dict):
        page_no = to_int_or_none(body.get("pageNo") or body.get("page_no"))
    num_of_rows = (
        to_int_or_none(body.get("numOfRows") or body.get("num_of_rows"))
        if isinstance(body, dict)
        else None
    )
    total_count = (
        to_int_or_none(body.get("totalCount") or body.get("total_count"))
        if isinstance(body, dict)
        else None
    )
    return NormalizedPayload(
        items=items,
        page_no=page_no,
        num_of_rows=num_of_rows,
        total_count=total_count,
        raw=payload,
        header=header,
        context=context,
    )


def _raise_for_status(
    response: ResponseLike,
    *,
    provider: str,
    endpoint: str,
    api_key: str,
    params: dict[str, Any],
) -> None:
    status = response.status_code
    if status < 400:
        return
    message = redact_secret(response.text[:300], api_key)
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
        params=mask_params(params),
        failure_kind=failure_kind,
    )
