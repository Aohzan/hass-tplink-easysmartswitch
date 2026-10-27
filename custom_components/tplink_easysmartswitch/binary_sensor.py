"""Support for the TP-Link Easy Smart Switch port links."""

from collections.abc import Mapping
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    TPLINK_PORT_LINK_STATUS,
    TPLINK_PORT_RX_BAD_PKT,
    TPLINK_PORT_RX_GOOD_PKT,
    TPLINK_PORT_STATE,
    TPLINK_PORT_TX_BAD_PKT,
    TPLINK_PORT_TX_GOOD_PKT,
)
from .coordinator import TpLinkSwitchConfigEntry, TpLinkSwitchCoordinator
from .entity import TpLinkSwitchEntity

PARALLEL_UPDATES = 0

# Attribute name of each port value
PORT_ATTRIBUTES = {
    "status": TPLINK_PORT_STATE,
    "link_status": TPLINK_PORT_LINK_STATUS,
    "tx_good_packet": TPLINK_PORT_TX_GOOD_PKT,
    "tx_bad_packet": TPLINK_PORT_TX_BAD_PKT,
    "rx_good_packet": TPLINK_PORT_RX_GOOD_PKT,
    "rx_bad_paquet": TPLINK_PORT_RX_BAD_PKT,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TpLinkSwitchConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the TP-Link Easy Smart binary sensor platform."""
    coordinator = entry.runtime_data
    async_add_entities(
        TpLinkSwitchBinarySensor(coordinator, port_number)
        for port_number in range(1, coordinator.controller.port_number + 1)
    )


class TpLinkSwitchBinarySensor(TpLinkSwitchEntity, BinarySensorEntity):
    """Port enabled with a link up."""

    def __init__(self, coordinator: TpLinkSwitchCoordinator, port_number: int) -> None:
        """Initialize the binary sensor."""
        super().__init__(
            coordinator,
            port_number,
            unique_id_suffix=f"binary_sensor_{port_number}",
            translation_key="port",
        )

    @property
    def _port_data(self) -> dict[str, Any] | None:
        """Return the values of the port."""
        return self.coordinator.data.get(self._port_number)

    @property
    def is_on(self) -> bool | None:
        """Return the state."""
        if (port_data := self._port_data) is None:
            return None
        return (
            port_data[TPLINK_PORT_STATE] == "Enabled"
            and port_data[TPLINK_PORT_LINK_STATUS] != "Link Down"
        )

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the state attributes."""
        if (port_data := self._port_data) is None:
            return None
        return {name: port_data[key] for name, key in PORT_ATTRIBUTES.items()}
