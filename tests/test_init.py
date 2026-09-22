"""Tests for setup, migration, statistics import, sensors and diagnostics."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

from homeassistant.components.recorder.statistics import statistics_during_period
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.components.recorder.common import (
    async_wait_recording_done,
)

from custom_components.ha_electric_usage_downloader.api import (
    ServiceLocation,
    SmartHubAuthError,
    SmartHubConnectionError,
    parse_usage,
)
from custom_components.ha_electric_usage_downloader.const import DOMAIN
from custom_components.ha_electric_usage_downloader.coordinator import statistic_id
from custom_components.ha_electric_usage_downloader.diagnostics import (
    async_get_config_entry_diagnostics,
)

CLIENT = "custom_components.ha_electric_usage_downloader.api.SmartHubClient"
DATA = {
    "host": "example.smarthub.coop",
    "username": "u",
    "password": "pw",
    "account": "1000001",
    "service_location": "900001",
}
LOC = ServiceLocation("1000001", "900001")


def _entry(hass, data=None, version=2):
    entry = MockConfigEntry(
        domain=DOMAIN, version=version, data=data or DATA, unique_id="x"
    )
    entry.add_to_hass(hass)
    return entry


async def test_setup_imports_statistics_and_sensors(hass: HomeAssistant, poll_complete):
    entry = _entry(hass)
    with patch(f"{CLIENT}.async_get_usage", return_value=parse_usage(poll_complete)):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    await async_wait_recording_done(hass)
    sid = statistic_id(LOC, "consumption")
    stats = await hass.async_add_executor_job(
        statistics_during_period,
        hass,
        datetime(2026, 9, 1, tzinfo=UTC),
        None,
        {sid},
        "hour",
        None,
        {"sum", "state"},
    )
    assert [round(r["sum"], 2) for r in stats[sid]] == [0.13, 1.63]

    states = {s.entity_id: s.state for s in hass.states.async_all("sensor")}
    assert "1.63" in states.values()
    assert "10.3" in states.values()

    diag = await async_get_config_entry_diagnostics(hass, entry)
    assert diag["entry"]["password"] == "**REDACTED**"
    assert diag["entry"]["account"] == "**REDACTED**"

    # A second refresh anchors on the existing sum instead of restarting at zero.
    with patch(f"{CLIENT}.async_get_usage", return_value=parse_usage(poll_complete)):
        await entry.runtime_data.async_refresh()
    await async_wait_recording_done(hass)
    stats = await hass.async_add_executor_job(
        statistics_during_period,
        hass,
        datetime(2026, 9, 1, tzinfo=UTC),
        None,
        {sid},
        "hour",
        None,
        {"sum"},
    )
    assert [round(r["sum"], 2) for r in stats[sid]] == [0.13, 1.63]

    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_auth_failure_starts_reauth(hass: HomeAssistant):
    entry = _entry(hass)
    with patch(f"{CLIENT}.async_get_usage", side_effect=SmartHubAuthError("x")):
        await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert any(
        f["context"]["source"] == "reauth"
        for f in hass.config_entries.flow.async_progress()
    )


async def test_connection_failure_retries(hass: HomeAssistant):
    entry = _entry(hass)
    with patch(f"{CLIENT}.async_get_usage", side_effect=SmartHubConnectionError("x")):
        await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_migrate_v1_single_location(hass: HomeAssistant, poll_complete):
    v1 = {
        "username": "u",
        "password": "pw",
        "login_url": "https://example.smarthub.coop/Login.html",
        "usage_url": "x",
    }
    entry = _entry(hass, v1, version=1)
    with (
        patch(f"{CLIENT}.async_get_service_locations", return_value=[LOC]),
        patch(f"{CLIENT}.async_get_usage", return_value=parse_usage(poll_complete)),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
    assert entry.version == 2
    assert entry.data["host"] == "example.smarthub.coop"
    assert entry.data["account"] == "1000001"
    assert "login_url" not in entry.data


async def test_migrate_v1_ambiguous_or_failing(hass: HomeAssistant):
    v1 = {
        "username": "u",
        "password": "pw",
        "login_url": "https://example.smarthub.coop/Login.html",
    }
    for effect, state in (
        (
            {"return_value": [LOC, ServiceLocation("1", "2")]},
            ConfigEntryState.SETUP_ERROR,
        ),
        ({"side_effect": SmartHubAuthError("x")}, ConfigEntryState.SETUP_ERROR),
        ({"side_effect": SmartHubConnectionError("x")}, ConfigEntryState.SETUP_RETRY),
    ):
        entry = _entry(hass, dict(v1), version=1)
        with patch(f"{CLIENT}.async_get_service_locations", **effect):
            await hass.config_entries.async_setup(entry.entry_id)
        assert entry.state is state
        await hass.config_entries.async_remove(entry.entry_id)
