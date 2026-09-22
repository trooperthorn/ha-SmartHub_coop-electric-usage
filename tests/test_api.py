"""Tests for the SmartHub JSON client."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

import aiohttp
import pytest

from custom_components.ha_electric_usage_downloader.api import (
    ServiceLocation,
    SmartHubAuthError,
    SmartHubClient,
    SmartHubConnectionError,
    _parse_expiry,
    parse_usage,
)

from .conftest import LOGIN_OK, FakeResponse, FakeSession

HOST = "example.smarthub.coop"
LOC = ServiceLocation("1000001", "900001")
T0 = datetime(2026, 9, 20, tzinfo=UTC)
T1 = datetime(2026, 9, 21, tzinfo=UTC)


def _client(routes):
    session = FakeSession(routes)
    return SmartHubClient(session, HOST, "user@example.com", "secret"), session


def _login_routes():
    return {
        "/ui/": [FakeResponse()],
        "/services/oauth/auth/v2": [FakeResponse(200, LOGIN_OK)],
    }


async def test_login_sends_xsrf_and_form_fields():
    client, session = _client(_login_routes())
    await client.async_login()
    _method, path, kwargs = session.calls[1]
    assert path == "/services/oauth/auth/v2"
    assert kwargs["data"] == {"userId": "user@example.com", "password": "secret"}
    assert kwargs["headers"]["X-XSRF-TOKEN"] == "xsrf-value"


@pytest.mark.parametrize("status", [400, 401, 403])
async def test_login_rejected_status(status):
    client, _ = _client(
        {
            "/ui/": [FakeResponse()],
            "/services/oauth/auth/v2": [FakeResponse(status, {})],
        }
    )
    with pytest.raises(SmartHubAuthError):
        await client.async_login()


async def test_login_200_without_token_is_auth_error():
    """A 200 with no token must not be mistaken for success (the v1 bug)."""
    client, _ = _client(
        {
            "/ui/": [FakeResponse()],
            "/services/oauth/auth/v2": [FakeResponse(200, {"status": "FAILED"})],
        }
    )
    with pytest.raises(SmartHubAuthError):
        await client.async_login()


async def test_login_server_error_and_bad_json_and_network():
    client, _ = _client(
        {"/ui/": [FakeResponse()], "/services/oauth/auth/v2": [FakeResponse(500, {})]}
    )
    with pytest.raises(SmartHubConnectionError):
        await client.async_login()
    client, _ = _client(
        {
            "/ui/": [FakeResponse()],
            "/services/oauth/auth/v2": [FakeResponse(200, ValueError())],
        }
    )
    with pytest.raises(SmartHubConnectionError):
        await client.async_login()
    client, _ = _client({"/ui/": [aiohttp.ClientError("boom")]})
    with pytest.raises(SmartHubConnectionError):
        await client.async_login()


async def test_service_locations_and_auth_headers():
    routes = _login_routes()
    routes["/services/secured/accounts"] = [
        FakeResponse(
            200, [{"account": 1000001, "serviceLocations": ["900001", "900002"]}]
        )
    ]
    client, session = _client(routes)
    locs = await client.async_get_service_locations()
    assert locs == [
        ServiceLocation("1000001", "900001"),
        ServiceLocation("1000001", "900002"),
    ]
    headers = session.calls[-1][2]["headers"]
    assert headers["Authorization"] == "Bearer tok"
    assert headers["X-NISC-SMARTHUB-USERNAME"] == "user@example.com"


async def test_service_locations_unexpected_shape():
    routes = _login_routes()
    routes["/services/secured/accounts"] = [FakeResponse(200, {"oops": True})]
    client, _ = _client(routes)
    with pytest.raises(SmartHubConnectionError):
        await client.async_get_service_locations()


async def test_401_triggers_single_relogin():
    routes = {
        "/ui/": [FakeResponse(), FakeResponse()],
        "/services/oauth/auth/v2": [
            FakeResponse(200, LOGIN_OK),
            FakeResponse(200, LOGIN_OK),
        ],
        "/services/secured/accounts": [FakeResponse(401), FakeResponse(200, [])],
    }
    client, _ = _client(routes)
    assert await client.async_get_service_locations() == []


async def test_repeated_401_is_auth_error():
    routes = {
        "/ui/": [FakeResponse(), FakeResponse()],
        "/services/oauth/auth/v2": [
            FakeResponse(200, LOGIN_OK),
            FakeResponse(200, LOGIN_OK),
        ],
        "/services/secured/accounts": [FakeResponse(401), FakeResponse(401)],
    }
    client, _ = _client(routes)
    with pytest.raises(SmartHubAuthError):
        await client.async_get_service_locations()


async def test_request_errors():
    for resp in (
        FakeResponse(500),
        FakeResponse(200, ValueError()),
        aiohttp.ClientError("x"),
    ):
        routes = _login_routes()
        routes["/services/secured/accounts"] = [resp]
        client, _ = _client(routes)
        with pytest.raises(SmartHubConnectionError):
            await client.async_get_service_locations()


async def test_usage_polls_until_complete(poll_complete):
    routes = _login_routes()
    routes["/services/secured/utility-usage/poll"] = [
        FakeResponse(200, {"status": "PENDING"}),
        FakeResponse(200, poll_complete),
    ]
    client, session = _client(routes)
    with patch(
        "custom_components.ha_electric_usage_downloader.api.asyncio.sleep"
    ) as sleep:
        result = await client.async_get_usage(LOC, T0, T1)
    assert sleep.await_count == 1
    body = session.calls[-1][2]["json"]
    assert body["timeFrame"] == "HOURLY"
    assert body["accountNumber"] == "1000001"
    assert body["startDateTime"] == int(T0.timestamp() * 1000)
    assert result.readings["generation"][0][1] == 10.3


async def test_usage_unexpected_status_and_timeout():
    routes = _login_routes()
    routes["/services/secured/utility-usage/poll"] = [
        FakeResponse(200, {"status": "ERROR"})
    ]
    client, _ = _client(routes)
    with pytest.raises(SmartHubConnectionError):
        await client.async_get_usage(LOC, T0, T1)

    routes = _login_routes()
    routes["/services/secured/utility-usage/poll"] = [
        FakeResponse(200, {"status": "PENDING"})
    ] * 20
    client, _ = _client(routes)
    with (
        patch("custom_components.ha_electric_usage_downloader.api.asyncio.sleep"),
        pytest.raises(SmartHubConnectionError),
    ):
        await client.async_get_usage(LOC, T0, T1)


def test_parse_usage_maps_channels_by_flow_direction(poll_complete):
    result = parse_usage(poll_complete)
    assert set(result.readings) == {"consumption", "generation", "net"}
    assert result.readings["consumption"][1] == (
        datetime(2026, 9, 19, 14, tzinfo=UTC),
        1.5,
    )
    assert all(v >= 0 for _, v in result.readings["generation"])
    assert result.readings["net"][0][1] == -10.17


def test_parse_usage_single_channel_meter_and_gaps():
    data = {
        "data": {
            "ELECTRIC": [
                {
                    "series": [
                        {
                            "channel": 1,
                            "isNet": False,
                            "data": [
                                {"x": 1789822800000, "y": None},
                                {"x": 1789822800000, "y": 2},
                            ],
                        }
                    ]
                }
            ]
        }
    }
    result = parse_usage(data)
    assert list(result.readings) == ["consumption"]
    assert len(result.readings["consumption"]) == 1


def test_parse_usage_empty_and_malformed():
    assert parse_usage({"data": {"ELECTRIC": []}}).readings == {}
    with pytest.raises(SmartHubConnectionError):
        parse_usage({"data": {}})


def test_parse_expiry_variants():
    assert _parse_expiry({"expiration": 4102444800000}).year == 2100
    assert _parse_expiry({"expiresIn": 60}) > datetime.now(UTC)
    assert _parse_expiry({}) > datetime.now(UTC)
