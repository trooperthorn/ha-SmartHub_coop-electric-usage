"""Coordinator that pulls SmartHub usage and imports it as statistics.

Meter readings arrive hours to a day late, so a normal sensor state would
record them against the wrong hour. Instead, each hourly reading is written
into the recorder as an external statistic stamped with the hour it was
actually used. The Energy dashboard reads those statistics directly.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import (
    StatisticData,
    StatisticMeanType,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    get_last_statistics,
    statistics_during_period,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import EnergyConverter

from .api import (
    ServiceLocation,
    SmartHubAuthError,
    SmartHubClient,
    SmartHubError,
    UsageResult,
)
from .const import DOMAIN, INITIAL_BACKFILL, REFRESH_WINDOW, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

type SmartHubConfigEntry = ConfigEntry[SmartHubCoordinator]


@dataclass
class ChannelSummary:
    """Latest known figures for one channel, exposed through sensors."""

    last_24h_kwh: float
    last_reading: datetime


def statistic_id(location: ServiceLocation, channel: str) -> str:
    """Return the external statistic id for a channel.

    External ids must be ``<domain>:<object_id>`` with a lowercase object id,
    so account and location numbers are normalized.
    """
    raw = f"{location.account}_{location.service_location}_{channel}"
    object_id = "".join(c if c.isalnum() else "_" for c in raw.lower())
    return f"{DOMAIN}:{object_id}"


class SmartHubCoordinator(DataUpdateCoordinator[dict[str, ChannelSummary]]):
    """Fetches usage for one service location."""

    config_entry: SmartHubConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: SmartHubConfigEntry,
        client: SmartHubClient,
        location: ServiceLocation,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"SmartHub {location.account}",
            update_interval=SCAN_INTERVAL,
        )
        self.client = client
        self.location = location

    async def _async_update_data(self) -> dict[str, ChannelSummary]:
        now = dt_util.utcnow()
        start = await self._async_window_start(now)
        try:
            usage = await self.client.async_get_usage(self.location, start, now)
        except SmartHubAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except SmartHubError as err:
            raise UpdateFailed(str(err)) from err

        await self._async_import_statistics(usage)
        return _summarize(usage)

    async def _async_window_start(self, now: datetime) -> datetime:
        """Pick the start of the fetch window.

        Normally this is ``REFRESH_WINDOW`` ago so late or revised readings
        are re-imported. If statistics are older than that (Home Assistant
        was down), the window reaches back to the last imported hour. On the
        very first run it reaches back ``INITIAL_BACKFILL``.
        """
        oldest_needed = now - REFRESH_WINDOW
        last = await get_instance(self.hass).async_add_executor_job(
            get_last_statistics,
            self.hass,
            1,
            statistic_id(self.location, "consumption"),
            True,
            {"sum"},
        )
        rows = next(iter(last.values()), [])
        if not rows:
            start = now - INITIAL_BACKFILL
        else:
            last_start = dt_util.utc_from_timestamp(rows[0]["start"])
            start = min(oldest_needed, last_start)
        return start.replace(minute=0, second=0, microsecond=0)

    async def _async_import_statistics(self, usage: UsageResult) -> None:
        for channel, points in usage.readings.items():
            if not points:
                continue
            stat_id = statistic_id(self.location, channel)
            first_hour = points[0][0]
            base = await self._async_sum_before(stat_id, first_hour)

            running = base
            stats: list[StatisticData] = []
            for when, kwh in points:
                running += kwh
                stats.append(StatisticData(start=when, state=kwh, sum=running))

            metadata = StatisticMetaData(
                mean_type=StatisticMeanType.NONE,
                has_sum=True,
                name=f"SmartHub {self.location.account} {channel}",
                source=DOMAIN,
                statistic_id=stat_id,
                unit_class=EnergyConverter.UNIT_CLASS,
                unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            )
            async_add_external_statistics(self.hass, metadata, stats)

    async def _async_sum_before(self, stat_id: str, hour: datetime) -> float:
        """Return the cumulative sum of the last imported hour before ``hour``.

        Rewriting a window of hours with a sum anchored here keeps the series
        continuous even when the portal revises readings inside the window.
        """
        rows = await get_instance(self.hass).async_add_executor_job(
            statistics_during_period,
            self.hass,
            hour - INITIAL_BACKFILL,
            hour,
            {stat_id},
            "hour",
            None,
            {"sum"},
        )
        series = rows.get(stat_id) or []
        if not series:
            return 0.0
        return float(series[-1].get("sum") or 0.0)


def _summarize(usage: UsageResult) -> dict[str, ChannelSummary]:
    summary: dict[str, ChannelSummary] = {}
    for channel, points in usage.readings.items():
        if not points:
            continue
        last_time = points[-1][0]
        cutoff = last_time - timedelta(hours=23)
        total = sum(kwh for when, kwh in points if when >= cutoff)
        summary[channel] = ChannelSummary(round(total, 3), last_time)
    return summary
