"""SmartHub co-op electric usage integration."""

from __future__ import annotations

import logging
from urllib.parse import urlparse

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .api import ServiceLocation, SmartHubAuthError, SmartHubClient, SmartHubError
from .const import (
    CONF_ACCOUNT,
    CONF_HOST,
    CONF_SERVICE_LOCATION,
    DEFAULT_PROVIDER,
    PLATFORMS,
    SMARTHUB_DOMAIN,
)
from .coordinator import SmartHubConfigEntry, SmartHubCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: SmartHubConfigEntry) -> bool:
    """Set up SmartHub from a config entry."""
    # A dedicated session gives this entry its own cookie jar, which the
    # portal's XSRF check needs and which must not leak into other integrations.
    session = async_create_clientsession(hass)
    client = SmartHubClient(
        session,
        entry.data[CONF_HOST],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
    )

    if CONF_ACCOUNT not in entry.data:
        await _async_resolve_location(hass, entry, client)

    location = ServiceLocation(
        entry.data[CONF_ACCOUNT], entry.data[CONF_SERVICE_LOCATION]
    )
    coordinator = SmartHubCoordinator(hass, entry, client, location)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_resolve_location(
    hass: HomeAssistant, entry: SmartHubConfigEntry, client: SmartHubClient
) -> None:
    """Fill in the account for entries migrated from version 1.

    Version 1 never stored an account. If the login has exactly one service
    location it is adopted; otherwise the user must re-add the integration
    and choose one, because guessing would import the wrong meter.
    """
    try:
        locations = await client.async_get_service_locations()
    except SmartHubAuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except SmartHubError as err:
        raise ConfigEntryNotReady(str(err)) from err
    if len(locations) != 1:
        raise ConfigEntryAuthFailed(
            "This login has several service locations; remove and re-add the "
            "integration to choose one"
        )
    loc = locations[0]
    hass.config_entries.async_update_entry(
        entry,
        data={
            **entry.data,
            CONF_ACCOUNT: loc.account,
            CONF_SERVICE_LOCATION: loc.service_location,
        },
        unique_id=f"{entry.data[CONF_HOST]}_{loc.account}_{loc.service_location}",
    )


async def async_unload_entry(hass: HomeAssistant, entry: SmartHubConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: SmartHubConfigEntry) -> bool:
    """Migrate version 1 entries (page URLs) to version 2 (portal host)."""
    if entry.version == 1:
        host = (
            urlparse(entry.data.get("login_url", "")).hostname
            or f"{DEFAULT_PROVIDER}.{SMARTHUB_DOMAIN}"
        )
        data = {
            CONF_HOST: host,
            CONF_USERNAME: entry.data[CONF_USERNAME],
            CONF_PASSWORD: entry.data[CONF_PASSWORD],
        }
        hass.config_entries.async_update_entry(entry, data=data, version=2)
        _LOGGER.info("Migrated SmartHub entry to version 2 (host %s)", host)
    return True
