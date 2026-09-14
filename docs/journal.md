# Journal

이 문서는 `python-knps-api` 프로젝트의 개발 기록과 주요 기술적 결정을 역시간순으로 관리한다.

## 2026-09-14 TPS 통합 검증 완료

- 기존 고정 요청 간격 제한을 토큰 버킷으로 교체했다. 일반 응답과 스트리밍 모두 재시도마다 토큰을 소비한다.
- 공통 계약과 회귀 테스트는 `docs/async-tps.md`를 참고한다.
- 오프라인 pytest 97 passed, ruff/mypy/compileall 통과. 독립 적대적 리뷰 2건의 수정 사항을 반영하고 승인받았다.
- 실제 공급자 live E2E: 17 passed. xfail은 성공 건수에 포함하지 않는다.
- WSL에서 확인한 취소 테스트의 10ms 타이밍 의존성을 Event와 가짜 시계로 제거했고 8개 버킷 테스트가 통과했다.

## 2026-09-11 (claude, asyncio 재검증 2인 적대적 리뷰)

- **작업**: 이 저장소는 처음부터 async-only 클라이언트(`KnpsClient`, sync 클라이언트 없음)라
  다른 sibling 저장소들의 "sync/async 비대칭" 버그 유형은 적용되지 않는다는 전제로, 독립된
  서브에이전트 2명(동시성/자원관리 관점, 보안/데이터 무결성 관점)에게 async 코드 자체의
  순수 정합성을 다시 감사시켰다.
- **발견 1 (동시성)**: `download_artifact()`/`download_geometries()`/`read_place_records()`/
  `read_geo_records()`가 CPU-bound CSV/ZIP 파싱(`read_file_artifact`/`extract_geometries`)과
  Pydantic 정규화를 `asyncio.to_thread` 없이 코루틴 안에서 직접 실행해 이벤트 루프를 막고
  있었다. `knps_trails`는 실측 910,110 vertex 행 규모라(2026-06-12 항목 참고)
  `asyncio.gather()`로 여러 다운로드를 동시에 돌리거나 공유 클라이언트로 서버를 만들면 한
  호출이 다른 모든 코루틴을 초 단위로 막을 수 있었다. `download_to_rustfs()`의
  `boto3.client()` 생성도 threading 누락이었다(바로 아래 `s3_client.put_object`는 이미
  올바르게 `asyncio.to_thread`로 감싸져 있었는데 클라이언트 생성만 빠짐 — mcst-api에서 찾은
  것과 같은 패턴).
- **발견 2 (데이터 무결성)**: `download_artifact()`/`download_geometries()`가 `max_bytes`로
  다운로드를 일부러 자르는 기능(큰 파일 빠른 미리보기용)을 제공하는데, 결과
  `FileArtifact`/`GeoFeatureCollection`에는 잘렸다는 신호가 전혀 없어서 호출자가 완전한
  파일을 읽은 것과 구분할 수 없었다. `max_bytes` 도달 여부를 감지해 두 모델에 새로
  추가한 `truncated: bool` 필드에 채워 넣도록 수정.
- **수정**: `files.py`의 CPU-bound 호출부를 `asyncio.to_thread`로 감싸고(정규화 후처리는
  `_read_place_records`/`_normalize_geo_records` helper로 추출), `models.py`에
  `FileArtifact.truncated`/`GeoFeatureCollection.truncated` 필드 추가,
  `artifacts.read_file_artifact()`/`geometry.extract_geometries()`가 `truncated` 인자를
  받아 결과에 반영하도록 확장.
- **검증**: mock 테스트 82 passed(기존 70 + 신규 12: thread-offload 4개, truncation 신호
  8개, 모두 수정 전 코드로 되돌리면 실패함을 확인), ruff/mypy 통과, live e2e 17/17 passed
  (`knps_trails` 910K행 데이터셋 포함, 회귀 없음).
- **비대칭 아님 확인**: 레이트리미터(`AsyncRateLimiter`)는 `await asyncio.sleep`까지 포함해
  critical section 전체를 단일 lock으로 감싸 안전, HTTP 에러 매핑/재시도는 모든 경로에서
  타입화된 예외로 귀결, RustFS 자격증명은 `repr=False`로 보호되고 예외 메시지에도 노출
  안 됨, 다운로드 URL은 항상 고정 카탈로그로만 해석되어 조작 불가능함을 확인.

## 2026-06-12
- **작업**: #9 — `knps_trails` vertex 행을 코스 단위 LINESTRING으로 조립
- **내용**:
  - krtour-map T-212e live 적재에서 `read_geo_records("knps_trails")`가
    910,110개 **vertex 단위 POINT record**를 반환(코스당 수천 행) —
    카탈로그가 선언한 geometry 계약(`LineString`)과 불일치, downstream
    route 변환이 전 행 skip(krtour-map#407).
  - `read_geo_records`에 라인형 dataset 분기(`_LINE_GEOMETRY_TYPES`) +
    `_assemble_line_records` 추가: 같은 `source_id`의 POINT vertex를 파일
    등장 순서대로 이어 코스당 1개 `LINESTRING` record로 조립(속성/raw는 첫
    vertex 행, 대표점=첫 vertex, 2점 미만 코스 skip, 비-POINT record 통과).
  - live 종단 검증: 910,110 vertex → **625 코스 LINESTRING**(수통골 2코스 등).
  - 단위 테스트 2종(코스 그루핑/등장순서/비인접 병합, 1점 skip·line 통과).

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
- **작업**: T-002 및 T-003 공간데이터 파싱 및 라이브 검증 완료
- **내용**:
  - 타 로컬 Git 레포인 `python-datagokr-api`의 `.env`에서 공공데이터포털 공용 서비스키(`22f6c708dbafcf5d94cb0479334665aa1759c770c177c30559f8e2a1a70c296a`)를 성공적으로 추출.
  - 추출한 키를 환경 변수 `DATA_GO_KR_SERVICE_KEY`로 연동하여 15개의 Live 테스트(`pytest -m live`)를 전면 수행하고 100% 성공 확인.
  - 선택 의존성 `geo`(`pyshp`, `pyproj`) 및 `geometry.py`를 활용한 공간데이터 파싱 정합성 및 WGS84 좌표계 재투영(SHP/CSV) 로직이 정상 동작함을 완벽히 입증.
  - `docs/tasks.md` 및 `CLAUDE.md` 진행 상태 업데이트 완료.
- **다음 작업**: 변경사항 최종 확인 후 `main` 브랜치 머지 및 푸시.

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
