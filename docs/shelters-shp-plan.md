# 대피소 중첩 SHP 원천 지원

## 범위

python-knps-api#17과 Map T-KNPS-DATA-GAPS의 남은 대피소를 처리한다. 최신 Map#1452/#1453의 데이터셋별 schedule·보호지역 정책·위험지역/선형시설 미적재 결정은 보존한다. 원천 형식·정규화 record는 provider에서 수정하고, Map에는 병합된 provider 핀과 소비 회귀 검증만 반영한다.

## 절차와 검증

초안 PR을 먼저 만들고 중간 커밋을 원격에 저장한다. WSL에서 중첩 SHP의 Point 레이어와 polygon 부지를 섞은 최소 synthetic archive로 현행 실패를 재현한 뒤 공개 read_place_records가 Point만 typed record로 반환하도록 보완한다. 좌표계·한글 속성·출처 식별자·형식 오류와 CSV 기존 동작을 함께 검증한다. 실제 확인되지 않은 원천 의미나 좌표계를 추정하지 않는다.

수정 전 CodeGraph 영향도를 확인하고 전체 non-live 테스트·ruff·strict mypy·실제 적용 CI와 두 독립 전문 적대 리뷰를 마친 뒤 PR로 병합한다. 실제 운영 적재·DB/SSH·provider live 호출은 수행하지 않고, Claude Code가 재적재와 Pinvi 최종 UI를 확인할 수 있도록 절차와 미검증 항목을 기록한다.

## 2026-11-07 구현 체크포인트 (미커밋)

- 변경은 이 전용 ext4 작업트리의 src/tests/docs 및 CHANGELOG에 한정한다. 다른 Code의 정책·스케줄·작업트리를 수정하지 않는다.
- 기존 코드에서 합성 공개 client 회귀 6개 실패·5개 통과를 먼저 기록했다. 실패 원인은 중첩 다중 SHP·CPG·CRS 입력 경로의 부재이며, 실제 provider 실패를 재현했다고 주장하지 않는다.
- 구현 중 DBF 행 개수 불일치·삭제 행 좌표 밀림 2개와 geometry-only raw payload 불변 1개를 추가 실패로 확인한 뒤 수정했다.
- 대피소 경로만 중첩 ZIP의 모든 Point/PointZ/PointM XY를 읽는다. Polygon/MultiPoint/선형 레이어를 대피소 대표점으로 바꾸지 않는다. SHP가 있으나 유효 Point가 없으면 0건 성공 대신 KnpsParseError다.
- 기본 CSV와 다른 dataset의 첫 geometry/CSV 선택 계약은 유지한다. read_all_csv_rows는 SHP-only archive를 계속 거부한다.
- 카탈로그 기존 URL과 데이터셋 키는 보존하고 needs_verification을 명시한다. 탐색한 전용 캐시·기존 체크아웃에서 대피소 원본은 발견하지 못했다. 실제 DBF 필드, PRJ, CPG, 공식 다운로드 원본과의 동일성은 미확인이다.
- 독립 전문 리뷰 2건, 최종 exact SHA/CI, 소비 Map의 raw hash 회귀와 공식 원본 fixture 검증은 후속 단계다. 운영 적재·provider live 호출·완료 판정은 하지 않았다.

## 2026-11-07 전역 식별자 리뷰 보완

- 리뷰 P2 수용: 기존 normalizer의 전역 ID_CD/STN_ID까지 멤버 hash로 바뀌어 파일명 변경이 원천 identity를 바꾸던 문제를 수정했다.
- 수정 전 공개 client 회귀 7 failed / 43 deselected를 확인했다. 경로 변경 ID 유지, 동일/상이 좌표의 전역 ID 중복 거부, geometry-only raw 변경을 포함한다.
- 전역 ID는 원래 값을 유지하고, 로컬 OBJECTID/SEQNO/NO와 행 fallback만 멤버 경로로 scope한다. archive 전체 중복 전역 ID는 동일 내용이어도 fail-closed다.
- 부모의 immutable 88 Map 소비 negative 4건은 별도 실행 증거다. 이 작업자는 upstream 테스트만 실행하며 Map 통과를 대신 주장하지 않는다.


## 2026-11-07 SHP/DBF 물리 구조 보완

- 독립 리뷰 P1/P2 수용: 음수 SHP 길이와 0 DBF stride/high count는 Reader sentinel로 안전하게 실패 우선 검증했다. 실제 위험 반복자는 기존 코드에서 실행하지 않았다.
- 실제 parser로 오래된 SHX/DBF가 2개 SHP Point를 1개로 숨기는 문제도 확인했다. 수정 전 3 failed / 정상 no-SHX 1 passed다.
- Reader 전에 독립 물리 framing 검증과 누적 record 100,000 상한을 적용한다. SHX는 무시하고 SHP를 순차 읽는다. valid no-SHX와 stale-SHX/정상 DBF는 실제 2개 Point를 모두 반환한다.
- 최종 직접 검증: 관련 120 passed (0.82초), non-live 168 passed / 17 deselected / 14 subtests passed (3.30초), Ruff/strict mypy 15개 파일 통과. 전역 ID 보존과 기존 archive/raw hash 회귀도 포함한다.


## 2026-11-07 CSV source_crs 실제 guard 보완

- 4fb61a2의 문서상 설명과 달리 명시적 source_crs가 CSV 경로에서 무시되던 P2를 실제 코드로 수정했다.
- 대피소 plain CSV/CSV ZIP/다른 dataset CSV의 공개 호출 3건은 CSV reader sentinel로 수정 전 모두 실패했다. None 기본값 대조 3건은 통과했다.
- SHP 결과가 없으면 source_crs is not None일 때 CSV reader 전에 KnpsParseError다. asyncio.to_thread와 기본 CSV 의미는 변경하지 않았다.
- 직접 검증: 관련 126 passed (0.77초), 전체 non-live 174 passed / 17 deselected / 14 subtests passed (3.25초), Ruff 전체·strict mypy 15개 파일 통과. 소비 Map/UI 성공은 부모의 별도 증거다.


## 2026-11-07 삭제 DBF/NULL shape 보완

- 물리 framing preflight가 정상적인 삭제 DBF 행의 NULL shape까지 거부하던 P2를 수정했다. NULL은 정확히 type 4 bytes만 허용하며 양수 전진/실제 길이/record budget은 유지한다.
- 삭제 DBF+NULL 뒤 정상 Point 반환은 수정 전 1 failed였다. 활성 DBF+NULL 오류와 잘못된 NULL 20-byte body의 Reader 전 거부는 2 passed 대조였다.
- 기존 reader가 DBF 삭제 여부를 먼저 확인하므로 삭제 행만 skip하고 활성 NULL은 계속 KnpsParseError다. 다른 삭제 정책은 바꾸지 않았다.
- CSV source_crs guard를 포함한 직접 최종 결과: 관련 129 passed (0.78초), non-live 177 passed / 17 deselected / 14 subtests passed (3.31초), Ruff/strict mypy 15개 파일 통과.
