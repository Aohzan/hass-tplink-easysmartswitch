"""Support for the TP-Link Easy Smart Switch."""
import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import (
    CONTROLLER,
    COORDINATOR,
    DOMAIN,
    TIMESTAMP,
    TPLINK_PORT_RX_GOOD_PKT,
    TPLINK_PORT_TX_GOOD_PKT,
)
from .tplink import EasySwitch

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the TP-Link Easy Smart Switch platform."""
    data = hass.data[DOMAIN][entry.entry_id]
    controller: EasySwitch = data[CONTROLLER]
    coordinator = data[COORDINATOR]

    entities = []
    ports_count = controller.port_number
    for port in range(ports_count):
        entities.append(
            TpLinkSpeedSensor(
                controller,
                coordinator,
                port_number=port + 1,
                attribute=TPLINK_PORT_RX_GOOD_PKT,
            )
        )
        entities.append(
            TpLinkSpeedSensor(
                controller,
                coordinator,
                port_number=port + 1,
                attribute=TPLINK_PORT_TX_GOOD_PKT,
            )
        )
    if entities:
        async_add_entities(entities)


class TpLinkSpeedSensor(CoordinatorEntity, SensorEntity):
    """Representation of a generic TP-Link Easy Smart Switch sensor."""

    def __init__(
        self,
        controller,
        coordinator,
        port_number,
        attribute,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._last_value = None
        self._last_timestamp = None

        self.controller = controller
        self._port_number = port_number
        self._attribute = attribute
        self._attr_unit_of_measurement = "packets/s"

        suffix = "Ingress" if attribute == TPLINK_PORT_RX_GOOD_PKT else "Egress"
        self._attr_name = f"Port {port_number:02} - {suffix}"
        self._attr_unique_id = slugify(
            "_".join(
                [
                    DOMAIN,
                    self.controller.mac_address,
                    "speed_sensor",
                    str(port_number),
                    attribute,
                ]
            )
        )
        self._attr_device_info = {
            "identifiers": {(DOMAIN, self.controller.mac_address)},
            "via_device": (DOMAIN, self.controller.mac_address),
        }

        self._state = None

    def _has_overflowed(self, current_value) -> bool:
        """Check if value has overflowed."""
        return current_value < self._last_value

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        current_value = int(self.coordinator.data[self._port_number][self._attribute])
        if current_value is None:
            return None
        current_timestamp = self.coordinator.data[TIMESTAMP]
        if self._last_value is None or self._has_overflowed(current_value):
            self._last_value = current_value
            self._last_timestamp = current_timestamp
            return None

        # Calculate derivative.
        delta_value = current_value - self._last_value
        delta_time = current_timestamp - self._last_timestamp
        if delta_time.total_seconds() == 0:
            # Prevent division by 0.
            return None
        derived = delta_value / delta_time.total_seconds()

        # Store current values for future use.
        self._last_value = current_value
        self._last_timestamp = current_timestamp

        return round(derived, 2)
