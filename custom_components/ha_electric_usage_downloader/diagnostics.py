"""Diagnostics with credentials and account identifiers redacted."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import CONF_ACCOUNT, CONF_SERVICE_LOCATION
from .coordinator import SmartHubConfigEntry

TO_REDACT = {CONF_PASSWORD, CONF_USERNAME, CONF_ACCOUNT, CONF_SERVICE_LOCATION}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SmartHubConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "last_update_success": coordinator.last_update_success,
        "channels": {
            name: {
                "last_24h_kwh": item.last_24h_kwh,
                "last_reading": item.last_reading.isoformat(),
            }
            for name, item in (coordinator.data or {}).items()
        },
    }
