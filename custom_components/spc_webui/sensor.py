from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
)

from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up SPC sensor entities from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]

    coordinator = data["coordinator"]
    get_zone_device_info = data["get_zone_device_info"]
    unique_prefix = data["unique_prefix"]

    async_add_entities([
        SPCZoneStatus(
            coordinator=coordinator,
            device_info=get_zone_device_info(zone),
            unique_prefix=unique_prefix,
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
        "actuated",
        "tamper",
        "disconnected",
        "inhibit",
    ]

    def __init__(self, coordinator, device_info, unique_prefix, zone):
        super().__init__(coordinator)

        zone_id = zone["zone_id"]

        self._zone_id = zone_id
        self._attr_name = "Status"
        self._attr_unique_id = f"{unique_prefix}-zone{zone_id}-status"
        self._attr_device_info = device_info

    @property
    def native_value(self):
        """Return the current zone status."""
        zone = self.coordinator.data["zones"].get(self._zone_id)
        if zone:
            return zone["status"]
