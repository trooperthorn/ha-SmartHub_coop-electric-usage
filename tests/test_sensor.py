"""Tests for the electric usage sensor entity."""
from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.const import UnitOfEnergy
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ha_electric_usage_downloader.const import DOMAIN

ENTRY_DATA = {
    "username": "someuser",
    "password": "secret",
    "login_url": "https://bluebonnet.smarthub.coop/Login.html",
    "usage_url": "https://bluebonnet.smarthub.coop/Usage/Usage.htm",
}


async def test_sensor_reports_usage(hass: HomeAssistant):
    entry = MockConfigEntry(domain=DOMAIN, data=ENTRY_DATA)
    entry.add_to_hass(hass)

    with patch(
        "custom_components.ha_electric_usage_downloader.api.ElectricUsageAPI.login",
        AsyncMock(return_value=None),
    ), patch(
        "custom_components.ha_electric_usage_downloader.api.ElectricUsageAPI.get_usage_data",
        AsyncMock(return_value={"usage": 7.5}),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.electric_usage")
    assert state is not None
    assert state.state == "7.5"
    assert state.attributes["unit_of_measurement"] == UnitOfEnergy.KILO_WATT_HOUR
    assert state.attributes["device_class"] == "energy"
