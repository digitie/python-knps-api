# 비동기 TPS 제어

`src/knps/_ratelimit.py`의 `AsyncTokenBucket`은 자매 라이브러리에 동일한 소스로
복제하는 구현이다. 공급자 사이의 런타임 의존성이나 전역 버킷은 만들지 않는다.
기존 GPL-3.0-or-later 자매 저장소의 토큰 충전 규칙을 유지하고 취소 처리와
fractional TPS를 보완했다.

## 설정과 요청 예산

- `max_rps`: 유한한 양수. 기본 5 TPS이며 0.5 TPS는 평균 2초에 한 번 충전한다.
- 초기·최대 토큰 용량: 기본 `max(1, max_rps)`. 최초 burst 이후에는 충전량으로 제한한다.
- `AsyncTokenBucket(..., capacity=1)`: burst를 한 번으로 줄인다. 명시 용량은 유한한 1 이상이어야 한다.
- 라이브러리가 제어하는 요청마다 토큰 1개를 소비한다. 실패한 송신, 재시도와 HTTPX redirect 후속 송신도 각각 센다.
- 공급자 기본 API 키 인증이 기준이다. 사용자 세션의 DigestAuth challenge 등 인증·전송 객체 내부의 추가 송신은 제어 범위 밖이다.
- 토큰을 기다리는 중 취소된 요청은 토큰을 소비하지 않는다.
- 같은 클라이언트를 재사용해야 API 호출·파일 처리에 같은 예산이 적용된다.
- 프로세스나 공급자별 별도 클라이언트 인스턴스 사이에는 예산이 자동 공유되지 않는다.
- 한 버킷은 하나의 이벤트 루프에서 사용한다. 여러 `asyncio.run()`에서 재사용하면 `RuntimeError`다.
- 이 제한은 고정된 매초 구간의 최대 건수가 아니라 burst 용량을 포함한 토큰 버킷이다.

```python
import asyncio
from knps import KnpsClient

async def main():
    async with KnpsClient(max_rps=0.5) as client:
        # 이 범위에서 client의 비동기 조회 메서드를 await한다.
        pass

asyncio.run(main())
```

기존 고정 요청 간격 제한을 토큰 버킷으로 교체했다. 일반 응답과 스트리밍 모두 재시도마다 토큰을 소비한다.

## 검증

`tests/test_ratelimit.py`는 수치 검증, 소수 TPS, FIFO, 누적 예산, 취소와 단일 루프
계약을 검사한다. `tests/test_tps_requests.py`는 실제 클라이언트 호출 경로와 재시도별
과금을 오프라인으로 검증한다. live E2E 성공과 독립 리뷰 2건은 별도 머지 조건이다.
현재 변경은 독립 코드 리뷰 2건을 통과했다. 실제 서비스 live E2E와 머지는 완료되지 않았다.

## 디버그 실행

공개 `run_dataset_operation()`도 `async def`이며 `await`해야 한다. 전달받은 client를
실행 후 같은 루프에서 닫는다. client 소유권을 유지하려면 `arun_dataset_operation()`을
사용한다. Streamlit 예제의 동기 진입점에서만 `asyncio.run()`을 실행한다.
