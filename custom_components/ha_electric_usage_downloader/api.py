"""Client for the NISC SmartHub consumer portal JSON services.

SmartHub is a single-page application. The browser does not scrape HTML; it
authenticates against ``/services/oauth/auth/v2`` for a bearer token and then
requests usage from ``/services/secured/utility-usage/poll``, re-posting the
same request until the server finishes building the result. This client
reproduces that exchange, which was observed against bluebonnet.smarthub.coop
(portal version 26.16.0) in September 2026.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import aiohttp

from .const import (
    FLOW_TO_CHANNEL,
    POLL_INTERVAL_SECONDS,
    POLL_MAX_ATTEMPTS,
    TOKEN_REFRESH_MARGIN,
)

_LOGGER = logging.getLogger(__name__)

USER_AGENT = "HomeAssistant-SmartHub-Usage (+https://github.com/trooperthorn/ha-SmartHub_coop-electric-usage)"
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30)


class SmartHubError(Exception):
    """Base error for the SmartHub client."""


class SmartHubAuthError(SmartHubError):
    """The portal rejected the credentials or the session token."""


class SmartHubConnectionError(SmartHubError):
    """The portal could not be reached or returned an unexpected response."""


# Names kept so existing imports and tests do not break during the transition.
ElectricUsageAuthError = SmartHubAuthError
ElectricUsageConnectionError = SmartHubConnectionError


@dataclass(frozen=True)
class ServiceLocation:
    """One account and service location pair the user can read usage for."""

    account: str
    service_location: str


@dataclass
class UsageResult:
    """Hourly (or coarser) readings grouped by meter channel.

    ``readings`` maps a channel name (consumption, generation, net) to a list
    of ``(interval_start, kwh)`` tuples sorted by time. Generation is stored as
    a positive number even though the portal charts it as negative.
    """

    unit: str
    readings: dict[str, list[tuple[datetime, float]]] = field(default_factory=dict)


class SmartHubClient:
    """Talks to one SmartHub portal on behalf of one user."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        username: str,
        password: str,
    ) -> None:
        """Initialize the client.

        The session should have its own cookie jar (``async_create_clientsession``)
        because login depends on the portal's XSRF cookie.
        """
        self._session = session
        self._base = f"https://{host}"
        self._username = username
        self._password = password
        self._token: str | None = None
        self._token_expires: datetime | None = None

    @property
    def username(self) -> str:
        """Return the configured username."""
        return self._username

    def _token_valid(self) -> bool:
        if self._token is None or self._token_expires is None:
            return False
        return datetime.now(UTC) < self._token_expires - TOKEN_REFRESH_MARGIN

    async def async_login(self) -> None:
        """Obtain a bearer token.

        The login POST carries an ``X-XSRF-TOKEN`` header whose value comes
        from the ``XSRF-TOKEN`` cookie the portal sets when the UI loads, so
        the UI root is fetched first.
        """
        headers = {"User-Agent": USER_AGENT}
        try:
            async with self._session.get(
                f"{self._base}/ui/", headers=headers, timeout=REQUEST_TIMEOUT
            ) as resp:
                await resp.read()
            xsrf = None
            for cookie in self._session.cookie_jar:
                if cookie.key == "XSRF-TOKEN":
                    xsrf = cookie.value
            if xsrf:
                headers["X-XSRF-TOKEN"] = xsrf
            async with self._session.post(
                f"{self._base}/services/oauth/auth/v2",
                data={"userId": self._username, "password": self._password},
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            ) as resp:
                if resp.status in (400, 401, 403):
                    raise SmartHubAuthError(f"Login rejected with status {resp.status}")
                if resp.status != 200:
                    raise SmartHubConnectionError(
                        f"Login failed with status {resp.status}"
                    )
                body = await resp.json(content_type=None)
        except aiohttp.ClientError as err:
            raise SmartHubConnectionError(f"Cannot reach {self._base}: {err}") from err
        except ValueError as err:
            raise SmartHubConnectionError("Login response was not JSON") from err

        token = body.get("authorizationToken") if isinstance(body, dict) else None
        if not token:
            # A 200 with no token is how the portal reports bad credentials
            # or a pending second factor; either way the user must act.
            status = body.get("status") if isinstance(body, dict) else None
            raise SmartHubAuthError(f"Login did not return a token (status {status!r})")

        self._token = token
        self._token_expires = _parse_expiry(body)
        _LOGGER.debug(
            "Logged in to %s; token valid until %s", self._base, self._token_expires
        )

    async def _request(
        self, method: str, path: str, json_body: Any | None = None
    ) -> Any:
        """Make an authenticated request, logging in again once on a 401."""
        for attempt in (1, 2):
            if not self._token_valid():
                await self.async_login()
            headers = {
                "User-Agent": USER_AGENT,
                "Authorization": f"Bearer {self._token}",
                "X-NISC-SMARTHUB-USERNAME": self._username,
                "Accept": "application/json",
            }
            try:
                async with self._session.request(
                    method,
                    f"{self._base}{path}",
                    json=json_body,
                    headers=headers,
                    timeout=REQUEST_TIMEOUT,
                ) as resp:
                    if resp.status == 401 and attempt == 1:
                        self._token = None
                        continue
                    if resp.status in (401, 403):
                        raise SmartHubAuthError(
                            f"{path} rejected the session ({resp.status})"
                        )
                    if resp.status != 200:
                        raise SmartHubConnectionError(
                            f"{path} returned status {resp.status}"
                        )
                    return await resp.json(content_type=None)
            except aiohttp.ClientError as err:
                raise SmartHubConnectionError(f"Error calling {path}: {err}") from err
            except ValueError as err:
                raise SmartHubConnectionError(f"{path} did not return JSON") from err
        raise SmartHubAuthError(f"{path} rejected a fresh session")  # pragma: no cover

    async def async_get_service_locations(self) -> list[ServiceLocation]:
        """Return every account and service location on the login."""
        data = await self._request("GET", "/services/secured/accounts")
        if not isinstance(data, list):
            raise SmartHubConnectionError("Unexpected accounts response")
        return [
            ServiceLocation(str(item["account"]), str(loc))
            for item in data
            for loc in item.get("serviceLocations") or []
        ]

    async def async_get_usage(
        self,
        location: ServiceLocation,
        start: datetime,
        end: datetime,
        time_frame: str = "HOURLY",
    ) -> UsageResult:
        """Fetch usage between ``start`` and ``end`` for one location."""
        body = {
            "timeFrame": time_frame,
            "userId": self._username,
            "screen": "USAGE_EXPLORER",
            "includeDemand": False,
            "serviceLocationNumber": location.service_location,
            "accountNumber": location.account,
            "industries": ["ELECTRIC"],
            "startDateTime": int(start.timestamp() * 1000),
            "endDateTime": int(end.timestamp() * 1000),
        }
        for _ in range(POLL_MAX_ATTEMPTS):
            data = await self._request(
                "POST", "/services/secured/utility-usage/poll", body
            )
            status = data.get("status") if isinstance(data, dict) else None
            if status == "COMPLETE":
                return parse_usage(data)
            if status != "PENDING":
                raise SmartHubConnectionError(f"Usage poll returned status {status!r}")
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
        raise SmartHubConnectionError("Usage poll did not complete in time")


