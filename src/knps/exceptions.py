"""knps 예외 계층."""

from __future__ import annotations

from typing import Any


class KnpsApiError(Exception):
    """모든 knps 예외의 기반 클래스."""

    def __init__(
        self,
        message: str,
        *,
        provider: str | None = None,
        endpoint: str | None = None,
        status_code: int | None = None,
        result_code: str | None = None,
        failure_kind: str | None = None,
        response: Any | None = None,
        params: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.endpoint = endpoint
        self.status_code = status_code
        self.result_code = result_code
        self.failure_kind = failure_kind
        self.response = response
        self.params = params or {}

    @property
    def metadata(self) -> dict[str, Any]:
        """구조화된 오류 메타데이터를 반환한다."""

        return {
            "provider": self.provider,
            "endpoint": self.endpoint,
            "status_code": self.status_code,
            "result_code": self.result_code,
            "failure_kind": self.failure_kind,
            "params": self.params,
        }


class KnpsAuthError(KnpsApiError):
    """인증 실패 또는 서비스 활용신청 미승인 오류."""


class KnpsRateLimitError(KnpsApiError):
    """쿼터 초과 또는 rate limit 오류."""


class KnpsRequestError(KnpsApiError):
    """잘못된 요청 또는 지원하지 않는 파라미터 오류."""


class KnpsServerError(KnpsApiError):
    """원격 서버 오류."""


class KnpsParseError(KnpsApiError):
    """원격 응답을 파싱할 수 없을 때의 오류."""


class KnpsStorageError(KnpsApiError):
    """객체 저장소(S3/RustFS) 또는 로컬 스토리지 입출력 실패 시의 오류."""
