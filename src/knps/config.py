"""런타임 설정 로딩."""

from __future__ import annotations

import ipaddress
import os
import urllib.parse
from dataclasses import dataclass, field

from .exceptions import KnpsRequestError, KnpsStorageError

DEFAULT_TIMEOUT = 10.0
DEFAULT_MAX_RPS = 5.0


@dataclass(frozen=True, slots=True)
class KnpsConfig:
    """명시 인자에서 만든 KNPS 파일데이터 실행 설정."""

    timeout: float = DEFAULT_TIMEOUT
    max_rps: float = DEFAULT_MAX_RPS
    rustfs_endpoint_url: str | None = None
    rustfs_bucket: str | None = None
    rustfs_access_key: str | None = field(default=None, repr=False)
    rustfs_secret_key: str | None = field(default=None, repr=False)
    rustfs_region: str = "us-east-1"

    @classmethod
    def from_env(
        cls,
        *,
        timeout: float | str | None = None,
        max_rps: float | str | None = None,
        rustfs_endpoint_url: str | None = None,
        rustfs_bucket: str | None = None,
        rustfs_access_key: str | None = None,
        rustfs_secret_key: str | None = None,
        rustfs_region: str | None = None,
    ) -> KnpsConfig:
        resolved_endpoint_url = (
            rustfs_endpoint_url
            or os.environ.get("KNPS_RUSTFS_ENDPOINT_URL")
            or os.environ.get("RUSTFS_ENDPOINT_URL")
            or os.environ.get("KRTOUR_MAP_OBJECT_STORE_ENDPOINT_URL")
        )
        if resolved_endpoint_url:
            _validate_rustfs_endpoint_url(resolved_endpoint_url)
        return cls(
            timeout=_resolve_positive_float(timeout, default=DEFAULT_TIMEOUT, field_name="timeout"),
            max_rps=_resolve_positive_float(max_rps, default=DEFAULT_MAX_RPS, field_name="max_rps"),
            rustfs_endpoint_url=resolved_endpoint_url,
            rustfs_bucket=(
                rustfs_bucket
                or os.environ.get("KNPS_RUSTFS_BUCKET")
                or os.environ.get("RUSTFS_BUCKET")
                or os.environ.get("KRTOUR_MAP_OBJECT_STORE_BUCKET")
                or "knps"
            ),
            rustfs_access_key=(
                rustfs_access_key
                or os.environ.get("KNPS_RUSTFS_ACCESS_KEY")
                or os.environ.get("RUSTFS_ACCESS_KEY")
                or os.environ.get("KNPS_RUSTFS_ACCESS_KEY_ID")
                or os.environ.get("RUSTFS_ACCESS_KEY_ID")
                or os.environ.get("KRTOUR_MAP_OBJECT_STORE_ACCESS_KEY_ID")
            ),
            rustfs_secret_key=(
                rustfs_secret_key
                or os.environ.get("KNPS_RUSTFS_SECRET_KEY")
                or os.environ.get("RUSTFS_SECRET_KEY")
                or os.environ.get("KNPS_RUSTFS_SECRET_ACCESS_KEY")
                or os.environ.get("RUSTFS_SECRET_ACCESS_KEY")
                or os.environ.get("KRTOUR_MAP_OBJECT_STORE_SECRET_ACCESS_KEY")
            ),
            rustfs_region=(
                rustfs_region
                or os.environ.get("KNPS_RUSTFS_REGION")
                or os.environ.get("RUSTFS_REGION")
                or os.environ.get("KRTOUR_MAP_OBJECT_STORE_REGION")
                or "us-east-1"
            ),
        )


def _resolve_positive_float(
    value: float | str | None,
    *,
    default: float,
    field_name: str,
) -> float:
    if value is None or value == "":
        return default
    try:
        resolved = float(value)
    except (TypeError, ValueError) as exc:
        raise KnpsRequestError(
            f"{field_name} must be a positive number", failure_kind="config"
        ) from exc
    if resolved <= 0:
        raise KnpsRequestError(f"{field_name} must be greater than 0", failure_kind="config")
    return resolved


def _validate_rustfs_endpoint_url(url: str) -> None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme == "https":
        return
    if parsed.scheme == "http" and _is_loopback_host(parsed.hostname):
        return
    raise KnpsStorageError(
        f"rustfs_endpoint_url must use https:// (got scheme {parsed.scheme!r}); "
        "http is only permitted for loopback endpoints",
        provider="rustfs",
        failure_kind="config",
    )


def _is_loopback_host(hostname: str | None) -> bool:
    if hostname is None:
        return False
    if hostname == "localhost":
        return True
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False
