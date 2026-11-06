# 대피소 중첩 SHP 원천 지원

## 범위

python-knps-api#17과 Map T-KNPS-DATA-GAPS의 남은 대피소를 처리한다. 최신 Map#1452/#1453의 데이터셋별 schedule·보호지역 정책·위험지역/선형시설 미적재 결정은 보존한다. 원천 형식·정규화 record는 provider에서 수정하고, Map에는 병합된 provider 핀과 소비 회귀 검증만 반영한다.

## 절차와 검증

초안 PR을 먼저 만들고 중간 커밋을 원격에 저장한다. WSL에서 중첩 SHP의 Point 레이어와 polygon 부지를 섞은 최소 synthetic archive로 현행 실패를 재현한 뒤 공개 read_place_records가 Point만 typed record로 반환하도록 보완한다. 좌표계·한글 속성·출처 식별자·형식 오류와 CSV 기존 동작을 함께 검증한다. 실제 확인되지 않은 원천 의미나 좌표계를 추정하지 않는다.

수정 전 CodeGraph 영향도를 확인하고 전체 non-live 테스트·ruff·strict mypy·실제 적용 CI와 두 독립 전문 적대 리뷰를 마친 뒤 PR로 병합한다. 실제 운영 적재·DB/SSH·provider live 호출은 수행하지 않고, Claude Code가 재적재와 Pinvi 최종 UI를 확인할 수 있도록 절차와 미검증 항목을 기록한다.
