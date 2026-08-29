# decisions.md — 의사결정 기록

이 문서는 이 프로젝트의 구조적 결정을 결정 시점 순서로 누적한다.
결정이 뒤집힐 때는 새 항목을 추가하고, 옛 항목은 지우지 않은 채
(supersedes: 위 항목)으로 표시한다.

## D-001: KNPS는 별도 provider 라이브러리로 둔다

- 상태: accepted
- 날짜: 2026-05-25

### 컨텍스트

`python-krforest-api`와 KNPS는 산/탐방 도메인이 겹치지만 기관이 다르다. 기존 관례는 1기관 1라이브러리이며,
data.go.kr 활용신청, rate limit, 장애 양상, 파일데이터 catalog도 기관별로 다르게 움직인다.

### 결정

- canonical provider name은 `python-knps-api`다.
- import module은 `knps`다.
- 인증, rate limit, exception은 `knps.*` 내부에 독립 구현한다.
- `python-krtour-map`은 KNPS wrapper를 만들지 않고 이 public client/model/catalog를 직접 사용한다.

### 근거

기관별로 활용신청, rate limit, 장애 양상이 달라 공유 계층을 두면 한 기관의 변경이 다른 기관 코드에
영향을 준다. 1기관 1라이브러리 관례를 유지하면 경계가 명확하다.

### 결과

`src/knps/exceptions.py`, `src/knps/_ratelimit.py`가 KNPS 전용으로 독립됐고, `python-krtour-map`은
이 라이브러리의 public client를 직접 import한다.

## D-002: v1은 catalog-first로 간다

- 상태: accepted
- 날짜: 2026-05-25

### 컨텍스트

KNPS는 확인된 OpenAPI catalog가 없고 파일 기반 공간데이터 비중이 크다. data.go.kr 상세 페이지와
다운로드 URL은 운영 상태에 따라 변동된다.

### 결정

- `FileDataset.verification_status`를 둔다.
- 미검증 dataset의 `download_url`은 비워둔다.
- live test가 상세 ID와 직접 다운로드 URL을 검증하면 `verified`로 승격한다.

### 근거

확인되지 않은 URL을 그대로 노출하면 downstream이 조용히 깨진 링크를 소비하게 된다. 검증 상태를
명시적으로 표시하면 미확정 dataset과 확정 dataset을 구분해 사용할 수 있다.

### 결과

`docs/knps-api.md`의 File datasets 표가 검증 상태를 기록하고, `knps_basic_statistics`처럼 URL이
미확인인 dataset은 catalog에 있지만 downloader에서 사용되지 않는다.

## D-003: feature 변환은 downstream ETL 책임으로 둔다

- 상태: accepted
- 날짜: 2026-05-25

### 컨텍스트

provider 라이브러리는 원본 file dataset을 안정적으로 호출하고 record/model/catalog를 제공한다.
TripMate 도메인 feature로 바꾸는 일은 `python-krtour-map` ETL 책임이다.

### 결정

- 이 저장소는 `FeatureBundle`을 import하지 않는다.
- `docs/knps-feature-etl.md`에 변환 계약을 기록한다.
- downstream은 provider catalog key를 dataset_key로 사용한다.

### 근거

feature 변환 로직을 provider 라이브러리에 내장하면 도메인 스키마가 바뀔 때마다 provider를 함께
바꿔야 해서 결합도가 높아진다. 원본 데이터 제공과 도메인 변환을 분리하면 각자 독립적으로 진화할 수 있다.

### 결과

`src/knps/records.py`는 정규화된 raw record(`KnpsPlaceRecord`/`KnpsGeoRecord`)만 반환하고, feature
스키마 변환은 `python-krtour-map` 쪽 ETL 함수에서 수행한다.

## D-004: RustFS(S3 호환) 연동 및 로컬 이중 저장 지원

- 상태: accepted
- 날짜: 2026-06-07

### 컨텍스트

downstream인 `python-krtour-map`과의 결합 과정에서 파일 데이터를 로컬 저장함과 동시에 S3 호환
저장소(RustFS)에 함께 적재해야 하는 유스케이스가 식별되었다.

### 결정

- `KnpsConfig`에 S3 호환 스토리지 관련 자격증명 및 엔드포인트 설정을 추가한다.
- 기존의 API 형태는 그대로 보존하고, 이중 저장을 전용으로 처리하는 `download_to_rustfs` 메서드를
  `FileDataNamespace`에 추가한다.
- S3 SDK 호출 시에는 `boto3` 라이브러리를 사용하며, 이벤트 루프 차단을 방지하기 위해
  `asyncio.to_thread`를 사용하여 비동기적으로 처리한다.
- 자격증명/엔드포인트 env var는 `KNPS_RUSTFS_*` → `RUSTFS_*` → `KRTOUR_MAP_OBJECT_STORE_*` 순으로
  폴백한다(`AGENTS.md` 식별자 표 참고).

### 근거

기존 다운로드 API를 바꾸지 않고 opt-in 메서드로 추가하면 이중 저장이 필요 없는 기존 소비자에게
영향이 없다. env var 3단 폴백은 KNPS 전용 설정이 없어도 `python-krtour-map`이 이미 쓰는 공용
object store 설정을 그대로 재사용할 수 있게 한다.

### 결과

`tests/test_rustfs.py`가 로컬 파일 생성과 S3 API 호출 파라미터를 검증하고, `pyproject.toml`에
`boto3`/`types-boto3[s3]` 의존성이 추가됐다.
