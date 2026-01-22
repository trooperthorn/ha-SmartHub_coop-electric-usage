import logging
from homeassistant import config_entries
import voluptuous as vol
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DEFAULT_LOGIN_URL = "https://bluebonnet.smarthub.coop/Login.html"
DEFAULT_USAGE_URL = "https://bluebonnet.smarthub.coop/Usage/Usage.htm"

class ElectricUsageConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the config flow for Electric Usage Downloader."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            # Ensure username and password are not empty
            try:
                if not user_input.get("username") or not user_input.get("password"):
                    errors["base"] = "missing_credentials"
                    _LOGGER.error("Missing credentials.")
                else:
                    # If no errors, create the config entry
                    return self.async_create_entry(
                        title="Electric Usage Downloader", data=user_input
                    )
            except Exception as e:
                _LOGGER.error(f"Error during config flow: {e}")
                errors["base"] = "unknown_error"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("username"): str,
                vol.Required("password"): str,
                vol.Required("login_url", default=DEFAULT_LOGIN_URL): str,
                vol.Required("usage_url", default=DEFAULT_USAGE_URL): str,
            }),
            errors=errors,
        )
