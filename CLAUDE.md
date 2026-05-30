# CLAUDE.md — 프로젝트 컨텍스트

이 파일은 AI 에이전트가 매 세션 시작 시 자동으로 읽어 프로젝트 상태를 파악하는 문서다.
프로젝트 규칙은 `AGENTS.md`에, 아키텍처 의사결정은 `docs/decisions.md`에 있다.
이 파일은 **현재 상태**와 **세션 간 연속성**에 집중한다.

## 프로젝트 현황 (2026-05-31)

국립공원공단(KNPS) 오픈 API 및 파일 기반 공간데이터를 제공하는 Python Client 및 Catalog 라이브러리.
현재 `feat/style-and-mcp-settings` 작업을 통해 `maplibre-vworld-js` 프로젝트의 스타일 가이드와 AI 에이전트 협업 환경(MCP 및 에이전트별 고정 worktree)을 이식하고 적용했다.

### 현재 작업

- `feat/style-and-mcp-settings`: `maplibre-vworld-js` 프로젝트 스타일 및 MCP 설정을 가져와서 적용 및 리모트 푸시 완료 중.

### 잔존 기술 부채

- (없음 — 발견 시 `docs/tasks.md`에 T-NNN으로 등록)

### 브랜치 정리

- `feat/style-and-mcp-settings` — 현재 작업 중인 브랜치. 스타일 및 MCP 설정 적용 후 main에 머지 예정.

## 에이전트 worktree + CodeGraph

ChatGPT Codex는 `F:\dev\knps-codex`, Claude Code는 `F:\dev\knps-claude`, Google Antigravity 2.0은 `F:\dev\knps-antigravity`를 고정 worktree로 사용한다. 새 작업은 해당 worktree에서 `git fetch` 후 `git switch -c agent/<topic> main`으로 브랜치를 딴다.
CodeGraph는 worktree마다 1회 `codegraph init -i`로 초기화하고 이후에는 `codegraph sync`를 실행한다. `.codegraph/`는 gitignore 대상이다.

## 로컬 개발 환경

```
f:\dev\python-knps-api\
├── src/              # Python 소스 코드
│   └── knps/         # knps 패키지 디렉토리
├── tests/            # pytest 기반 테스트 코드
├── docs/             # 설계 문서, ADR, 태스크 및 일지
└── pyproject.toml    # Poetry 패키지 설정 및 의존성
```

Python 3.10+ 및 Poetry 환경.
`poetry install`을 통해 의존성을 설치하고 로컬 환경을 구성한다.

## 빠른 검증 명령

```bash
# 의존성 설치
poetry install

# 품질 게이트 (PR 전 로컬에서 직접 돌린다 — GitHub Actions는 사용하지 않는다)
poetry run pytest                  # 로컬 유닛 테스트
poetry run pytest -m live          # Live API 테스트
poetry run ruff check src tests    # 린터 및 스타일 체크
poetry run mypy src                # 정적 타입 체크
```

## 작업 후 의무사항

1. `docs/journal.md`에 항목 추가 (날짜·요약·결정·다음 작업, 역시간순)
2. `docs/tasks.md`의 현재 작업 상태 업데이트
3. 아키텍처 결정이 있었다면 `docs/decisions.md`에 ADR 추가
4. 사용자 가시 변경이면 `CHANGELOG.md` 갱신
5. 로컬 품질 게이트 통과 확인 후 커밋 및 머지
