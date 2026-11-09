from __future__ import annotations

from unittest.mock import MagicMock

import httpx

from ssj.model_ping import ping_error_from_http_status


def test_geo_403_adds_hint() -> None:
    response = MagicMock(spec=httpx.Response)
    response.status_code = 403
    response.text = (
        '{"error":{"message":"This model is not available in your region.",'
        '"code":403,"metadata":{"failed_routing_step":"Gate Endpoints with Geo Restrictions"}}}'
    )
    exc = httpx.HTTPStatusError('403', request=MagicMock(), response=response)
    msg = str(ping_error_from_http_status(exc))
    assert 'HTTP 403' in msg
    assert '地区限制' in msg
