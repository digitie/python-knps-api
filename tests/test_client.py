from typing import Any

import pytest

from knps import KnpsClient


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
async def test_raw_endpoint_redacts_context_key() -> None:
    session = FakeSession()
    client = KnpsClient(api_key="secret", session=session, max_rps=1000)
    page = await client.raw_endpoint("knps_visitor_statistics", num_of_rows=1)
    await client.aclose()

    assert page.items == ({"name": "A"},)
    assert page.context.request_params["serviceKey"] == "***"
    assert session.params is not None
    assert session.params["serviceKey"] == "secret"
    assert session.closed is False
