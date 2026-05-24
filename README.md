# python-knps-api

국립공원공단(KNPS) 공개 API와 파일데이터를 여행, 탐방, 안전, 기상 use case 중심으로 다루는 비공식 async Python client다.

이 package는 `python-mois-api`, `python-krheritage-api`, `python-khoa-api`, `python-krforest-api`와 같은 방향성을 따른다. 기관별 provider 라이브러리를 분리하고, `python-krtour-map`은 이 public client와 typed model/catalog를 직접 사용한다. 인증, rate limit, 예외 계층은 KNPS 전용으로 독립시킨다.

## 문서 언어 정책

이 저장소의 모든 Markdown/RST 문서는 한글로 작성한다. API field, code identifier, 명령어, URL, provider 원문은 필요한 경우 원문을 유지한다.

## 설치

```bash
pip install -e ".[dev]"
```

공간데이터 ZIP/SHP/GeoJSON 파싱을 구현할 때는 선택 의존성을 추가한다.

```bash
pip install -e ".[dev,geo]"
```

## Service key

`KnpsClient`는 data.go.kr 서비스키를 사용한다. `api_key=...`를 직접 넘기거나 `KnpsConfig.from_env()`가 지원 환경 변수를 읽게 한다.

- `DATA_GO_KR_SERVICE_KEY`
- `KNPS_SERVICE_KEY` (프로젝트 전용 override)

```python
import asyncio

from knps import KnpsClient


async def main() -> None:
    async with KnpsClient.from_env() as client:
        for endpoint in client.endpoints():
            print(endpoint.key, endpoint.title)

        for dataset in client.files.datasets("spatial"):
            print(dataset.key, dataset.title, dataset.formats)


asyncio.run(main())
```

## API 예시

```python
import asyncio

from knps import KnpsClient


async def main() -> None:
    async with KnpsClient(api_key="YOUR_DATA_GO_KR_KEY") as client:
        page = await client.raw_endpoint(
            "knps_visitor_statistics",
            {"baseYm": "202501"},
            num_of_rows=10,
        )
        print(page.total_count, page.items[0] if page.items else None)
        print(page.context.request_params)  # service key는 제거된다.


asyncio.run(main())
```

Paged API 응답은 raw item mapping을 담은 `Page`와 안전한 call context를 반환한다. KNPS는 파일 기반 공간데이터 비중이 높으므로 v1 public surface는 catalog와 raw transport를 먼저 안정화하고, SHP/GeoJSON 파서는 `docs/knps-feature-etl.md`의 dataset별 변환 규칙에 맞춰 확장한다.

## File dataset

File-data namespace는 curated catalog를 제공한다. data.go.kr 상세 페이지 또는 직접 다운로드 URL이 확인된 dataset은 `client.files.download(...)`로 bytes를 받을 수 있다. 아직 다운로드 URL 검증이 필요한 dataset은 catalog에서 `verification_status="needs_verification"`으로 표시한다.

```python
async with KnpsClient.from_env() as client:
    for dataset in client.files.datasets():
        print(dataset.key, dataset.data_go_id, dataset.title, dataset.verification_status)
```

## Scope

v1 scope는 `python-krtour-map/docs/forest-feature-etl.md`의 KNPS 통합 계획을 라이브러리로 분리한 것이다.

- 국립공원 경계, 탐방로, 탐방안내소, 위험지역, 기상관측시설, 화장실, 문화자원
- 야영장, 대피소, 입산통제, 산불경보, 추천 탐방코스, 사진/VR, 탐방객 통계
- 파일데이터는 원본 catalog와 bytes download primitive를 제공하고, feature 변환은 downstream ETL에서 수행한다.

## 문서 지도

- [`docs/knps-api.md`](docs/knps-api.md) — KNPS API/file dataset catalog와 client 방향성
- [`docs/knps-feature-etl.md`](docs/knps-feature-etl.md) — `python-krtour-map` feature/notice/weather 적재 계약
- [`docs/decisions.md`](docs/decisions.md) — 프로젝트 기술 및 정책 의사결정
- [`docs/testing.md`](docs/testing.md) — 테스트/fixture/live test 정책

## Reference

Curated scope는 data.go.kr의 국립공원공단 공개 데이터, `python-krtour-map/docs/forest-feature-etl.md`, 그리고 공개 검색으로 확인 가능한 국립공원 공간데이터 안내를 기준으로 작성했다. data.go.kr 검색/상세 페이지는 운영 상태와 로그인 흐름에 따라 응답이 달라질 수 있으므로, ID와 다운로드 URL은 live test에서 계속 검증한다.
