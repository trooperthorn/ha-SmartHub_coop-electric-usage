from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "ha_electric_usage_downloader"
PLATFORMS = [Platform.SENSOR]
SCAN_INTERVAL = timedelta(minutes=15)
