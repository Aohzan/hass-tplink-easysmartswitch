"""Base entities of the TP-Link Easy Smart Switch integration."""

from typing import cast

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import DOMAIN
from .coordinator import TpLinkSwitchCoordinator


class TpLinkSwitchEntity(CoordinatorEntity[TpLinkSwitchCoordinator]):
    """Base entity of the switch."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TpLinkSwitchCoordinator,
        unique_id_suffix: str,
        translation_key: str | None = None,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        controller = coordinator.controller
        # The setup of the coordinator fails when the switch has no MAC address
        mac_address = cast(str, controller.mac_address)
        self._attr_unique_id = slugify(f"{DOMAIN}_{mac_address}_{unique_id_suffix}")
        self._attr_translation_key = translation_key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, mac_address)},
            manufacturer="TP-Link",
            model=controller.hardware_version,
            name=f"Switch {controller.host}",
            sw_version=controller.firmware_version,
            connections={(CONNECTION_NETWORK_MAC, mac_address)},
            configuration_url=f"http://{controller.host}",
        )


class TpLinkSwitchPortEntity(TpLinkSwitchEntity):
    """Base entity of a port of the switch."""

    def __init__(
        self,
        coordinator: TpLinkSwitchCoordinator,
        port_number: int,
        unique_id_suffix: str,
        translation_key: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, unique_id_suffix, translation_key)
        self._port_number = port_number
        self._attr_translation_placeholders = {"port": f"{port_number:02}"}
