"""Tests of the entities of the TP-Link Easy Smart Switch integration."""

from datetime import timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import NOW, switch_data

INGRESS = "sensor.switch_192_168_1_2_port_01_ingress"


@pytest.mark.parametrize("platform", [Platform.BINARY_SENSOR, Platform.SENSOR])
async def test_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    mock_switch: MagicMock,
    platform: Platform,
) -> None:
    """Test the entities and their states."""
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            "custom_components.tplink_easysmartswitch.PLATFORMS", [platform]
        )
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_unique_ids(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_switch: MagicMock,
) -> None:
    """Test the unique IDs of the entities are the ones of the previous versions."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    unique_ids = {
        entity.unique_id
        for entity in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
    }
    prefix = "tplink_easysmartswitch_50_c7_bf_00_00_01"
    assert unique_ids == {
        f"{prefix}_binary_sensor_1",
        f"{prefix}_binary_sensor_2",
        f"{prefix}_speed_sensor_1_rxgoodpkt",
        f"{prefix}_speed_sensor_1_txgoodpkt",
        f"{prefix}_speed_sensor_2_rxgoodpkt",
        f"{prefix}_speed_sensor_2_txgoodpkt",
    }


async def test_speed(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_switch: MagicMock,
) -> None:
    """Test the speed is derived from the counters of two updates."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    # The first value is only the reference
    assert hass.states.get(INGRESS).state == STATE_UNKNOWN

    async def update(**port_1: str) -> None:
        freezer.tick(30)
        mock_switch.get_data.return_value = switch_data(
            timestamp=NOW + timedelta(seconds=update.seconds), **port_1
        )
        update.seconds += 30
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    update.seconds = 30

    await update(rx_good="2600")
    assert hass.states.get(INGRESS).state == "20.0"
    # Reading the state again keeps the value
    hass.states.async_remove(INGRESS)
    mock_config_entry.runtime_data.async_update_listeners()
    await hass.async_block_till_done()
    assert hass.states.get(INGRESS).state == "20.0"

    await update(rx_good="2900")
    assert hass.states.get(INGRESS).state == "10.0"

    # Counter reset by a restart of the switch
    await update(rx_good="100")
    assert hass.states.get(INGRESS).state == STATE_UNKNOWN

    await update(rx_good="400")
    assert hass.states.get(INGRESS).state == "10.0"


async def test_missing_port(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_switch: MagicMock,
) -> None:
    """Test the entities of a port missing from the data have no state."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    data = switch_data(timestamp=NOW + timedelta(seconds=30))
    del data[2]
    mock_switch.get_data.return_value = data
    freezer.tick(30)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (
        hass.states.get("sensor.switch_192_168_1_2_port_02_ingress").state
        == STATE_UNKNOWN
    )
    state = hass.states.get("binary_sensor.switch_192_168_1_2_port_02")
    assert state.state == STATE_UNKNOWN
    assert "link_status" not in state.attributes
