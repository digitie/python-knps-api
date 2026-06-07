# Journal

이 문서는 `python-knps-api` 프로젝트의 개발 기록과 주요 기술적 결정을 역시간순으로 관리한다.

## 2026-06-07
- **작업**: 파일 dataset typed·정규화 record API 추가 (`feat/typed-file-records`)
- **내용**:
  - 모든 direct-download dataset을 실제로 내려받아 header schema를 검증하고(3종 변종: 표준 point 코드 임베디드, weather_stations 별도 코드, trails 순한글), 그 결과로 `knps.records` normalizer를 작성했다.
  - `KnpsPlaceRecord` / `KnpsGeoRecord` typed model을 `models.py`에 추가하고 `__init__` `__all__`에 export.
  - normalizer는 header의 `(영문코드)` 접미사를 우선 추출(대소문자 무시)하고, 코드가 없으면 순한글 header로 fallback한다. `(한글)`/`(영문)` 같은 순한글 괄호는 코드로 오인하지 않는다. source_id는 `ID_CD`(국립공원관리번호)를 최우선으로 하고, 없으면 행 해시(`row:...`)로 결정적 fallback.
  - `files.py`에 `read_place_records`(첫 CSV member 전체 행 정규화)와 `read_geo_records`(geometry→WKT + 속성 정규화 + 대표점) async 메서드 추가. `artifacts.read_all_csv_rows`로 preview cap 없는 전체 행 reader를 분리.
  - geometry.py의 WKT 컬럼 후보에 `gis위치` 추가(hazard_zones CSV의 POINT WKT 컬럼 감지).
  - 실제 header fixture 단위 테스트 + skip-by-default live 테스트 추가. ruff/mypy/pytest all green. live-verify로 visitor_centers/weather_stations/trails/hazard_zones/park_boundaries 정규화 결과 확인. version 0.1.0 → 0.2.0.
- **다음 작업**: downstream `python-krtour-map`이 `read_place_records`/`read_geo_records`를 소비하도록 ETL 연결(별도 작업).

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
