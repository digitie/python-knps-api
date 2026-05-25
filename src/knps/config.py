"""런타임 설정 로딩."""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_TIMEOUT = 10.0
DEFAULT_MAX_RPS = 5.0


@dataclass(frozen=True, slots=True)
class KnpsConfig:
    """명시 인자에서 만든 KNPS 파일데이터 실행 설정."""

    timeout: float = DEFAULT_TIMEOUT
    max_rps: float = DEFAULT_MAX_RPS

    @classmethod
    def from_env(
        cls,
        *,
        timeout: float | str | None = None,
        max_rps: float | str | None = None,
    ) -> KnpsConfig:
        return cls(
            timeout=_resolve_positive_float(timeout, default=DEFAULT_TIMEOUT, field_name="timeout"),
            max_rps=_resolve_positive_float(max_rps, default=DEFAULT_MAX_RPS, field_name="max_rps"),
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
        raise ValueError(f"{field_name} must be a positive number") from exc
    if resolved <= 0:
        raise ValueError(f"{field_name} must be greater than 0")
    return resolved
