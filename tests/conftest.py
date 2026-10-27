"""Fixtures of the TP-Link Easy Smart Switch tests."""

from collections.abc import Generator
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.syrupy import HomeAssistantSnapshotExtension
from syrupy.assertion import SnapshotAssertion

from custom_components.tplink_easysmartswitch.const import DOMAIN, TIMESTAMP
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)

HOST = "192.168.1.2"
MAC = "50:C7:BF:00:00:01"
NOW = datetime(2026, 10, 27, 12, 0, tzinfo=UTC)

ENTRY_DATA = {
    CONF_HOST: HOST,
    CONF_USERNAME: "admin",
    CONF_PASSWORD: "secret",
}
ENTRY_OPTIONS = {CONF_SCAN_INTERVAL: 30}


def port_data(
    state: str = "Enabled",
    link_status: str = "1000M Full",
    tx_good: str = "1000",
    rx_good: str = "2000",
) -> dict[str, str]:
    """Return the values of a port, as returned by EasySwitch.get_data."""
    return {
        "state": state,
        "link_status": link_status,
        "TxGoodPkt": tx_good,
        "TxBadPkt": "1",
        "RxGoodPkt": rx_good,
        "RxBadPkt": "2",
    }


def switch_data(timestamp: datetime = NOW, **port_1: str) -> dict[int | str, Any]:
    """Return the data of a switch with 2 ports, the second one down."""
    return {
        TIMESTAMP: timestamp,
        1: port_data(**port_1),
        2: port_data(link_status="Link Down", tx_good="0", rx_good="0"),
    }


@pytest.fixture
def snapshot(snapshot: SnapshotAssertion) -> SnapshotAssertion:
    """Return the snapshot assertion with the Home Assistant serializer."""
    return snapshot.use_extension(HomeAssistantSnapshotExtension)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable the custom integrations in every test."""


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the config entry of a switch."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=f"Switch {HOST}",
        unique_id=f"{DOMAIN}_{HOST}",
        data=ENTRY_DATA,
        options=ENTRY_OPTIONS,
        version=2,
    )


@pytest.fixture
def mock_switch() -> Generator[MagicMock]:
    """Mock the client of the switch."""
    client = MagicMock()
    client.host = HOST
    client.mac_address = MAC
    client.hardware_version = "TL-SG108E 3.0"
    client.firmware_version = "1.0.0 Build 20171214 Rel.70905"
    client.port_number = 2
    client.login = AsyncMock(return_value=True)
    client.update_informations = AsyncMock()
    client.get_data = AsyncMock(return_value=switch_data())
    with patch(
        "custom_components.tplink_easysmartswitch.coordinator.EasySwitch",
        return_value=client,
    ) as switch_class:
        client.switch_class = switch_class
        yield client
