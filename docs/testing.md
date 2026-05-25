# Testing

## Local test

```bash
pytest
```

현재 기본 테스트는 network를 사용하지 않는다.

## Live test

```powershell
$env:DATA_GO_KR_SERVICE_KEY = "..."
pytest -m live
```

Live test는 다음을 검증한다.

- data.go.kr detail URL reachability
- 직접 다운로드 URL이 확인된 file dataset의 bytes download
- 공간데이터 ZIP parser 도입 후 geometry type과 좌표계 변환

## Fixture 정책

- fixture에는 service key를 저장하지 않는다.
- request context는 `serviceKey="***"`로 보존한다.
- 공간데이터 fixture는 원본 전체 ZIP 대신 최소 샘플 또는 synthetic shapefile을 사용한다.
