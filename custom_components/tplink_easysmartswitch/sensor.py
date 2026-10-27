"""Support for the TP-Link Easy Smart Switch."""
from datetime import datetime
import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from . import get_device_info
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
                icon="mdi:download-network",
            )
        )
        entities.append(
            TpLinkSpeedSensor(
                controller,
                coordinator,
                port_number=port + 1,
                attribute=TPLINK_PORT_TX_GOOD_PKT,
                icon="mdi:upload-network",
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
        icon,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._last_value: float | None = None
        self._last_timestamp: datetime | None = None

        self.controller = controller
        self._port_number = port_number
        self._attribute = attribute
        self._attr_native_unit_of_measurement = "packets/s"
        self._attr_icon = icon

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
        self._attr_device_info = get_device_info(self.controller)
        # The first value is the reference of the next update
        self._update_speed()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Compute the speed from the new counter value."""
        self._update_speed()
        super()._handle_coordinator_update()

    def _update_speed(self) -> None:
        """Derive the speed from the packet counter since the previous update."""
        port_data = self.coordinator.data.get(self._port_number)
        if port_data is None or port_data.get(self._attribute) is None:
            self._attr_native_value = None
            return
        current_value = float(port_data[self._attribute])
        current_timestamp = self.coordinator.data[TIMESTAMP]

        if self._last_value is None or current_value < self._last_value:
            # First value, or counter reset by a restart or an overflow
            self._attr_native_value = None
        else:
            delta_time = (current_timestamp - self._last_timestamp).total_seconds()
            if delta_time <= 0:
                # Same data as the previous update
                return
            self._attr_native_value = round(
                (current_value - self._last_value) / delta_time, 2
            )

        self._last_value = current_value
        self._last_timestamp = current_timestamp
