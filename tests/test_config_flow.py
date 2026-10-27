"""Tests of the config flow of the TP-Link Easy Smart Switch integration."""

from unittest.mock import MagicMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.tplink_easysmartswitch.const import DOMAIN
from custom_components.tplink_easysmartswitch.tplink import (
    TpLinkSwitchCannotConnectError,
    TpLinkSwitchInvalidAuthError,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import ENTRY_DATA, HOST

USER_INPUT = {
    CONF_HOST: HOST,
    CONF_USERNAME: "admin",
    CONF_PASSWORD: "secret",
    CONF_SCAN_INTERVAL: 10,
}


async def test_user_flow(hass: HomeAssistant, mock_switch: MagicMock) -> None:
    """Test the creation of an entry, the scan interval in the options."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Switch {HOST}"
    assert result["data"] == ENTRY_DATA
    assert result["options"] == {CONF_SCAN_INTERVAL: 10}
    assert result["result"].unique_id == f"{DOMAIN}_{HOST}"
    assert mock_switch.switch_class.call_args.args == (HOST, "admin", "secret")


async def test_user_flow_without_password(
    hass: HomeAssistant, mock_switch: MagicMock
) -> None:
    """Test the password is optional."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    # The frontend doesn't send the empty fields
    user_input = {k: v for k, v in USER_INPUT.items() if k != CONF_PASSWORD}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_PASSWORD] == ""


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (TpLinkSwitchCannotConnectError, "cannot_connect"),
        (TpLinkSwitchInvalidAuthError, "invalid_auth"),
        (RuntimeError, "unknown"),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant,
    mock_switch: MagicMock,
    exception: type[Exception],
    error: str,
) -> None:
    """Test the connection errors, and the recovery."""
    mock_switch.get_data.side_effect = exception
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_switch.get_data.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_switch: MagicMock,
) -> None:
    """Test a switch can only be configured once."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_switch: MagicMock,
) -> None:
    """Test the scan interval option updates the entry and reloads it."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["step_id"] == "init"
    assert list(result["data_schema"].schema) == [CONF_SCAN_INTERVAL]

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SCAN_INTERVAL: 60}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options == {CONF_SCAN_INTERVAL: 60}
    assert mock_config_entry.data == ENTRY_DATA
    # Reloaded with the new options
    assert mock_config_entry.runtime_data.update_interval.total_seconds() == 60


async def test_reauth_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_switch: MagicMock,
) -> None:
    """Test the new credentials are tested and stored in the data."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    assert result["description_placeholders"][CONF_HOST] == HOST

    mock_switch.get_data.side_effect = TpLinkSwitchInvalidAuthError
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: "admin", CONF_PASSWORD: "wrong"}
    )
    assert result["errors"] == {"base": "invalid_auth"}

    mock_switch.get_data.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: "root", CONF_PASSWORD: "new"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data == {
        CONF_HOST: HOST,
        CONF_USERNAME: "root",
        CONF_PASSWORD: "new",
    }


async def test_reconfigure_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_switch: MagicMock,
) -> None:
    """Test the address of the switch can be changed."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["step_id"] == "reconfigure"

    mock_switch.login.side_effect = TpLinkSwitchCannotConnectError
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.3"}
    )
    assert result["errors"] == {"base": "cannot_connect"}

    mock_switch.login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.3"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_HOST] == "192.168.1.3"
    assert mock_config_entry.data[CONF_PASSWORD] == "secret"
    assert mock_config_entry.unique_id == f"{DOMAIN}_192.168.1.3"


async def test_reconfigure_flow_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_switch: MagicMock,
) -> None:
    """Test the address of another configured switch is refused."""
    mock_config_entry.add_to_hass(hass)
    MockConfigEntry(
        domain=DOMAIN, unique_id=f"{DOMAIN}_192.168.1.3", data={}
    ).add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.3"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
