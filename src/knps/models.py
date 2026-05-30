"""knps가 반환하는 Pydantic 모델."""

from __future__ import annotations

from typing import Literal, TypeAlias

from pydantic import BaseModel, ConfigDict

Category: TypeAlias = Literal[
    "park",
    "trail",
    "facility",
    "safety",
    "weather",
    "media",
    "statistics",
    "spatial",
]
Provider: TypeAlias = Literal["data.go.kr", "knps.or.kr"]
CatalogKind: TypeAlias = Literal["file_dataset"]
VerificationStatus: TypeAlias = Literal["verified", "needs_verification", "planned"]
FileArtifactKind: TypeAlias = Literal["zip", "csv", "binary"]
GeometryType: TypeAlias = Literal[
    "Point",
    "MultiPoint",
    "LineString",
    "MultiLineString",
    "Polygon",
    "MultiPolygon",
]

# GeoJSON 좌표는 geometry type에 따라 중첩 깊이가 다르다.
#   Point                       -> Position           (x, y)
#   MultiPoint / LineString     -> Position 의 tuple
#   MultiLineString / Polygon   -> Position tuple 의 tuple
#   MultiPolygon                -> Position tuple tuple 의 tuple
Position: TypeAlias = tuple[float, ...]
LineCoordinates: TypeAlias = tuple[Position, ...]
PolygonCoordinates: TypeAlias = tuple[LineCoordinates, ...]
MultiPolygonCoordinates: TypeAlias = tuple[PolygonCoordinates, ...]
GeometryCoordinates: TypeAlias = (
    Position | LineCoordinates | PolygonCoordinates | MultiPolygonCoordinates
)


class KnpsModel(BaseModel):
    """불변 공개 객체의 기반 모델."""

    model_config = ConfigDict(frozen=True)


class FileDataset(KnpsModel):
    """정리된 KNPS 파일데이터 메타데이터."""

    key: str
    title: str
    data_go_id: str
    categories: tuple[Category, ...]
    formats: tuple[str, ...]
    detail_url: str
    description: str
    provider: Provider = "data.go.kr"
    direct_download: bool = False
    download_url: str | None = None
    geometry_type: str | None = None
    feature_kind: str | None = None
    update_cycle: str | None = None
    verification_status: VerificationStatus = "needs_verification"
    notes: str | None = None


class CatalogEntry(KnpsModel):
    """디버그 UI 표시와 선택에 쓰는 human-readable 카탈로그 항목."""

    kind: CatalogKind
    key: str
    display_name: str
    dataset_id: str
    dataset_name: str
    categories: tuple[Category, ...]
    provider: str
    description: str
    detail_url: str
    url: str | None = None
    formats: tuple[str, ...] = ()
    verification_status: VerificationStatus = "needs_verification"


class FileMember(KnpsModel):
    """다운로드 파일 내부 member 메타데이터."""

    name: str
    size_bytes: int
    compressed_size_bytes: int | None = None


class CsvPreviewRow(KnpsModel):
    """CSV preview row DTO.

    Row 값은 header 순서를 보존하기 위해 ``(header, value)`` tuple의 tuple로
    저장한다. ``KnpsModel``의 frozen은 attribute 재할당만 막아서 내부 dict의
    mutation을 허용했는데, tuple로 두면 진짜 immutable이 된다.

    원본 row가 header 개수보다 많은 컬럼을 가지면 그 trailing 값들은
    ``extra_fields``에 보존되어 손실 없이 표현된다 (data.go.kr CSV에 가끔
    있는 trailing comma 등을 위한 안전장치).

    dict 형태가 필요하면 ``dict(row.values)`` 또는 ``row.as_dict``를 쓴다.
    """

    values: tuple[tuple[str, str | None], ...]
    extra_fields: tuple[str | None, ...] = ()

    @property
    def as_dict(self) -> dict[str, str | None]:
        """``values``를 dict로 변환한 사본을 돌려준다."""

        return dict(self.values)


class CsvPreview(KnpsModel):
    """CSV-like file preview DTO."""

    member_name: str | None = None
    encoding: str
    headers: tuple[str, ...]
    rows: tuple[CsvPreviewRow, ...]


class FileArtifact(KnpsModel):
    """다운로드 bytes를 Pydantic DTO로 읽은 결과."""

    dataset_key: str
    data_go_id: str
    kind: FileArtifactKind
    size_bytes: int
    members: tuple[FileMember, ...] = ()
    csv_previews: tuple[CsvPreview, ...] = ()


def _coordinates_to_lists(coordinates: object) -> object:
    """중첩 tuple 좌표를 GeoJSON 직렬화용 중첩 list로 변환한다."""

    if isinstance(coordinates, (tuple, list)):
        return [_coordinates_to_lists(item) for item in coordinates]
    return coordinates


class Geometry(KnpsModel):
    """GeoJSON 호환 geometry DTO.

    ``coordinates``는 immutable을 위해 중첩 list 대신 중첩 tuple로 보존한다.
    GeoJSON dict가 필요하면 ``as_geojson``을 사용한다.
    """

    type: GeometryType
    coordinates: GeometryCoordinates

    @property
    def as_geojson(self) -> dict[str, object]:
        """``{"type": ..., "coordinates": [...]}`` GeoJSON dict를 돌려준다."""

        return {"type": self.type, "coordinates": _coordinates_to_lists(self.coordinates)}


class GeoFeature(KnpsModel):
    """geometry 1건과 attribute 속성을 보존하는 feature DTO.

    ``properties``는 header 순서를 보존하기 위해 ``(name, value)`` tuple의 tuple로
    저장한다 (``CsvPreviewRow``와 동일한 규약). dict가 필요하면 ``as_dict``를 쓴다.
    geometry가 없는 record는 ``geometry=None``으로 보존한다.
    """

    geometry: Geometry | None = None
    properties: tuple[tuple[str, str | None], ...] = ()

    @property
    def as_dict(self) -> dict[str, str | None]:
        """``properties``를 dict로 변환한 사본을 돌려준다."""

        return dict(self.properties)

    @property
    def as_geojson(self) -> dict[str, object]:
        """GeoJSON ``Feature`` dict를 돌려준다."""

        return {
            "type": "Feature",
            "geometry": None if self.geometry is None else self.geometry.as_geojson,
            "properties": dict(self.properties),
        }


class GeoFeatureCollection(KnpsModel):
    """다운로드 bytes에서 추출한 geometry feature 묶음 DTO.

    ``source_crs``는 원본 좌표계(예: ``EPSG:5179``), ``crs``는 현재
    ``features`` 좌표가 따르는 좌표계다. 좌표를 재투영하면 ``crs``가
    ``source_crs``와 달라지고, 재투영하지 않으면 둘이 같다.
    """

    dataset_key: str
    data_go_id: str
    member_name: str | None = None
    geometry_type: str | None = None
    source_crs: str | None = None
    crs: str | None = None
    features: tuple[GeoFeature, ...] = ()

    @property
    def as_geojson(self) -> dict[str, object]:
        """GeoJSON ``FeatureCollection`` dict를 돌려준다."""

        return {
            "type": "FeatureCollection",
            "features": [feature.as_geojson for feature in self.features],
        }
