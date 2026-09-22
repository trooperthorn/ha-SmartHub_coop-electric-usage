"""Sensors summarizing the most recent SmartHub readings.

These sensors are informational. The Energy dashboard should use the
imported statistics (named "SmartHub <account> consumption" and
"... generation"), which are stamped with the hour the energy was used.
"""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import EntityCategory, UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CHANNEL_CONSUMPTION,
    CHANNEL_GENERATION,
    CHANNEL_NET,
    CONF_HOST,
    DOMAIN,
)
from .coordinator import SmartHubConfigEntry, SmartHubCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmartHubConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create sensors for the channels the meter actually reports."""
    coordinator = entry.runtime_data
    channels = [
        c
        for c in (CHANNEL_CONSUMPTION, CHANNEL_GENERATION, CHANNEL_NET)
        if c in coordinator.data
    ]
    entities: list[SensorEntity] = [
        SmartHubEnergySensor(coordinator, c) for c in channels
    ]
    entities.append(SmartHubLastReadingSensor(coordinator))
    async_add_entities(entities)


class _SmartHubEntity(CoordinatorEntity[SmartHubCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: SmartHubCoordinator, key: str) -> None:
        super().__init__(coordinator)
        loc = coordinator.location
        base = f"{loc.account}_{loc.service_location}"
        self._attr_unique_id = f"{base}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, base)},
            name=f"SmartHub meter {loc.account}",
            manufacturer="NISC SmartHub",
            model=coordinator.config_entry.data[CONF_HOST],
            entry_type=DeviceEntryType.SERVICE,
        )


class SmartHubEnergySensor(_SmartHubEntity, SensorEntity):
    """Energy over the last 24 hours of available readings for one channel."""

    # No state_class on purpose: this is a rolling window, and giving it one
    # would make the recorder build a second, misleading energy statistic.
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR

    def __init__(self, coordinator: SmartHubCoordinator, channel: str) -> None:
        super().__init__(coordinator, f"{channel}_last_24h")
        self._channel = channel
        self._attr_translation_key = f"{channel}_last_24h"

    @property
    def available(self) -> bool:
        return super().available and self._channel in (self.coordinator.data or {})

    @property
    def native_value(self) -> float | None:
        item = (self.coordinator.data or {}).get(self._channel)
        return item.last_24h_kwh if item else None


class SmartHubLastReadingSensor(_SmartHubEntity, SensorEntity):
    """Timestamp of the newest reading the portal has published."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "last_reading"

    def __init__(self, coordinator: SmartHubCoordinator) -> None:
        super().__init__(coordinator, "last_reading")

    @property
    def native_value(self):
        data = self.coordinator.data or {}
        times = [item.last_reading for item in data.values()]
        return max(times) if times else None
