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
    TpLinkSwitchNotLoggedInError,
    TpLinkSwitchParseError,
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

    # The switch answered its login page: logged in again
    mock_switch.get_data.side_effect = [
        TpLinkSwitchNotLoggedInError,
        mock_switch.get_data.return_value,
    ]
    freezer.tick(30)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert mock_switch.login.await_count == 2
    assert coordinator.last_update_success

    # Logging in doesn't open a session: no reauth, the polling continues
    mock_switch.get_data.side_effect = TpLinkSwitchNotLoggedInError
    freezer.tick(30)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert mock_switch.login.await_count == 3
    assert not coordinator.last_update_success
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)


async def test_update_invalid_auth(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_switch: MagicMock,
) -> None:
    """Test rejected credentials while polling start a reauth flow."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_switch.get_data.side_effect = TpLinkSwitchNotLoggedInError
    mock_switch.login.side_effect = TpLinkSwitchInvalidAuthError
    freezer.tick(30)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert not mock_config_entry.runtime_data.last_update_success
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert [flow["context"]["source"] for flow in flows] == [SOURCE_REAUTH]


async def test_login_refused(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_switch: MagicMock,
) -> None:
    """Test a login refused for another reason than the credentials is retried."""
    mock_switch.login.return_value = False
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_switch.update_informations.assert_not_awaited()
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)


@pytest.mark.parametrize(
    "exception",
    [TpLinkSwitchCannotConnectError("HTTP error 500"), TpLinkSwitchParseError],
)
async def test_update_failed(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_switch: MagicMock,
    exception: Exception,
) -> None:
    """Test the entities are unavailable on an error, and the polling continues."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    coordinator = mock_config_entry.runtime_data

    mock_switch.get_data.side_effect = exception
    freezer.tick(30)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert not coordinator.last_update_success
    assert hass.states.get("binary_sensor.switch_192_168_1_2_port_01").state == (
        "unavailable"
    )
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)

    mock_switch.get_data.side_effect = None
    freezer.tick(30)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert coordinator.last_update_success
    assert hass.states.get("binary_sensor.switch_192_168_1_2_port_01").state == "on"
    mock_switch.login.assert_awaited_once()


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
