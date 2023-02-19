"""Config flow to configure the TP-Link Easy Smart Switch integration."""
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigFlow,
    CONN_CLASS_LOCAL_POLL,
    HANDLERS,
    OptionsFlow,
    ConfigEntry,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
from .tplink import (
    EasySwitch,
    TpLinkSwitchCannotConnectError,
    TpLinkSwitchInvalidAuthError,
)

BASE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_USERNAME, default="admin"): str,
        vol.Optional(CONF_PASSWORD): str,
        vol.Required(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): int,
    }
)


@HANDLERS.register(DOMAIN)
class TpLinkSwitchConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a TP-Link Easy Smart Switch config flow."""

    VERSION = 1
    CONNECTION_CLASS = CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=BASE_SCHEMA, errors=errors
            )

        entry = await self.async_set_unique_id(
            "_".join([DOMAIN, user_input[CONF_HOST]])
        )

        if entry:
            self._abort_if_unique_id_configured()

        session = async_get_clientsession(self.hass, False)

        switch = EasySwitch(
            user_input[CONF_HOST],
            user_input[CONF_USERNAME],
            user_input[CONF_PASSWORD],
            session=session,
        )

        try:
            await switch.login()
            await switch.get_data()
            return self.async_create_entry(
                title=f"Switch {user_input[CONF_HOST]}",
                data=user_input,
            )
        except TpLinkSwitchInvalidAuthError:
            errors["base"] = "invalid_auth"
        except TpLinkSwitchCannotConnectError:
            errors["base"] = "connect_error"
        return self.async_show_form(
            step_id="user", data_schema=BASE_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Define the config flow to handle options."""
        return TpLinkSwitchOptionsFlowHandler(config_entry)


class TpLinkSwitchOptionsFlowHandler(OptionsFlow):
    """Handle a TpLinkSwitch options flow."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input) -> FlowResult:
        """Manage the options."""
        errors = {}
        if user_input is None:
            config = self.config_entry.data
            options = self.config_entry.options

            scan_interval = options.get(
                CONF_SCAN_INTERVAL, config.get(CONF_SCAN_INTERVAL)
            )
            username = options.get(CONF_USERNAME, config.get(CONF_USERNAME))
            password = options.get(CONF_PASSWORD, config.get(CONF_PASSWORD))

            options_schema = {
                vol.Optional(CONF_USERNAME, default=username): str,
                vol.Optional(CONF_PASSWORD, default=password): str,
                vol.Required(CONF_SCAN_INTERVAL, default=scan_interval): int,
            }

            return self.async_show_form(
                step_id="init", data_schema=vol.Schema(options_schema), errors=errors
            )

        session = async_get_clientsession(self.hass, False)
        switch = EasySwitch(
            self.config_entry.data[CONF_HOST],
            user_input[CONF_USERNAME],
            user_input[CONF_PASSWORD],
            session=session,
        )
        try:
            await switch.login()
            await switch.get_data()
            return self.async_create_entry(
                title=f"Switch {self.config_entry.data[CONF_HOST]}",
                data=user_input,
            )
        except TpLinkSwitchInvalidAuthError:
            errors["base"] = "invalid_auth"
        except TpLinkSwitchCannotConnectError:
            errors["base"] = "connect_error"
        return self.async_show_form(
            step_id="init", data_schema=BASE_SCHEMA, errors=errors
        )
