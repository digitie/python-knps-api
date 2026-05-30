# Journal

이 문서는 `python-knps-api` 프로젝트의 개발 기록과 주요 기술적 결정을 역시간순으로 관리한다.

## 2026-05-31
- **작업**: 워크트리 prefix 변경(python-knps-api-*) 및 에이전트별 worktree 생성과 codegraph init
- **내용**: 
  - 워크트리 prefix를 기존 `knps-*`에서 `python-knps-api-*`로 전면 변경하고 설정 파일(`.gemini/mcp.json`, `antigravity.json`, `claude.json`, `codex.json`, `AGENTS.md`, `CLAUDE.md`)을 업데이트 완료.
  - `git worktree add`를 사용하여 `python-knps-api-antigravity`, `python-knps-api-claude`, `python-knps-api-codex` 디렉토리를 로컬에 생성 완료.
  - 각 워크트리 디렉토리 내에서 `codegraph init -i`를 성공적으로 실행하여 인덱싱 구조를 활성화 및 연동함.
- **다음 작업**: (백로그) 공간데이터 파서 선택 의존성 도입 및 파싱 기능 구현.

- **작업**: maplibre-vworld-js 프로젝트 스타일 및 MCP 설정 이식
- **내용**: 
  - `maplibre-vworld-js`의 선진적인 AI 에이전트 협업 체계(에이전트별 고정 worktree 및 CodeGraph), 엄격한 한글 문서화 규칙, 로컬 품질 게이트 및 DO NOT 룰을 `python-knps-api` 프로젝트에 이식 완료.
  - `.gemini/mcp.json`, `antigravity.json`, `claude.json`, `codex.json` 추가.
  - `AGENTS.md` 개편 및 `CLAUDE.md` 신설.
  - `docs/tasks.md` 및 `docs/journal.md` 신설.
- **다음 작업**: 로컬 품질 게이트 확인 후 main 브랜치 머지 및 리모트 푸시.
