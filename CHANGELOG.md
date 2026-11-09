# 변경 이력

이 문서는 [Keep a Changelog](https://keepachangelog.com/ko/1.1.0/) 형식을 따른다.

## [Unreleased]

### 대피소 SHP

- 대피소의 중첩 ZIP에서 실제 Point 레이어만 typed place record로 읽는다.
  PRJ/명시적 CRS, 엄격한 인코딩, archive 한계, 로컬 멤버별 ID와 geometry raw provenance를 적용한다.
  전역 ID_CD/STN_ID는 보존하고 archive 전체의 중복 전역 ID는 거부한다.
  외부 Reader 전에 SHP/DBF 물리 구조와 누적 record 수를 검증하고 SHX는 무시한다.
  SHP 이외 place 경로에서는 명시적 source_crs를 무시하지 않고 오류로 거부한다.
- 다른 dataset의 CSV/geometry 계약은 유지한다.
  상세 계약과 한계는 docs/knps-api.md의 대피소 절을 참고한다.
- 공식 원본 확인(#17): `knps_shelters` 카탈로그를 포털 현재 배포본
  `FILE_000000003681543`(_20230928, 평면 SHP 22 Point, UTF-8, EPSG:5186)으로 바꾸고
  `formats=("SHP",)`, `verified`로 올렸다. 이전 URL은 2013년 8건짜리 파일이었다.
- 현재 배포본의 DBF 필드명은 10 bytes에서 잘린 UTF-8 한글이다. 필드명 끝의 불완전 시퀀스만
  제거하고(값과 이름 중간 byte는 계속 strict), 대피소 전용 필드 `시설물명`·`위치.주소`·`순번`을
  name·jibun_address·로컬 ID로 매핑한다.
- archive의 모든 Point가 이름을 얻지 못하면 DBF 필드 목록과 함께 `KnpsParseError`를 낸다.


### TPS 제어 변경

- 공통 `AsyncTokenBucket`으로 FIFO·취소·유한한 수치 검증·1 TPS 미만 설정을 지원한다.
- 기존 고정 요청 간격 제한을 토큰 버킷으로 교체했다. 일반 응답과 스트리밍 모두 재시도마다 토큰을 소비한다.
- 사용법과 범위: `docs/async-tps.md`.

### 수정

- 2인 적대적 리뷰어 서브에이전트(동시성/자원관리 관점, 보안/데이터 무결성 관점)의 asyncio 전환
  재검증에서 발견·검증된 버그 2건 수정:
  - `download_artifact()`/`download_geometries()`/`read_place_records()`/`read_geo_records()`가
    CPU-bound CSV/ZIP 파싱과 Pydantic 정규화(`read_file_artifact()`/`extract_geometries()`와
    그 후처리)를 `asyncio.to_thread` 없이 코루틴 안에서 직접 실행해 이벤트 루프를 막던 문제.
    `knps_trails`(실측 910,110 vertex 행)처럼 큰 데이터셋에서는 초 단위로 이벤트 루프 전체가
    멈출 수 있었다. `download_to_rustfs()`의 `boto3.client()` 생성도 함께 스레드로 옮겼다
    (같은 함수의 `path.write_bytes`/`s3_client.put_object`는 이미 올바르게 스레드로 감싸져
    있었음).
  - `download_artifact()`/`download_geometries()`가 `max_bytes`로 다운로드를 잘라 놓고도
    결과 `FileArtifact`/`GeoFeatureCollection`에 아무 신호도 남기지 않아, 호출자가 완전한
    파일을 읽은 것처럼 착각할 수 있던 문제. 두 모델에 `truncated: bool` 필드를 추가하고
    실제 다운로드가 `max_bytes`에 도달했는지 감지해 채워 넣는다.
  - 두 리뷰어 모두 다른 관점에서는 실제 버그를 찾지 못함 — 레이트리미터(`AsyncRateLimiter`)는
    `await asyncio.sleep`을 포함해 critical section 전체를 lock으로 감싸 안전함을 확인, HTTP
    에러 매핑/재시도는 모든 경로에서 타입화된 예외로 귀결됨을 확인, 자격증명(RustFS
    access/secret key)은 `repr=False`로 보호되고 예외 메시지에도 노출되지 않음을 확인,
    다운로드 URL은 항상 고정 카탈로그로만 해석되어 조작 불가능함을 확인.

### 변경

- 14개 저장소 문서 컨벤션 통일 작업의 일환으로 `README.md`/`AGENTS.md`/`CLAUDE.md`/`docs/decisions.md` 구조를 정리하고, `LICENSE`(GPL-3.0-or-later)와 이 `CHANGELOG.md`를 추가했다.
