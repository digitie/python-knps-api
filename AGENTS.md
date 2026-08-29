# AGENTS.md

이 저장소는 `python-knps-api` 작업 진입점이다.

## 목표

`python-knps-api`(GitHub 저장소 이름 `python-knps-api`, Python 패키지 이름 `knps`)는 국립공원공단(KNPS)의 공개 파일 기반 공간데이터를 가져오는 독립적인 Python API client 및 catalog다. `KnpsClient`는 file dataset catalog 조회, bytes/artifact 다운로드, geometry 추출, typed·정규화 record 변환을 async 인터페이스로 제공한다. 원본 바이트와 메타데이터를 안정적으로 제공하는 데 집중하며, 도메인 특화 feature 변환은 downstream ETL(`python-krtour-map`)의 책임이다.

## Think Before Coding

- 새 file dataset을 catalog에 추가하기 전에 data.go.kr 상세 ID와 다운로드 URL을 실제로 확인한다 — 추정 URL은 `verification_status="needs_verification"`으로만 표시한다(ADR-002).
- CSV header 정규화 규칙을 바꾸기 전에 `knps.records`가 이미 처리하는 header 변종(영문코드 접미사/순한글/weather_stations 별도 코드)에 미치는 영향을 확인한다.
- geometry 좌표계 변환 로직을 건드리기 전에 `.prj`/`source_crs` 유무에 따른 두 경로(재투영 vs 원본 보존)를 모두 검토한다.

## Simplicity First

- feature 변환, notice/weather 적재 같은 도메인 로직을 이 라이브러리에 넣지 않는다 — downstream ETL 책임이다(ADR-003).
- 새 provider 예외나 rate limit 계층을 만들기 전에 `knps.exceptions`/`knps._ratelimit`에 이미 있는 것으로 충분한지 확인한다.
- RustFS 이중 저장처럼 옵션 기능은 기존 다운로드 API를 바꾸지 않고 전용 메서드(`download_to_rustfs`)로 추가한다(ADR-004).

## Surgical Changes

- 한 PR/커밋은 하나의 dataset 또는 하나의 API 표면만 다룬다 — catalog 확장과 normalizer 변경을 섞지 않는다.
- CSV header fallback 체인이나 좌표계 재투영처럼 여러 dataset이 공유하는 경로를 바꿀 때는 영향받는 dataset을 `docs/knps-api.md`의 File datasets 표에서 먼저 확인한다.
- `config.py`의 RustFS 폴백 체인 순서(`KNPS_*` → `RUSTFS_*` → `KRTOUR_MAP_*`)를 이유 없이 재배열하지 않는다 — downstream이 이 순서에 의존한다.

## Goal-Driven Execution

- 작업 후에는 로컬 테스트(`pytest`), live 테스트(`pytest -m live`), 린트(`ruff check src tests`), 타입 체크(`mypy src`)를 통과시킨다.
- 사용자 가시 변경이면 `CHANGELOG.md`를, 구조적 의사결정이 있었으면 `docs/decisions.md`에 ADR을 추가한다.
- `docs/journal.md`(역시간순 작업 기록)와 `docs/tasks.md`(T-NNN 상태)를 갱신해 다음 세션이 현재 상태를 바로 파악하게 한다.

## Practical Bias

- 확인되지 않은 data.go.kr URL이나 미검증 필드로 catalog를 채우지 않는다 — 동작하는 verified dataset부터 완성한다.
- live test가 100% 통과하지 않아도 로컬(non-live) 품질 게이트가 깨끗하면 우선 커밋하고, live 실패는 `docs/journal.md`에 원인과 함께 남긴다.
- 완벽한 typed feature model보다 정확한 raw record + 정규화 필드를 먼저 제공한다(ADR-003과 일치).

## 문서 언어 정책

이 저장소의 **모든 Markdown/RST 문서는 한글로 작성한다**. 예외 없음. `README.md`, `CHANGELOG.md`도 본문은 한글이다.

다음 항목만 영어를 유지한다 — 한글로 옮기면 의미가 변하거나 정확성이 깨지기 때문:

- **코드 식별자**: 함수/클래스/메서드/변수/모듈 이름 (`KnpsClient`, `download_file`, `FileDataset`, `verification_status`).
- **명령어와 경로**: `poetry run pytest`, `ruff check src`, `f:\dev\python-knps-api\src\knps`.
- **외부 공식 용어**: API 응답 필드, URL (`https://www.data.go.kr/...`), Pydantic, HTTPX.
- **벤더/제품명**: KNPS(국립공원공단), data.go.kr(공공데이터포털), GitHub, Ruff, Mypy.
- **표준 keyword**: ADR, CHANGELOG, ISO 8601 날짜, semver 라벨(`Added`/`Changed`/`Removed`/`Fixed`/`Security`).
- **shell 출력 / 로그 예시**: 그대로 캡처한 문자열은 보존.

