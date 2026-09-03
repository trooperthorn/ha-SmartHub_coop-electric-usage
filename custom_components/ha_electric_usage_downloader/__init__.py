import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .const import PLATFORMS, SCAN_INTERVAL
from .api import ElectricUsageAPI, ElectricUsageAuthError, ElectricUsageConnectionError

_LOGGER = logging.getLogger(__name__)

type ElectricUsageConfigEntry = ConfigEntry["ElectricUsageCoordinator"]


async def async_setup_entry(hass: HomeAssistant, entry: ElectricUsageConfigEntry) -> bool:
    """Set up the Electric Usage Downloader from a config entry."""
    username = entry.data["username"]
    password = entry.data["password"]
    login_url = entry.data["login_url"]
    usage_url = entry.data["usage_url"]

    session = async_get_clientsession(hass)
    api = ElectricUsageAPI(session, username, password, login_url, usage_url)

    coordinator = ElectricUsageCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ElectricUsageConfigEntry) -> bool:
    """Unload the Electric Usage Downloader."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


class ElectricUsageCoordinator(DataUpdateCoordinator):
    """Coordinator to manage fetching electric usage data."""

    def __init__(self, hass: HomeAssistant, config_entry: ElectricUsageConfigEntry, api: ElectricUsageAPI):
        """Initialize the coordinator."""
        self.api = api
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name="Electric Usage Coordinator",
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self):
        """Fetch data from the API."""
        try:
            await self.api.login()
            return await self.api.get_usage_data()
        except ElectricUsageAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except ElectricUsageConnectionError as err:
            raise UpdateFailed(str(err)) from err
