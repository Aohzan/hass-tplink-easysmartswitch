"""Base entity of the TP-Link Easy Smart Switch integration."""

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import DOMAIN
from .coordinator import TpLinkSwitchCoordinator


class TpLinkSwitchEntity(CoordinatorEntity[TpLinkSwitchCoordinator]):
    """Base entity of a port of the switch."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TpLinkSwitchCoordinator,
        port_number: int,
        unique_id_suffix: str,
        translation_key: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        controller = coordinator.controller
        self._port_number = port_number
        self._attr_unique_id = slugify(
            f"{DOMAIN}_{controller.mac_address}_{unique_id_suffix}"
        )
        self._attr_translation_key = translation_key
        self._attr_translation_placeholders = {"port": f"{port_number:02}"}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, controller.mac_address)},
            manufacturer="TP-Link",
            model=controller.hardware_version,
            name=f"Switch {controller.host}",
            sw_version=controller.firmware_version,
            connections={(CONNECTION_NETWORK_MAC, controller.mac_address)},
            configuration_url=f"http://{controller.host}",
        )