설명 문장, 절제목, 표 column 헤더, ADR 본문, 빠른 시작 가이드, 일지 항목은 한글로 적는다. 새 문서를 만들 때 영문 초안을 두지 않는다 — 처음부터 한글로 쓴다.

## 식별자 (혼동 방지)

| 항목 | 값 |
|------|----|
| GitHub 저장소 이름 | `python-knps-api` |
| Python 패키지 이름 | `knps` |
| import 경로 | `import knps` 또는 `from knps import KnpsClient` |
| 주요 외부 의존성 | `httpx`, `pydantic`, `boto3`, `geo`(`pyproj`/`pyshp`, 선택 의존성) |
| 데이터 소스 | 국립공원공단, 공공데이터포털(data.go.kr) |
| RustFS endpoint URL env var (3단 폴백) | `KNPS_RUSTFS_ENDPOINT_URL` → `RUSTFS_ENDPOINT_URL` → `KRTOUR_MAP_OBJECT_STORE_ENDPOINT_URL` |
| RustFS bucket env var (3단 폴백) | `KNPS_RUSTFS_BUCKET` → `RUSTFS_BUCKET` → `KRTOUR_MAP_OBJECT_STORE_BUCKET`(기본값 `knps`) |
| RustFS access key env var (3단 폴백, 별칭 포함) | `KNPS_RUSTFS_ACCESS_KEY`/`KNPS_RUSTFS_ACCESS_KEY_ID` → `RUSTFS_ACCESS_KEY`/`RUSTFS_ACCESS_KEY_ID` → `KRTOUR_MAP_OBJECT_STORE_ACCESS_KEY_ID` |
| RustFS secret key env var (3단 폴백, 별칭 포함) | `KNPS_RUSTFS_SECRET_KEY`/`KNPS_RUSTFS_SECRET_ACCESS_KEY` → `RUSTFS_SECRET_KEY`/`RUSTFS_SECRET_ACCESS_KEY` → `KRTOUR_MAP_OBJECT_STORE_SECRET_ACCESS_KEY` |
| RustFS region env var (3단 폴백) | `KNPS_RUSTFS_REGION` → `RUSTFS_REGION` → `KRTOUR_MAP_OBJECT_STORE_REGION`(기본값 `us-east-1`) |

RustFS 관련 env var는 `KnpsConfig.from_env()`(ADR-004)가 읽으며, 세 접두어 중 먼저 값이 있는 것을 사용한다.

## 지시 우선순위

사용자 요청 > 이 `AGENTS.md` > `README.md`/기존 코드와 테스트.

## 절대 하지 말 것 (DO NOT)

1. **`main` 직접 푸시 금지** — 반드시 feature 브랜치 + PR/로컬 머지 후 푸시.
2. **타 provider와 exception/rate limit 계층 공유 금지** — KNPS 고유의 예외 및 속도 제한 로직은 `knps.*` 내부에만 둔다(ADR-001).
3. **`python-krtour-map` 안에 KNPS wrapper 추가 금지** — 소비자가 이 라이브러리의 public client/model/catalog를 직접 사용하게 한다(ADR-001).
4. **검증되지 않은 데이터셋의 무조건적인 다운로드 구현 금지** — 상세 ID나 URL이 검증되지 않은 경우 `needs_verification` 상태로 표시하고, 확정된 URL만 downloader에서 사용한다(ADR-002).
5. **Feature 변환 코드를 이 라이브러리에 내장 금지** — downstream ETL의 책임으로 두며, 라이브러리는 원본 바이트와 메타데이터만 제공한다(ADR-003).
6. **API 키/인증 정보 평문 커밋 금지** — 테스트 코드나 로컬 설정에 하드코딩하지 않고 환경 변수나 `.env`를 활용한다.

## 검증

```bash
# 의존성 설치 및 환경 진입
poetry install

# 품질 게이트
poetry run pytest
poetry run pytest -m live
poetry run ruff check src tests
poetry run mypy src
```

CI(`.github/workflows/ci.yml`)가 push/PR마다 동일한 lint/typecheck/test를 실행한다 — PR 머지 전 로컬에서도 먼저 통과시킨다.
