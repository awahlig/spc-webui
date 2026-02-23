from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.switch import SwitchEntity
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .spc import SPCError


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up SPC switch entities from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]

    coordinator = data["coordinator"]
    spc = data["spc"]
    get_zone_device_info = data["get_zone_device_info"]
    unique_prefix = data["unique_prefix"]

    async_add_entities([
        SPCZoneInhibit(
            coordinator=coordinator,
            spc=spc,
            device_info=get_zone_device_info(zone),
            unique_prefix=unique_prefix,
            zone=zone,
        )
        for zone in coordinator.data["zones"].values()
    ])


class SPCZoneInhibit(CoordinatorEntity, SwitchEntity):
    """Switch representing SPC zone inhibit state."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, spc, device_info, unique_prefix, zone):
        super().__init__(coordinator)
        self.spc = spc

        zone_id = zone["zone_id"]

        self._zone_id = zone_id
        self._attr_name = "Inhibit"
        self._attr_unique_id = f"{unique_prefix}-zone{zone_id}-inhibit"
        self._attr_device_info = device_info

    @property
    def is_on(self):
        """Return True when zone is inhibited."""
        zone = self.coordinator.data["zones"].get(self._zone_id)
        if zone:
            return (zone["status"] == "inhibit")
        return False

    async def _async_set_inhibit(self, inhibited):
        try:
            await self.spc.set_zone_inhibit(self._zone_id, inhibited)
        except SPCError as err:
            raise HomeAssistantError(str(err)) from err
        finally:
            await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs):
        """Inhibit this zone."""
        await self._async_set_inhibit(True)

    async def async_turn_off(self, **kwargs):
        """Uninhibit this zone."""
        await self._async_set_inhibit(False)
