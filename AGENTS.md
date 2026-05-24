# AGENTS.md

이 저장소는 `python-knps-api` 작업 진입점이다.

## 절대 규칙

- Markdown/RST 문서는 한글로 작성한다.
- `python-mois-api`, `python-krheritage-api`, `python-khoa-api`, `python-krforest-api`의 구조와 방향성을 따른다.
- KNPS 인증, rate limit, exception 계층은 다른 provider와 공유하지 않는다.
- `python-krtour-map` 안에 KNPS wrapper를 만들지 않는다. 이 라이브러리의 public client/model/catalog를 직접 사용하게 한다.
- data.go.kr ID나 다운로드 URL이 검증되지 않은 경우 문서와 catalog에 `needs_verification`을 남긴다.

## 구현 원칙

- public client는 async/httpx 기반이다.
- catalog는 코드를 생성하기 쉬운 typed model로 유지한다.
- file dataset은 먼저 원본 bytes와 metadata를 안정적으로 제공하고, feature 변환은 downstream ETL에서 수행한다.
- 공간데이터 파서는 선택 의존성(`geo`)으로 둔다.

## 자주 보는 문서

- `README.md`
- `docs/knps-api.md`
- `docs/knps-feature-etl.md`
- `docs/decisions.md`
- `docs/testing.md`
