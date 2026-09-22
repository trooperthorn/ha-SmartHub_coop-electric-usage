"""Config flow for the SmartHub co-op electric usage integration."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)

from .api import ServiceLocation, SmartHubAuthError, SmartHubClient, SmartHubError
from .const import (
    CONF_ACCOUNT,
    CONF_HOST,
    CONF_PROVIDER,
    CONF_SERVICE_LOCATION,
    DEFAULT_PROVIDER,
    DOMAIN,
    SMARTHUB_DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def _normalize_provider(value: str) -> str:
    """Turn a provider name or a pasted portal URL into a SmartHub host.

    Accepts a bare provider like ``bluebonnet``, a full host like
    ``bluebonnet.smarthub.coop``, or a pasted portal URL, and always returns
    ``<provider>.smarthub.coop``.
    """
    value = value.strip().lower()
    for prefix in ("https://", "http://"):
        value = value.removeprefix(prefix)
    value = value.split("/", 1)[0]
    value = value.removesuffix(f".{SMARTHUB_DOMAIN}").strip(".")
    return f"{value}.{SMARTHUB_DOMAIN}"


class SmartHubConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SmartHub."""

    VERSION = 2

    def __init__(self) -> None:
        """Initialize the flow."""
        self._data: dict[str, str] = {}
        self._locations: list[ServiceLocation] = []

    async def _async_try_login(
        self, data: dict[str, str]
    ) -> tuple[list[ServiceLocation], str | None]:
        client = SmartHubClient(
            async_create_clientsession(self.hass),
            data[CONF_HOST],
            data[CONF_USERNAME],
            data[CONF_PASSWORD],
        )
        try:
            return await client.async_get_service_locations(), None
        except SmartHubAuthError:
            return [], "invalid_auth"
        except SmartHubError:
            return [], "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected error validating SmartHub login")
            return [], "unknown"

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect the portal host and credentials, and verify them."""
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {
                CONF_HOST: _normalize_provider(user_input[CONF_PROVIDER]),
                CONF_USERNAME: user_input[CONF_USERNAME],
                CONF_PASSWORD: user_input[CONF_PASSWORD],
            }
            locations, error = await self._async_try_login(data)
            if error:
                errors["base"] = error
            elif not locations:
                errors["base"] = "no_locations"
            else:
                self._data = data
                self._locations = locations
                if len(locations) == 1:
                    return await self._async_create(locations[0])
                return await self.async_step_location()

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_PROVIDER): str,
                        vol.Required(CONF_USERNAME): str,
                        vol.Required(CONF_PASSWORD): str,
                    }
                ),
                user_input or {CONF_PROVIDER: DEFAULT_PROVIDER},
            ),
            errors=errors,
        )

    async def async_step_location(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user pick one service location when the login has several."""
        options = {
            f"{loc.account}|{loc.service_location}": loc for loc in self._locations
        }
        if user_input is not None:
            return await self._async_create(options[user_input["location"]])
        return self.async_show_form(
            step_id="location",
            data_schema=vol.Schema(
                {
                    vol.Required("location"): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(
                                    value=key,
                                    label=f"Account {loc.account}, location {loc.service_location}",
                                )
                                for key, loc in options.items()
                            ]
                        )
                    )
                }
            ),
        )

    async def _async_create(self, location: ServiceLocation) -> ConfigFlowResult:
        await self.async_set_unique_id(
            f"{self._data[CONF_HOST]}_{location.account}_{location.service_location}"
        )
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=f"{self._data[CONF_HOST].split('.')[0].title()} {location.account}",
            data={
                **self._data,
                CONF_ACCOUNT: location.account,
                CONF_SERVICE_LOCATION: location.service_location,
            },
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start reauthentication after the portal rejects stored credentials."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a new password and verify it."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {**entry.data, CONF_PASSWORD: user_input[CONF_PASSWORD]}
            _, error = await self._async_try_login(data)
            if error:
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(entry, data=data)
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            description_placeholders={"username": entry.data[CONF_USERNAME]},
            errors=errors,
        )
