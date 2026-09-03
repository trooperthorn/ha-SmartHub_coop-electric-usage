"""Tests for the config flow."""
from homeassistant import config_entries
from homeassistant.core import HomeAssistant

from custom_components.ha_electric_usage_downloader.const import DOMAIN


async def test_user_form_shows_defaults(hass: HomeAssistant):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"


async def test_missing_credentials_shows_error(hass: HomeAssistant):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "username": "",
            "password": "",
            "login_url": "https://bluebonnet.smarthub.coop/Login.html",
            "usage_url": "https://bluebonnet.smarthub.coop/Usage/Usage.htm",
        },
    )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "missing_credentials"}


async def test_valid_input_creates_entry(hass: HomeAssistant):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "username": "someuser",
            "password": "secret",
            "login_url": "https://bluebonnet.smarthub.coop/Login.html",
            "usage_url": "https://bluebonnet.smarthub.coop/Usage/Usage.htm",
        },
    )

    assert result["type"] == "create_entry"
    assert result["title"] == "Electric Usage Downloader"
    assert result["data"]["username"] == "someuser"
