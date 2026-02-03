from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
)

from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up SPC zone status sensors from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    device_info = data["device_info"]

    async_add_entities([
        SPCZoneStatus(
            coordinator=coordinator,
            device_info=device_info,
            zone=zone,
        )
        for zone in coordinator.data["zones"].values()
    ])


class SPCZoneStatus(CoordinatorEntity, SensorEntity):
    """Enum sensor representing SPC zone status."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_has_entity_name = True
    _attr_translation_key = "zone_status"
    _attr_options = [
        "normal",
        "open",
        "tamper",
        "disconnected",
        "inhibited",
    ]

    def __init__(self, coordinator, device_info, zone):
        super().__init__(coordinator)

        zone_id = zone["zone_id"]
        zone_name = zone["zone_name"]
        serial_number = device_info["serial_number"]
        unique_id = f"spc-{serial_number}-{zone_id}-status"

        self._zone_id = zone_id
        self._attr_name = f"{zone_name} status"
        self._attr_unique_id = unique_id
        self._attr_device_info = device_info

    @property
    def native_value(self):
        """Return the current zone status."""
        zone = self.coordinator.data["zones"].get(self._zone_id)
        if zone:
            return zone["status"]
