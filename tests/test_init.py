"""Tests for setup and unload of the config entry."""
from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntryState
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ha_electric_usage_downloader.const import DOMAIN

ENTRY_DATA = {
    "username": "someuser",
    "password": "secret",
    "login_url": "https://bluebonnet.smarthub.coop/Login.html",
    "usage_url": "https://bluebonnet.smarthub.coop/Usage/Usage.htm",
}


async def test_setup_and_unload_entry(hass: HomeAssistant):
    entry = MockConfigEntry(domain=DOMAIN, data=ENTRY_DATA)
    entry.add_to_hass(hass)

    with patch(
        "custom_components.ha_electric_usage_downloader.api.ElectricUsageAPI.login",
        AsyncMock(return_value=None),
    ), patch(
        "custom_components.ha_electric_usage_downloader.api.ElectricUsageAPI.get_usage_data",
        AsyncMock(return_value={"usage": 12.3}),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.data == {"usage": 12.3}

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_entry_not_ready_on_connection_error(hass: HomeAssistant):
    from custom_components.ha_electric_usage_downloader.api import ElectricUsageConnectionError

    entry = MockConfigEntry(domain=DOMAIN, data=ENTRY_DATA)
    entry.add_to_hass(hass)

    with patch(
        "custom_components.ha_electric_usage_downloader.api.ElectricUsageAPI.login",
        AsyncMock(side_effect=ElectricUsageConnectionError("unreachable")),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
