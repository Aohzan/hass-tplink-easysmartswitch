"""Support for the TP-Link Easy Smart Switch port speeds."""

from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import TIMESTAMP, TPLINK_PORT_RX_GOOD_PKT, TPLINK_PORT_TX_GOOD_PKT
from .coordinator import TpLinkSwitchConfigEntry, TpLinkSwitchCoordinator
from .entity import TpLinkSwitchEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class TpLinkSpeedSensorEntityDescription(SensorEntityDescription):
    """Describe a speed sensor derived from a packet counter of a port."""

    counter: str


SPEED_SENSORS = (
    TpLinkSpeedSensorEntityDescription(
        key="ingress",
        translation_key="ingress",
        counter=TPLINK_PORT_RX_GOOD_PKT,
        native_unit_of_measurement="packets/s",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    TpLinkSpeedSensorEntityDescription(
        key="egress",
        translation_key="egress",
        counter=TPLINK_PORT_TX_GOOD_PKT,
        native_unit_of_measurement="packets/s",
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TpLinkSwitchConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the TP-Link Easy Smart Switch platform."""
    coordinator = entry.runtime_data
    async_add_entities(
        TpLinkSpeedSensor(coordinator, port_number, description)
        for port_number in range(1, coordinator.controller.port_number + 1)
        for description in SPEED_SENSORS
    )


class TpLinkSpeedSensor(TpLinkSwitchEntity, SensorEntity):
    """Packets per second received or sent by a port."""

    entity_description: TpLinkSpeedSensorEntityDescription

    def __init__(
        self,
        coordinator: TpLinkSwitchCoordinator,
        port_number: int,
        description: TpLinkSpeedSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator,
            port_number,
            unique_id_suffix=f"speed_sensor_{port_number}_{description.counter}",
            translation_key=description.key,
        )
        self.entity_description = description
        self._last_value: float | None = None
        self._last_timestamp: datetime | None = None
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
        if port_data is None or port_data.get(self.entity_description.counter) is None:
            self._attr_native_value = None
            return
        current_value = float(port_data[self.entity_description.counter])
        current_timestamp = self.coordinator.data[TIMESTAMP]

        if (
            self._last_value is None
            or self._last_timestamp is None
            or current_value < self._last_value
        ):
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
