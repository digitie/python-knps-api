# Testing

## Local test

```bash
pytest
```

현재 기본 테스트는 network를 사용하지 않는다.

## Live test

```bash
pytest -m live
```

Live test는 다음을 검증한다.

- data.go.kr detail URL reachability
- 직접 다운로드 URL이 확인된 file dataset의 keyless bytes download
- 다운로드한 ZIP/CSV의 `FileArtifact` Pydantic DTO 변환
- 공간데이터 ZIP parser 도입 후 geometry type과 좌표계 변환

## Fixture 정책

- fixture에는 원본 전체 파일 대신 최소 샘플 또는 synthetic shapefile을 사용한다.
