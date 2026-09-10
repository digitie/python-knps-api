"""async 다운로드 경로가 CPU-bound 파싱/정규화를 이벤트 루프 밖으로 offload하는지 검증.

회귀 방지 대상: ``download_artifact()``/``download_geometries()``/
``read_place_records()``/``read_geo_records()``가 ``read_file_artifact()``/
``extract_geometries()``/CSV 파싱/Pydantic 정규화를 `asyncio.to_thread` 없이
코루틴 안에서 직접 호출해 이벤트 루프를 막던 문제(#9 knps_trails 실측
910,110 vertex 행 기준으로 특히 심각).
"""

from __future__ import annotations

import threading
from typing import Any

from knps import KnpsClient
from knps import files as files_module


class _FakeResponse:
    def __init__(self, status_code: int, content: bytes, text: str = "") -> None:
        self.status_code = status_code
        self.content = content
        self.text = text


class _FixedContentSession:
    def __init__(self, content: bytes) -> None:
        self._content = content

    async def get(self, url: str, **kwargs: Any) -> _FakeResponse:  # noqa: ARG002
        return _FakeResponse(status_code=200, content=self._content)

    async def aclose(self) -> None:
        return None


async def test_download_artifact_offloads_parsing_to_thread(monkeypatch) -> None:
    main_thread = threading.current_thread()
    call_threads: list[threading.Thread] = []
    real_read_file_artifact = files_module.read_file_artifact

    def _tracking_read_file_artifact(*args: Any, **kwargs: Any) -> Any:
        call_threads.append(threading.current_thread())
        return real_read_file_artifact(*args, **kwargs)

    monkeypatch.setattr(files_module, "read_file_artifact", _tracking_read_file_artifact)

    session = _FixedContentSession("이름,값\n지리산,1\n".encode())
    async with KnpsClient(session=session, max_rps=None) as client:  # type: ignore[arg-type]
        await client.files.download_artifact("knps_lod_table_catalog")

    assert len(call_threads) == 1
    assert call_threads[0] is not main_thread


async def test_download_geometries_offloads_parsing_to_thread(monkeypatch) -> None:
    main_thread = threading.current_thread()
    call_threads: list[threading.Thread] = []
    real_extract_geometries = files_module.extract_geometries

    def _tracking_extract_geometries(*args: Any, **kwargs: Any) -> Any:
        call_threads.append(threading.current_thread())
        return real_extract_geometries(*args, **kwargs)

    monkeypatch.setattr(files_module, "extract_geometries", _tracking_extract_geometries)

    session = _FixedContentSession("이름,경도,위도\na,127.1,37.1\n".encode())
    async with KnpsClient(session=session, max_rps=None) as client:  # type: ignore[arg-type]
        await client.files.download_geometries("knps_visitor_centers")

    assert len(call_threads) == 1
    assert call_threads[0] is not main_thread


async def test_read_place_records_offloads_normalization_to_thread(monkeypatch) -> None:
    main_thread = threading.current_thread()
    call_threads: list[threading.Thread] = []
    real_read_place_records = files_module._read_place_records

    def _tracking(*args: Any, **kwargs: Any) -> Any:
        call_threads.append(threading.current_thread())
        return real_read_place_records(*args, **kwargs)

    monkeypatch.setattr(files_module, "_read_place_records", _tracking)

    session = _FixedContentSession("이름,경도,위도\na,127.1,37.1\n".encode())
    async with KnpsClient(session=session, max_rps=None) as client:  # type: ignore[arg-type]
        await client.files.read_place_records("knps_visitor_centers")

    assert len(call_threads) == 1
    assert call_threads[0] is not main_thread


async def test_read_geo_records_offloads_normalization_to_thread(monkeypatch) -> None:
    main_thread = threading.current_thread()
    call_threads: list[threading.Thread] = []
    real_normalize_geo_records = files_module._normalize_geo_records

    def _tracking(*args: Any, **kwargs: Any) -> Any:
        call_threads.append(threading.current_thread())
        return real_normalize_geo_records(*args, **kwargs)

    monkeypatch.setattr(files_module, "_normalize_geo_records", _tracking)

    session = _FixedContentSession("이름,경도,위도\na,127.1,37.1\n".encode())
    async with KnpsClient(session=session, max_rps=None) as client:  # type: ignore[arg-type]
        await client.files.read_geo_records("knps_visitor_centers")

    assert len(call_threads) == 1
    assert call_threads[0] is not main_thread
