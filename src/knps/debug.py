"""디버그 UI와 fixture 저장에 공통으로 쓰는 보조 기능.

``examples/streamlit_debug_ui.py``가 이 모듈에 의존한다. Streamlit 자체는
optional dependency(``debug-ui`` extra)이므로, 이 모듈은 streamlit/pandas를
import하지 않는다 — 순수 표준 라이브러리 + knps 내부 타입만 사용해서 core
설치(``pip install python-knps-api``)에서도 문제없이 import되고, pytest로
직접 테스트할 수 있다.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
import traceback
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from os import PathLike
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
from zoneinfo import ZoneInfo

from pydantic import BaseModel

from .catalog import DatasetOperation, file_dataset
from .exceptions import KnpsApiError, KnpsRequestError
from .models import FileArtifact, FileDataset, GeoFeatureCollection

if TYPE_CHECKING:
    from .client import KnpsClient

SENSITIVE_KEYS = {
    "authorization",
    "x-api-key",
    "api_key",
    "apikey",
    "service_key",
    "servicekey",
    "service-key",
    "access_token",
    "refresh_token",
    "access_key",
    "secret_key",
    "rustfs_access_key",
    "rustfs_secret_key",
    "access_key_id",
    "secret_access_key",
    "aws_access_key_id",
    "aws_secret_access_key",
}
DEFAULT_ASSERTION = {
    "mode": "snapshot",
    "exclude_fields": ["fetched_at", "request_id", "updated_at"],
    "required_fields": [],
}

# DatasetOperation.key -> FileDataNamespace 메서드 이름. 두 값은 항상
# 같지만(카탈로그가 실제 메서드 이름으로 key를 선언한다는 계약), 이 표를 통해
# routing해서 "알 수 없는 operation" 요청을 명시적으로 거부할 수 있게 한다.
_OPERATION_METHODS: dict[str, str] = {
    "download_artifact": "download_artifact",
    "download_geometries": "download_geometries",
    "read_geo_records": "read_geo_records",
    "read_place_records": "read_place_records",
    "download_to_rustfs": "download_to_rustfs",
}


@dataclass(frozen=True)
class DebugRun:
    """디버그 UI 오퍼레이션 한 번의 입력, 요청, 응답, 파싱, 가공 결과 묶음."""

    function: str
    input: dict[str, Any]
    request: dict[str, Any]
    response: dict[str, Any]
    parsed: Any
    processed: Any
    trace: list[str]
    error: dict[str, Any] | None = None
    catalog: dict[str, Any] | None = None


def jsonable(obj: Any) -> Any:
    """Pydantic v2 모델과 날짜 값을 JSON으로 저장 가능한 값으로 변환합니다."""

    if isinstance(obj, BaseModel):
        return obj.model_dump(mode="json")
    if isinstance(obj, Mapping):
        return {str(key): jsonable(value) for key, value in obj.items()}
    if isinstance(obj, (list, tuple, set, frozenset)):
        return [jsonable(item) for item in obj]
    if isinstance(obj, datetime | date):
        return obj.isoformat()
    if isinstance(obj, Path):
        return str(obj)
    return obj


def redact_sensitive(obj: Any) -> Any:
    """dict/list 구조에서 API key/token/자격증명 성격의 값을 마스킹합니다."""

    if isinstance(obj, Mapping):
        redacted: dict[str, Any] = {}
        for key, value in obj.items():
            text_key = str(key)
            if text_key.lower() in SENSITIVE_KEYS:
                redacted[text_key] = "<REDACTED>"
            else:
                redacted[text_key] = redact_sensitive(value)
        return redacted
    if isinstance(obj, list | tuple):
        return [redact_sensitive(item) for item in obj]
    return obj


def debug_error(exc: Exception) -> dict[str, Any]:
    """예외를 디버그 UI/fixture에 넣기 쉬운 dict로 변환합니다."""

    payload: dict[str, Any] = {
        "type": exc.__class__.__name__,
        "message": str(exc),
        "traceback": "".join(
            traceback.format_exception(type(exc), exc, exc.__traceback__)
        ),
    }
    if isinstance(exc, KnpsApiError):
        payload.update(exc.metadata)
    return cast(dict[str, Any], redact_sensitive(payload))


def save_fixture(
    *,
    base_dir: str | PathLike[str],
    function_name: str,
    case_name: str,
    description: str,
    input_data: Any,
    request_data: Any,
    response_data: Any,
    parsed_result: Any,
    processed_result: Any,
    assertion: Mapping[str, Any] | None = None,
    library_version: str | None = None,
    overwrite: bool = False,
) -> Path:
    """디버그 실행 결과를 pytest replay용 fixture JSON 파일로 저장합니다."""

    safe_case_name = slugify_case_name(case_name)
    fixture_dir = Path(base_dir) / function_name
    fixture_dir.mkdir(parents=True, exist_ok=True)
    fixture_path = fixture_dir / f"{safe_case_name}.json"
    if fixture_path.exists() and not overwrite:
        raise FileExistsError(f"Fixture already exists: {fixture_path}")

    fixture = {
        "name": safe_case_name,
        "function": function_name,
        "description": description,
        "input": redact_sensitive(jsonable(input_data)),
        "request": redact_sensitive(jsonable(request_data)),
        "response": redact_sensitive(jsonable(response_data)),
        "parsed": jsonable(parsed_result),
        "processed": jsonable(processed_result),
        "assertion": dict(assertion or DEFAULT_ASSERTION),
        "meta": {
            "created_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(),
            "library_version": library_version,
            "source": "debug_ui",
        },
    }
    with fixture_path.open("w", encoding="utf-8") as handle:
        json.dump(fixture, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return fixture_path


def slugify_case_name(value: str) -> str:
    """fixture 파일명에 쓸 수 있도록 case 이름을 느슨하게 정규화합니다."""

    cleaned = value.strip().lower()
    slug = re.sub(r"[^\w.-]+", "-", cleaned, flags=re.UNICODE)
    slug = re.sub(r"-{2,}", "-", slug).strip("-._")
    return slug or "case"


def resolve_operation_kwargs(
    operation: DatasetOperation,
    dataset: FileDataset,
    raw_values: Mapping[str, str | bool],
) -> dict[str, Any]:
    """UI에서 입력받은 문자열/불리언 값을 오퍼레이션 kwargs로 타입 변환합니다.

    빈 문자열(선택 파라미터)은 결과 dict에서 제외되어 클라이언트 메서드의
    기본값을 그대로 쓴다. 파라미터 타입은 ``OperationParam.kind``로만
    분기한다 — 오퍼레이션이나 dataset 이름별 특수 분기는 없다.
    """

    kwargs: dict[str, Any] = {}
    for param in operation.params:
        value = raw_values.get(param.name)
        if param.kind == "bool":
            kwargs[param.name] = bool(value)
            continue
        text = str(value if value is not None else "").strip()
        if not text:
            continue
        if param.kind == "int":
            kwargs[param.name] = int(text)
        else:
            kwargs[param.name] = text
    return kwargs


def _response_summary(result: Any) -> dict[str, Any]:
    """오퍼레이션 결과 타입에서 "raw response"에 해당하는 요약 정보를 뽑는다.

    이 API는 JSON envelope가 아니라 파일 bytes를 반환하므로, 실제 raw bytes를
    다시 노출하는 대신(재다운로드를 피하기 위해) 결과 타입에서 파생 가능한
    요약을 만든다. 분기는 결과의 **타입**(FileArtifact/GeoFeatureCollection/
    tuple/str)에만 의존하며 dataset이나 operation 이름과 무관하다.
    """

    if isinstance(result, FileArtifact):
        return {
            "kind": result.kind,
            "size_bytes": result.size_bytes,
            "member_count": len(result.members),
            "csv_preview_count": len(result.csv_previews),
        }
    if isinstance(result, GeoFeatureCollection):
        return {
            "member_name": result.member_name,
            "geometry_type": result.geometry_type,
            "source_crs": result.source_crs,
            "crs": result.crs,
            "feature_count": len(result.features),
        }
    if isinstance(result, tuple):
        return {"record_count": len(result)}
    if isinstance(result, str):
        return {"object_key": result}
    return {}


def _processed_view(result: Any) -> Any:
    """결과를 "Processed Result" 탭이 리스트/단일로 분기할 수 있는 형태로 만든다."""

    if isinstance(result, tuple):
        return list(result)
    if isinstance(result, GeoFeatureCollection):
        return list(result.features)
    if isinstance(result, FileArtifact):
        return list(result.csv_previews)
    if isinstance(result, str):
        return {"object_key": result}
    return result


async def arun_dataset_operation(
    client: KnpsClient,
    dataset_key: str,
    operation: DatasetOperation,
    kwargs: Mapping[str, Any],
) -> DebugRun:
    """카탈로그가 선언한 오퍼레이션을 ``client.files``에 동적으로 routing합니다.

    하드코딩된 ``if operation.key == "...":`` 분기 대신 ``getattr``로 실제
    :class:`~knps.files.FileDataNamespace` 메서드를 찾아 호출한다.
    """

    trace: list[str] = [f"dataset lookup: {dataset_key}", f"operation: {operation.key}"]
    input_data = redact_sensitive(
        {"dataset_key": dataset_key, "operation": operation.key, "kwargs": dict(kwargs)}
    )

    try:
        dataset = file_dataset(dataset_key)
    except KnpsApiError as exc:
        trace.append(f"dataset lookup 실패: {exc.__class__.__name__}")
        return DebugRun(
            function=operation.key,
            input=input_data,
            request={},
            response={},
            parsed=None,
            processed=None,
            trace=trace,
            error=debug_error(exc),
        )

    catalog_payload = jsonable(dataset)
    method_name = _OPERATION_METHODS.get(operation.key)
    method = getattr(client.files, method_name, None) if method_name else None
    request = {
        "dataset_key": dataset_key,
        "operation": operation.key,
        "method": f"client.files.{method_name}",
        "download_url": dataset.download_url,
        "params": redact_sensitive(dict(kwargs)),
    }
    trace.append(f"다운로드 URL: {dataset.download_url or 'n/a'}")

    if method is None or not callable(method):
        unknown_op_error = KnpsRequestError(
            f"unknown debug operation: {operation.key}",
            provider=dataset.provider,
            endpoint=dataset.key,
            failure_kind="unknown_operation",
        )
        trace.append("알 수 없는 operation")
        return DebugRun(
            function=operation.key,
            input=input_data,
            request=request,
            response={},
            parsed=None,
            processed=None,
            trace=trace,
            error=debug_error(unknown_op_error),
            catalog=catalog_payload,
        )

    start = time.perf_counter()
    try:
        result = await method(dataset_key, **kwargs)
    except Exception as exc:  # noqa: BLE001 - 디버그 UI는 모든 실패를 구조화해서 보여줘야 한다
        elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
        trace.append(f"실행 실패: {exc.__class__.__name__} ({elapsed_ms}ms)")
        return DebugRun(
            function=operation.key,
            input=input_data,
            request=request,
            response={"status": "error", "elapsed_ms": elapsed_ms},
            parsed=None,
            processed=None,
            trace=trace,
            error=debug_error(exc),
            catalog=catalog_payload,
        )

    elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
    trace.append(f"실행 성공 ({elapsed_ms}ms)")
    response = {
        "status": "ok",
        "elapsed_ms": elapsed_ms,
        "result_type": type(result).__name__,
        **_response_summary(result),
    }
    return DebugRun(
        function=operation.key,
        input=input_data,
        request=request,
        response=response,
        parsed=result,
        processed=_processed_view(result),
        trace=trace,
        catalog=catalog_payload,
    )


async def _arun_and_close(
    client: KnpsClient,
    dataset_key: str,
    operation: DatasetOperation,
    kwargs: Mapping[str, Any],
) -> DebugRun:
    try:
        return await arun_dataset_operation(client, dataset_key, operation, kwargs)
    finally:
        await client.aclose()


def run_dataset_operation(
    client: KnpsClient,
    dataset_key: str,
    operation: DatasetOperation,
    kwargs: Mapping[str, Any],
) -> DebugRun:
    """Streamlit 같은 동기 문맥에서 쓰는 :func:`arun_dataset_operation` wrapper.

    ``client``의 소유권을 넘겨받아 실행 후 ``client.aclose()``까지 같은
    이벤트 루프 안에서 처리한다 — 호출부(Streamlit)는 매 실행마다 새
    :class:`KnpsClient`를 만들어 넘기기만 하면 된다.
    """

    return asyncio.run(_arun_and_close(client, dataset_key, operation, kwargs))
