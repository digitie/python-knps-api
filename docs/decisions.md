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

## D-005: 취소에 안전한 공통 토큰 버킷

- 상태: accepted
- 날짜: 2026-09-14
- 결정자: Codex

### 컨텍스트

자매 라이브러리의 TPS 의미가 다르고 소수 TPS·취소 경합에서 진행이 멈추는 문제가 있었다.
사용자는 async-only와 동일한 토큰 버킷을 요구했다.

### 결정

외부 런타임 의존성을 추가하지 않고 같은 `AsyncTokenBucket` 소스를 패키지 내부에 둔다.
`asyncio.Lock`을 충전 대기까지 보유하여 FIFO와 취소 처리를 맡기고 별도 timer 큐를 없앤다.
초당 충전량과 burst 용량을 구분하고 명시적으로 한 이벤트 루프에서만 사용한다.
기존 고정 요청 간격 제한을 토큰 버킷으로 교체했다. 일반 응답과 스트리밍 모두 재시도마다 토큰을 소비한다.

### 결과

세부 계약과 회귀 테스트는 `docs/async-tps.md`에 기록한다.
독립 리뷰 2건 및 live E2E 성공을 확인한 뒤 PR로 머지한다.

## D-006: 대피소 중첩 SHP는 Point 원천과 검증 가능한 CRS만 허용한다

- 상태: 제안 구현, 독립 리뷰 대기
- 날짜: 2026-11-07

대피소는 Point와 부지 Polygon이 다른 중첩 archive에 섞일 수 있다. 첫 SHP나
Polygon 중심점은 대피소 Point의 대체 근거가 되지 않는다. 따라서 대피소 전용 읽기에서만
중첩 Point 레이어를 모두 모으고, PRJ/명시적 CRS가 없는 좌표는 경위도로 제공하지 않는다.
공통 geometry 추출기의 첫 레이어 선택과 CSV normalizer 기본값은 유지한다.

파일 로컬 ID의 충돌을 피하기 위해 멤버 경로를 식별자에 포함한다. 실제 DBF 속성과
예약 geometry provenance를 raw에 함께 제공하여 downstream raw hash가 좌표 변경을 놓치지 않게 한다.
실제 원천 필드·CRS는 합성 테스트로 검증할 수 없으므로 카탈로그 검증 상태는 보류한다.
운영·적재 정책은 소비자와 운영 담당자의 책임이다.
