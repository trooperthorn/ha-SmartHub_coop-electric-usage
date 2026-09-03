import logging
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import UnitOfEnergy
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from . import ElectricUsageConfigEntry

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry: ElectricUsageConfigEntry, async_add_entities):
    """Set up the sensor platform from a config entry."""
    coordinator = config_entry.runtime_data
    async_add_entities([ElectricUsageSensor(coordinator)])

class ElectricUsageSensor(CoordinatorEntity, SensorEntity):
    """Representation of an electric usage sensor."""

    _attr_device_class = SensorDeviceClass.ENERGY

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_name = "Electric Usage"
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_unique_id = "electric_usage"

    @property
    def native_value(self):
        """Return the current value of the sensor."""
        return self.coordinator.data.get("usage") if self.coordinator.data else None

    @property
    def available(self):
        """Return True if the sensor is available."""
        return self.coordinator.last_update_success
