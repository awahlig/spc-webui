from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)

from .const import DOMAIN


DEVICE_CLASS = {
    "alarm": BinarySensorDeviceClass.MOTION,
    "entry/exit": BinarySensorDeviceClass.OPENING,
    "entry/exit 2": BinarySensorDeviceClass.OPENING,
    "fire": BinarySensorDeviceClass.SMOKE,
    "technical": BinarySensorDeviceClass.POWER,
}


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up SPC binary sensor entity from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    device_info = data["device_info"]

    async_add_entities([
        SPCZoneInput(
            coordinator=coordinator,
            device_info=device_info,
            zone=zone,
        )
        for zone in coordinator.data["zones"].values()
    ])


class SPCZoneInput(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor representing SPC zone active state."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, device_info, zone):
        super().__init__(coordinator)

        zone_id = zone["zone_id"]
        zone_name = zone["zone_name"]
        device_class = DEVICE_CLASS.get(zone["zone_type"])
        serial_number = device_info["serial_number"]
        unique_id = f"spc-{serial_number}-{zone_id}"

        self._zone_id = zone_id
        self._attr_name = zone_name
        self._attr_device_class = device_class
        self._attr_unique_id = unique_id
        self._attr_device_info = device_info

    @property
    def is_on(self):
        """Return the current zone input state."""
        zone = self.coordinator.data["zones"].get(self._zone_id)
        if zone:
            return (zone["input"] == "open")
        return False
