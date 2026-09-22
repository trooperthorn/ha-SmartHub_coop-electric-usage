"""Tests for the SmartHub config flow."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ha_electric_usage_downloader.api import (
    ServiceLocation,
    SmartHubAuthError,
    SmartHubConnectionError,
)
from custom_components.ha_electric_usage_downloader.const import DOMAIN

GET_LOCS = "custom_components.ha_electric_usage_downloader.config_flow.SmartHubClient.async_get_service_locations"
SETUP = "custom_components.ha_electric_usage_downloader.async_setup_entry"
USER = {
    "host": "https://Example.smarthub.coop/ui/",
    "username": "u@example.com",
    "password": "pw",
}
ONE = [ServiceLocation("1000001", "900001")]
TWO = ONE + [ServiceLocation("1000001", "900002")]


async def _start(hass):
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )


async def test_single_location_creates_entry(hass: HomeAssistant):
    result = await _start(hass)
    assert result["type"] is FlowResultType.FORM
    with patch(GET_LOCS, return_value=ONE), patch(SETUP, return_value=True):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], USER)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["host"] == "example.smarthub.coop"
    assert result["data"]["account"] == "1000001"
    assert result["result"].unique_id == "example.smarthub.coop_1000001_900001"


async def test_multiple_locations_asks(hass: HomeAssistant):
    result = await _start(hass)
    with patch(GET_LOCS, return_value=TWO):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], USER)
    assert result["step_id"] == "location"
    with patch(SETUP, return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"location": "1000001|900002"}
        )
    assert result["data"]["service_location"] == "900002"


@pytest.mark.parametrize(
    ("effect", "error"),
    [
        (SmartHubAuthError("x"), "invalid_auth"),
        (SmartHubConnectionError("x"), "cannot_connect"),
        (RuntimeError("x"), "unknown"),
        ([], "no_locations"),
    ],
)
async def test_errors(hass: HomeAssistant, effect, error):
    result = await _start(hass)
    kwargs = (
        {"return_value": effect}
        if isinstance(effect, list)
        else {"side_effect": effect}
    )
    with patch(GET_LOCS, **kwargs):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], USER)
    assert result["errors"] == {"base": error}


async def test_duplicate_aborts(hass: HomeAssistant):
    MockConfigEntry(
        domain=DOMAIN, unique_id="example.smarthub.coop_1000001_900001", version=2
    ).add_to_hass(hass)
    result = await _start(hass)
    with patch(GET_LOCS, return_value=ONE):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], USER)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth(hass: HomeAssistant):
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        unique_id="example.smarthub.coop_1000001_900001",
        data={
            "host": "example.smarthub.coop",
            "username": "u",
            "password": "old",
            "account": "1000001",
            "service_location": "900001",
        },
    )
    entry.add_to_hass(hass)
    result = await entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    with patch(GET_LOCS, side_effect=SmartHubAuthError("x")):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"password": "bad"}
        )
    assert result["errors"] == {"base": "invalid_auth"}
    with patch(GET_LOCS, return_value=ONE), patch(SETUP, return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"password": "new"}
        )
    assert result["reason"] == "reauth_successful"
    assert entry.data["password"] == "new"
