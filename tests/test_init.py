"""Tests of the setup of the TP-Link Easy Smart Switch integration."""

from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.tplink_easysmartswitch.const import DOMAIN
from custom_components.tplink_easysmartswitch.tplink import (
    TpLinkSwitchCannotConnectError,
    TpLinkSwitchInvalidAuthError,
)
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant

from .conftest import HOST


async def test_setup_and_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_switch: MagicMock,
) -> None:
    """Test the setup and unload of an entry."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_switch.login.assert_awaited_once()
    mock_switch.update_informations.assert_awaited_once()
    assert mock_config_entry.runtime_data.update_interval.total_seconds() == 30

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize("method", ["login", "update_informations", "get_data"])
async def test_setup_cannot_connect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_switch: MagicMock,
    method: str,
) -> None:
    """Test the setup is retried when the switch is unreachable."""
    getattr(mock_switch, method).side_effect = TpLinkSwitchCannotConnectError
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_invalid_auth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_switch: MagicMock,
) -> None:
    """Test a rejected authentication starts a reauth flow."""
    mock_switch.update_informations.side_effect = TpLinkSwitchInvalidAuthError
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert [flow["context"]["source"] for flow in flows] == [SOURCE_REAUTH]


async def test_expired_session(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_switch: MagicMock,
) -> None:
    """Test an expired session logs in again, once."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    coordinator = mock_config_entry.runtime_data

    # The session expired: logged in again
    mock_switch.get_data.side_effect = [
        TpLinkSwitchInvalidAuthError,
        mock_switch.get_data.return_value,
    ]
    freezer.tick(30)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert mock_switch.login.await_count == 2
    assert coordinator.last_update_success

    # Still rejected after logging in: new credentials are needed
    mock_switch.get_data.side_effect = TpLinkSwitchInvalidAuthError
    freezer.tick(30)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert mock_switch.login.await_count == 3
    assert not coordinator.last_update_success
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert [flow["context"]["source"] for flow in flows] == [SOURCE_REAUTH]


async def test_update_cannot_connect(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_switch: MagicMock,
) -> None:
    """Test the entities are unavailable while the switch is unreachable."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_switch.get_data.side_effect = TpLinkSwitchCannotConnectError("timeout")
    freezer.tick(30)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert not mock_config_entry.runtime_data.last_update_success
    assert hass.states.get("binary_sensor.switch_192_168_1_2_port_01").state == (
        "unavailable"
    )


@pytest.mark.parametrize(
    ("data", "options"),
    [
        # Credentials changed in the options
        (
            {
                CONF_HOST: HOST,
                CONF_USERNAME: "admin",
                CONF_PASSWORD: "old",
                CONF_SCAN_INTERVAL: 10,
            },
            {CONF_USERNAME: "root", CONF_PASSWORD: "secret", CONF_SCAN_INTERVAL: 20},
        ),
        # No options, and no password
        ({CONF_HOST: HOST, CONF_USERNAME: "root", CONF_SCAN_INTERVAL: 20}, {}),
    ],
)
async def test_migrate_from_version_1(
    hass: HomeAssistant,
    mock_switch: MagicMock,
    data: dict,
    options: dict,
) -> None:
    """Test the credentials move to the data and the scan interval to the options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"{DOMAIN}_{HOST}",
        data=data,
        options=options,
        version=1,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.version == 2
    assert entry.data == {
        CONF_HOST: HOST,
        CONF_USERNAME: "root",
        CONF_PASSWORD: options.get(CONF_PASSWORD, ""),
    }
    assert entry.options == {CONF_SCAN_INTERVAL: 20}
