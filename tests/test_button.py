"""Tests of the reboot button of the TP-Link Easy Smart Switch integration."""

from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.tplink_easysmartswitch.tplink import (
    TpLinkSwitchCannotConnectError,
    TpLinkSwitchNotLoggedInError,
)
from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .test_init import next_update, setup_entry

RESTART = "button.switch_192_168_1_2_restart"


async def press(hass: HomeAssistant) -> None:
    """Press the reboot button."""
    await hass.services.async_call(
        BUTTON_DOMAIN, SERVICE_PRESS, {ATTR_ENTITY_ID: RESTART}, blocking=True
    )


async def test_reboot(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_switch: MagicMock,
) -> None:
    """Test the reboot, and the login right after the switch is back."""
    coordinator = await setup_entry(hass, mock_config_entry)

    await press(hass)
    mock_switch.reboot.assert_awaited_once()
    assert mock_switch.login.await_count == 1

    # The switch is back with its session lost: not taken for a login in the
    # web interface
    mock_switch.get_data.side_effect = [
        TpLinkSwitchNotLoggedInError,
        mock_switch.get_data.return_value,
    ]
    await next_update(hass, freezer)
    assert coordinator.last_update_success
    assert mock_switch.login.await_count == 2


async def test_reboot_session_lost(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_switch: MagicMock,
) -> None:
    """Test the reboot logs in when the session is lost."""
    await setup_entry(hass, mock_config_entry)
    mock_switch.reboot.side_effect = [TpLinkSwitchNotLoggedInError, None]

    await press(hass)
    assert mock_switch.reboot.await_count == 2
    assert mock_switch.login.await_count == 2


@pytest.mark.parametrize(
    "exception", [TpLinkSwitchCannotConnectError, TpLinkSwitchNotLoggedInError]
)
async def test_reboot_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_switch: MagicMock,
    exception: type[Exception],
) -> None:
    """Test a failed reboot raises an error."""
    await setup_entry(hass, mock_config_entry)
    mock_switch.reboot.side_effect = exception

    with pytest.raises(HomeAssistantError):
        await press(hass)