def _parse_expiry(body: dict[str, Any]) -> datetime:
    """Work out when the token expires.

    The login response carries both ``expiration`` and ``expiresIn``. The
    observed ``expiration`` is a millisecond epoch; ``expiresIn`` is treated
    as seconds. If neither is usable the token is assumed good for ten
    minutes, and a 401 triggers a fresh login regardless.
    """
    now = datetime.now(UTC)
    expiration = body.get("expiration")
    if isinstance(expiration, (int, float)) and expiration > 1e12:
        return datetime.fromtimestamp(expiration / 1000, UTC)
    expires_in = body.get("expiresIn")
    if isinstance(expires_in, (int, float)) and expires_in > 0:
        return now + timedelta(seconds=expires_in)
    return now + timedelta(minutes=10)


def parse_usage(data: dict[str, Any]) -> UsageResult:
    """Convert a COMPLETE poll response into per-channel readings.

    Channels are identified by the meter's ``flowDirection`` (FORWARD,
    REVERSE, NET) joined on the ``channel`` number, not by the display name,
    because the display name embeds the meter number and wording that a
    co-op can change.
    """
    try:
        electric = data["data"]["ELECTRIC"]
    except (KeyError, TypeError) as err:
        raise SmartHubConnectionError("Usage response has no ELECTRIC data") from err
    if not electric:
        return UsageResult(unit="KWH")

    block = electric[0]
    unit = str(block.get("unitOfMeasure", "KWH"))
    channel_names: dict[Any, str] = {}
    for meter in block.get("meters") or []:
        name = FLOW_TO_CHANNEL.get(str(meter.get("flowDirection", "")).upper())
        if name:
            channel_names[meter.get("channel")] = name

    result = UsageResult(unit=unit)
    for series in block.get("series") or []:
        name = channel_names.get(series.get("channel"))
        if name is None:
            # Meters without a flow direction are single-channel (no solar).
            name = "consumption" if not series.get("isNet") else "net"
        points: list[tuple[datetime, float]] = []
        for point in series.get("data") or []:
            x, y = point.get("x"), point.get("y")
            if x is None or y is None:
                continue
            value = float(y)
            if name == "generation":
                value = abs(value)
            points.append((datetime.fromtimestamp(x / 1000, UTC), value))
        points.sort(key=lambda p: p[0])
        result.readings.setdefault(name, []).extend(points)
    return result
