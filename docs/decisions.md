# Decisions

## ADR-001: KNPS는 별도 provider 라이브러리로 둔다

Status: accepted

`python-krforest-api`와 KNPS는 산/탐방 도메인이 겹치지만 기관이 다르다. 기존 관례는 1기관 1라이브러리이며, data.go.kr 활용신청, rate limit, 장애 양상, 파일데이터 catalog도 기관별로 다르게 움직인다.

결정:

- canonical provider name은 `python-knps-api`다.
- import module은 `knps`다.
- 인증, rate limit, exception은 `knps.*` 내부에 독립 구현한다.
- `python-krtour-map`은 KNPS wrapper를 만들지 않고 이 public client/model/catalog를 직접 사용한다.

## ADR-002: v1은 catalog-first로 간다

Status: accepted

KNPS는 OpenAPI보다 파일 기반 공간데이터 비중이 크고, data.go.kr 상세 페이지와 다운로드 URL은 운영 상태에 따라 변동된다. 따라서 v1은 모든 후보 dataset을 catalog에 올리되 검증 상태를 명시하고, 확정된 URL만 downloader에서 사용한다.

결정:

- `FileDataset.verification_status`를 둔다.
- 미검증 dataset의 `download_url`은 비워둔다.
- live test가 상세 ID와 직접 다운로드 URL을 검증하면 `verified`로 승격한다.

## ADR-003: feature 변환은 downstream ETL 책임으로 둔다

Status: accepted

provider 라이브러리는 원본 API/file dataset을 안정적으로 호출하고 record/model/catalog를 제공한다. TripMate 도메인 feature로 바꾸는 일은 `python-krtour-map` ETL 책임이다.

결정:

- 이 저장소는 `FeatureBundle`을 import하지 않는다.
- `docs/knps-feature-etl.md`에 변환 계약을 기록한다.
- downstream은 provider catalog key를 dataset_key로 사용한다.
