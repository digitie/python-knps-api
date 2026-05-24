from typing import Any

import pytest

from knps import KnpsClient
from knps._http import KnpsHttp


class FakeResponse:
    status_code = 200
    content = (
        b'{"response":{"body":{"items":{"item":[{"name":"A"}]},'
        b'"pageNo":1,"numOfRows":1,"totalCount":1},"header":{"resultCode":"00"}}}'
    )

    @property
    def text(self) -> str:
        return self.content.decode()

    def json(self) -> dict[str, Any]:
        return {
            "response": {
                "header": {"resultCode": "00"},
                "body": {
                    "items": {"item": [{"name": "A"}]},
                    "pageNo": 1,
                    "numOfRows": 1,
                    "totalCount": 1,
                },
            }
        }


class FakeSession:
    def __init__(self) -> None:
        self.params: dict[str, Any] | None = None
        self.closed = False

    async def get(self, url: str, **kwargs: Any) -> FakeResponse:
        self.params = kwargs["params"]
        return FakeResponse()

    async def aclose(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_raw_endpoint_requires_verified_catalog_key() -> None:
    session = FakeSession()
    client = KnpsClient(api_key="secret", session=session, max_rps=1000)
    with pytest.raises(KeyError):
        await client.raw_endpoint("knps_visitor_statistics", num_of_rows=1)
    await client.aclose()
    assert session.params is None


@pytest.mark.asyncio
async def test_http_redacts_context_key() -> None:
    session = FakeSession()
    http = KnpsHttp("secret", session=session, max_rps=1000)
    payload = await http.get(
        "https://example.test/knps",
        {"pageNo": 1, "numOfRows": 1},
        provider="data.go.kr",
        endpoint="verified_fixture",
        response_format="json",
    )
    await http.aclose()

    assert payload.items == [{"name": "A"}]
    assert payload.context.request_params["serviceKey"] == "***"
    assert session.params is not None
    assert session.params["serviceKey"] == "secret"
    assert session.closed is False
