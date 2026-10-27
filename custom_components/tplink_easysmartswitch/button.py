"""Support for the TP-Link Easy Smart Switch reboot."""

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import TpLinkSwitchConfigEntry, TpLinkSwitchCoordinator
from .entity import TpLinkSwitchEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TpLinkSwitchConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the TP-Link Easy Smart Switch button platform."""
    async_add_entities([TpLinkSwitchRebootButton(entry.runtime_data)])


class TpLinkSwitchRebootButton(TpLinkSwitchEntity, ButtonEntity):
    """Reboot the switch."""

    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: TpLinkSwitchCoordinator) -> None:
        """Initialize the button."""
        super().__init__(coordinator, unique_id_suffix="reboot")

    async def async_press(self) -> None:
        """Reboot the switch."""
        await self.coordinator.async_reboot()
