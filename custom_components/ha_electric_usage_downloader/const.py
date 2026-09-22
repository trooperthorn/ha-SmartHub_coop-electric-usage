"""Constants for the SmartHub electric usage integration."""

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "ha_electric_usage_downloader"
PLATFORMS = [Platform.SENSOR]

# SmartHub is a white-label portal; every co-op runs the same JSON services
# under its own subdomain of this domain.
SMARTHUB_DOMAIN = "smarthub.coop"
DEFAULT_PROVIDER = "bluebonnet"

CONF_PROVIDER = "provider"
CONF_HOST = "host"
CONF_ACCOUNT = "account"
CONF_SERVICE_LOCATION = "service_location"

# Meter data is published hours after the fact, so frequent polling only adds
# load on the co-op portal without producing newer readings.
SCAN_INTERVAL = timedelta(hours=2)

# How far back to look on every refresh. Readings can be revised or arrive
# late, so a rolling window re-imports recent hours instead of trusting a
# single pass.
REFRESH_WINDOW = timedelta(days=3)

# How far back to import on the first run for a location.
INITIAL_BACKFILL = timedelta(days=30)

# The portal answers usage requests asynchronously: the first POST returns
# PENDING and the client re-posts until the job reports COMPLETE.
POLL_INTERVAL_SECONDS = 2.0
POLL_MAX_ATTEMPTS = 15

# Refresh the bearer token this long before the portal says it expires.
TOKEN_REFRESH_MARGIN = timedelta(minutes=2)

CHANNEL_CONSUMPTION = "consumption"
CHANNEL_GENERATION = "generation"
CHANNEL_NET = "net"

# SmartHub reports each meter channel with a flow direction. This maps that
# direction to the channel name used for statistics and sensors.
FLOW_TO_CHANNEL = {
    "FORWARD": CHANNEL_CONSUMPTION,
    "REVERSE": CHANNEL_GENERATION,
    "NET": CHANNEL_NET,
}
