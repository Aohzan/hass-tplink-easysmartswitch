"""Support for the TP-Link Easy Smart Switch."""
import logging

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify
from .tplink import EasySwitch
from .const import (
    CONTROLLER,
    COORDINATOR,
    DOMAIN,
    TPLINK_PORT_LINK_STATUS,
    TPLINK_PORT_RX_BAD_PKT,
    TPLINK_PORT_RX_GOOD_PKT,
    TPLINK_PORT_STATE,
    TPLINK_PORT_TX_BAD_PKT,
    TPLINK_PORT_TX_GOOD_PKT,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the TP-Link Easy Smart binary sensor platform."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    controller: EasySwitch = data[CONTROLLER]
    coordinator = data[COORDINATOR]

    entities = []
    ports_count = controller.port_number
    for port in range(ports_count):
        entities.append(
            TpLinkSwitchBinarySensor(controller, coordinator, port_number=port + 1)
        )
    if entities:
        async_add_entities(entities)


class TpLinkSwitchBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Representation of a generic TP-Link Easy Smart Switch sensor."""

    def __init__(
        self,
        controller,
        coordinator,
        port_number,
    ):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.controller = controller
        self._port_number = port_number

        self._attr_name = f"Port {self._port_number:02}"

        self._attr_unique_id = slugify(
            "_".join(
                [
                    DOMAIN,
                    self.controller.mac_address,
                    "binary_sensor",
                    str(self._port_number),
                ]
            )
        )
        self._attr_device_info = {
            "identifiers": {(DOMAIN, self.controller.mac_address)},
            "via_device": (DOMAIN, self.controller.mac_address),
        }

    @property
    def is_on(self):
        """Return the state."""
        return (
            self.coordinator.data[self._port_number][TPLINK_PORT_STATE] == "Enabled"
            and self.coordinator.data[self._port_number][TPLINK_PORT_LINK_STATUS]
            != "Link Down"
        )

    @property
    def icon(self):
        """Return the port icon."""
        return "mdi:lan-connect" if self.is_on else "mdi:lan-disconnect"

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        if self.coordinator.data:
            return {
                "status": self.coordinator.data[self._port_number][TPLINK_PORT_STATE],
                "link_status": self.coordinator.data[self._port_number][
                    TPLINK_PORT_LINK_STATUS
                ],
                "tx_good_packet": self.coordinator.data[self._port_number][
                    TPLINK_PORT_TX_GOOD_PKT
                ],
                "tx_bad_packet": self.coordinator.data[self._port_number][
                    TPLINK_PORT_TX_BAD_PKT
                ],
                "rx_good_packet": self.coordinator.data[self._port_number][
                    TPLINK_PORT_RX_GOOD_PKT
                ],
                "rx_bad_paquet": self.coordinator.data[self._port_number][
                    TPLINK_PORT_RX_BAD_PKT
                ],
            }
