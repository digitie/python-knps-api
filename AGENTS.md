# AGENTS.md

이 저장소는 `python-knps-api` 작업 진입점이다.

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

## 역할

이 저장소(GitHub 저장소 이름 `python-knps-api`, Python 패키지 이름 `knps`)는 국립공원공단(KNPS)의 오픈 API 및 파일 기반 공간데이터를 가져오기 위한 **독립적인 Python API Client 및 Catalog**다. 원본 바이트와 메타데이터를 안정적으로 제공하며, 도메인 특화 feature 변환은 downstream ETL(`python-krtour-map` 등)의 책임이다.

## 식별자 (혼동 방지)

| 항목 | 값 |
|------|----|
| GitHub 저장소 이름 | `python-knps-api` |
| Python 패키지 이름 | `knps` |
| import 경로 | `import knps` 또는 `from knps import KnpsClient` |
| 주요 외부 의존성 | `httpx`, `pydantic`, `geo` (선택 의존성) |
| 데이터 소스 | 국립공원공단, 공공데이터포털(data.go.kr) |

## 개발 환경 정책

PC 개발은 Windows 호스트에서 직접 진행한다.

- **로컬 품질 게이트 강제**: 이 저장소는 GitHub Actions/CI를 사용하지 않는다(ADR-10 정책 준용). 품질 게이트는 PR 머지 직전 작업자가 로컬에서 실행한다.
- **에이전트별 고정 worktree**: ChatGPT Codex는 `F:\dev\python-knps-api-codex`, Claude Code는 `F:\dev\python-knps-api-claude`, Google Antigravity 2.0은 `F:\dev\python-knps-api-antigravity`를 사용한다. 작업마다 브랜치만 새로 만들고, CodeGraph는 worktree마다 1회 `codegraph init -i` 후 `codegraph sync`로 유지한다.

작업 전에 반드시 다음을 읽는다:

1. `CLAUDE.md` — 현재 작업과 잔존 부채
2. `docs/decisions.md` — ADR-001 ~ ADR-003
3. `docs/knps-api.md`, `docs/knps-feature-etl.md`
4. `docs/tasks.md` — T-NNN 백로그
5. `docs/testing.md` — 로컬 및 Live 테스트 가이드

## 지시 우선순위

1. 사용자 요청
2. 이 `AGENTS.md`
3. `CLAUDE.md`
4. `docs/decisions.md`, `docs/testing.md`
5. `docs/tasks.md`, `docs/journal.md`, `README.md`
6. 기존 코드와 테스트
7. 최소한의, 되돌릴 수 있는 가정

## 절대 하지 말 것 (DO NOT)

1. **`main` 직접 푸시 금지** — 반드시 feature 브랜치 + PR/로컬 머지 후 푸시.
2. **타 provider와 exception/rate limit 계층 공유 금지** — KNPS 고유의 예외 및 속도 제한 로직은 `knps.*` 내부에만 둔다(ADR-001).
3. **`python-krtour-map` 안에 KNPS wrapper 추가 금지** — 소비자가 이 라이브러리의 public client/model/catalog를 직접 사용하게 한다(ADR-001).
4. **검증되지 않은 데이터셋의 무조건적인 다운로드 구현 금지** — 데이터셋의 상세 ID나 URL이 검증되지 않은 경우 반드시 `needs_verification` 상태로 표시하고, 확정된 URL만 downloader에서 사용한다(ADR-002).
5. **Feature 변환 코드를 이 라이브러리에 내장 금지** — downstream ETL의 책임으로 두며, 라이브러리는 원본 바이트와 메타데이터만 안정적으로 제공한다(ADR-003).
6. **API 키/인증 정보 평문 커밋 금지** — 테스트 코드나 로컬 설정에 하드코딩하지 않고 환경 변수나 `.env`를 활용한다.
7. **`.codegraph/` 커밋 금지** — CodeGraph 인덱스는 worktree 로컬 산출물이다.

## 작업 후 체크리스트

- [ ] 로컬 테스트 통과 (`pytest`)
- [ ] Live 테스트 통과 (`pytest -m live`)
- [ ] 린트 체크 통과 (`ruff check src tests`)
- [ ] 타입 체크 통과 (`mypy src`)
- [ ] `docs/journal.md`에 작업 항목 추가 (역시간순)
- [ ] `docs/tasks.md`의 T-NNN 상태 갱신
- [ ] 의사결정이 있었다면 `docs/decisions.md`에 ADR 추가
- [ ] 사용자 가시 변경이면 `CHANGELOG.md` 갱신

## 검증 명령

```bash
# 의존성 설치 및 환경 진입
poetry install

# 품질 게이트
poetry run pytest
poetry run pytest -m live
poetry run ruff check src tests
poetry run mypy src
```
