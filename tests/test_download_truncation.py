"""``max_bytes``로 잘린 다운로드가 ``truncated`` 신호로 남는지 end-to-end 검증.

회귀 방지 대상: ``download_artifact()``/``download_geometries()``가
``max_bytes``로 다운로드를 잘라 놓고도 결과 DTO에 아무 신호를 남기지 않아,
호출자가 완전한 파일을 읽은 것처럼 착각할 수 있던 문제.
"""

from __future__ import annotations

from typing import Any

from knps import KnpsClient


class _FakeResponse:
    def __init__(self, status_code: int, content: bytes, text: str = "") -> None:
        self.status_code = status_code
        self.content = content
        self.text = text


class _FixedContentSession:
    """호출할 때마다 같은 bytes를 돌려주는 fake 비동기 session (스트리밍 아님)."""

    def __init__(self, content: bytes) -> None:
        self._content = content

    async def get(self, url: str, **kwargs: Any) -> _FakeResponse:  # noqa: ARG002
        return _FakeResponse(status_code=200, content=self._content)

    async def aclose(self) -> None:
        return None


async def test_download_artifact_flags_truncated_download() -> None:
    full_csv = "이름,값\n지리산,1\n설악산,2\n계룡산,3\n".encode()
    session = _FixedContentSession(full_csv)
    max_bytes = 10  # 전체 bytes보다 훨씬 짧게 잘라 truncation을 강제한다.
    assert max_bytes < len(full_csv)

    async with KnpsClient(session=session, max_rps=None) as client:  # type: ignore[arg-type]
        artifact = await client.files.download_artifact(
            "knps_lod_table_catalog", max_bytes=max_bytes
        )

    assert artifact.truncated is True
    assert artifact.size_bytes == max_bytes


async def test_download_artifact_does_not_flag_complete_download() -> None:
    full_csv = "이름,값\n지리산,1\n".encode()
    session = _FixedContentSession(full_csv)

    async with KnpsClient(session=session, max_rps=None) as client:  # type: ignore[arg-type]
        artifact = await client.files.download_artifact("knps_lod_table_catalog")

    assert artifact.truncated is False
    assert artifact.size_bytes == len(full_csv)


async def test_download_geometries_flags_truncated_download() -> None:
    full_csv = "이름,경도,위도\na,127.1,37.1\nb,127.2,37.2\nc,127.3,37.3\n".encode()
    session = _FixedContentSession(full_csv)
    max_bytes = 20
    assert max_bytes < len(full_csv)

    async with KnpsClient(session=session, max_rps=None) as client:  # type: ignore[arg-type]
        collection = await client.files.download_geometries(
            "knps_visitor_centers", max_bytes=max_bytes
        )

    assert collection.truncated is True
