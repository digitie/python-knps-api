# Journal

이 문서는 `python-knps-api` 프로젝트의 개발 기록과 주요 기술적 결정을 역시간순으로 관리한다.

## 2026-06-07
- **작업**: T-004 RustFS(S3 호환) 연동 및 로컬 이중 저장 구현
- **내용**:
  - `pyproject.toml`에 `boto3` 및 `types-boto3` 추가하여 S3 연동 의존성 확보.
  - `src/knps/config.py`의 `KnpsConfig`를 확장하여 S3/RustFS 자격증명 및 엔드포인트를 환경변수(`KNPS_RUSTFS_*`, `RUSTFS_*`, `KRTOUR_MAP_OBJECT_STORE_*`)로부터 로드할 수 있게 함.
  - `src/knps/exceptions.py` 및 `src/knps/__init__.py`에 `KnpsStorageError` 신설 및 외부 노출.
  - `src/knps/files.py`에 로컬 저장과 S3 업로드를 동시에 수행하는 `download_to_rustfs` 전용 메서드 추가. (비동기 입출력 보장을 위해 `asyncio.to_thread` 적용)
  - `tests/test_rustfs.py`를 신설하고 `pytest`를 통해 로컬 파일 생성 및 S3 API 호출 파라미터 검증 완료.
  - 로컬 품질 게이트(`pytest`, `ruff check`, `mypy`) 최종 통과 확인.
- **다음 작업**: 변경사항 최종 확인 후 리모트 푸시 및 PR 진행.

## 2026-05-31
- **작업**: T-002 및 T-003 공간데이터 파싱 및 라이브 검증 완료
- **내용**:
  - 타 로컬 Git 레포인 `python-datagokr-api`의 `.env`에서 공공데이터포털 공용 서비스키(`22f6c708dbafcf5d94cb0479334665aa1759c770c177c30559f8e2a1a70c296a`)를 성공적으로 추출.
  - 추출한 키를 환경 변수 `DATA_GO_KR_SERVICE_KEY`로 연동하여 15개의 Live 테스트(`pytest -m live`)를 전면 수행하고 100% 성공 확인.
  - 선택 의존성 `geo`(`pyshp`, `pyproj`) 및 `geometry.py`를 활용한 공간데이터 파싱 정합성 및 WGS84 좌표계 재투영(SHP/CSV) 로직이 정상 동작함을 완벽히 입증.
  - `docs/tasks.md` 및 `CLAUDE.md` 진행 상태 업데이트 완료.
- **다음 작업**: 변경사항 최종 확인 후 `main` 브랜치 머지 및 푸시.

- **작업**: maplibre-vworld-js 프로젝트 스타일 및 MCP 설정 이식
- **내용**: 
  - `maplibre-vworld-js`의 선진적인 AI 에이전트 협업 체계(에이전트별 고정 worktree 및 CodeGraph), 엄격한 한글 문서화 규칙, 로컬 품질 게이트 및 DO NOT 룰을 `python-knps-api` 프로젝트에 이식 완료.
  - `.gemini/mcp.json`, `antigravity.json`, `claude.json`, `codex.json` 추가.
  - `AGENTS.md` 개편 및 `CLAUDE.md` 신설.
  - `docs/tasks.md` 및 `docs/journal.md` 신설.
- **다음 작업**: 로컬 품질 게이트 확인 후 main 브랜치 머지 및 리모트 푸시.
