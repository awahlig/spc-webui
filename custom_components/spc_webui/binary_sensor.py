from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)

from .const import DOMAIN


ENTITY_NAME = {
    "alarm": "Motion",
    "entry/exit": "Contact",
    "entry/exit 2": "Contact",
    "fire": "Fire",
    "technical": "Fault",
}


DEVICE_CLASS = {
    "alarm": BinarySensorDeviceClass.MOTION,
    "entry/exit": BinarySensorDeviceClass.OPENING,
    "entry/exit 2": BinarySensorDeviceClass.OPENING,
    "fire": BinarySensorDeviceClass.SMOKE,
    "technical": BinarySensorDeviceClass.PROBLEM,
}


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up SPC binary sensor entity from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]

    coordinator = data["coordinator"]
    get_zone_device_info = data["get_zone_device_info"]
    unique_prefix = data["unique_prefix"]

    async_add_entities([
        SPCZoneInputOpen(
            coordinator=coordinator,
            device_info=get_zone_device_info(zone),
            unique_prefix=unique_prefix,
            zone=zone,
        )
        for zone in coordinator.data["zones"].values()
    ])


class SPCZoneInputOpen(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor representing SPC zone input open state."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, device_info, unique_prefix, zone):
        super().__init__(coordinator)

        zone_id = zone["zone_id"]
        zone_type = zone["zone_type"]

        self._zone_id = zone_id
        self._attr_name = ENTITY_NAME.get(zone_type, "Input Open")
        self._attr_device_class = DEVICE_CLASS.get(zone_type)
        self._attr_unique_id = f"{unique_prefix}-zone{zone_id}-open"
        self._attr_device_info = device_info

    @property
    def is_on(self):
        """Return the current zone open state."""
        zone = self.coordinator.data["zones"].get(self._zone_id)
        if zone:
            return (zone["input"] == "open")
        return False
