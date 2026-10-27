"""Config flow to configure the TP-Link Easy Smart Switch integration."""

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import DEFAULT_SCAN_INTERVAL, DEFAULT_USERNAME, DOMAIN
from .coordinator import TpLinkSwitchConfigEntry, create_switch
from .tplink import TpLinkSwitchCannotConnectError, TpLinkSwitchInvalidAuthError

_LOGGER = logging.getLogger(__name__)

USERNAME_SELECTOR = TextSelector(
    TextSelectorConfig(type=TextSelectorType.TEXT, autocomplete="username")
)
PASSWORD_SELECTOR = TextSelector(
    TextSelectorConfig(type=TextSelectorType.PASSWORD, autocomplete="current-password")
)
SCAN_INTERVAL_VALIDATOR = vol.All(int, vol.Range(min=1))

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME, default=DEFAULT_USERNAME): USERNAME_SELECTOR,
        vol.Optional(CONF_PASSWORD): PASSWORD_SELECTOR,
        vol.Required(
            CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
        ): SCAN_INTERVAL_VALIDATOR,
    }
)
CREDENTIALS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): USERNAME_SELECTOR,
        vol.Optional(CONF_PASSWORD): PASSWORD_SELECTOR,
    }
)
RECONFIGURE_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str})
OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(
            CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
        ): SCAN_INTERVAL_VALIDATOR,
    }
)


def _unique_id(host: str) -> str:
    """Return the unique ID of the config entry of a switch."""
    return f"{DOMAIN}_{host}"


class TpLinkSwitchConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a TP-Link Easy Smart Switch config flow."""

    VERSION = 2

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(_unique_id(user_input[CONF_HOST]))
            self._abort_if_unique_id_configured()

            data = {
                CONF_HOST: user_input[CONF_HOST],
                CONF_USERNAME: user_input[CONF_USERNAME],
                # The frontend doesn't send an empty password
                CONF_PASSWORD: user_input.get(CONF_PASSWORD, ""),
            }
            errors = await _test_connection(self.hass, data)
            if not errors:
                return self.async_create_entry(
                    title=f"Switch {user_input[CONF_HOST]}",
                    data=data,
                    options={CONF_SCAN_INTERVAL: user_input[CONF_SCAN_INTERVAL]},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, user_input),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle a rejected authentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for new credentials."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input.setdefault(CONF_PASSWORD, "")
            errors = await _test_connection(self.hass, {**entry.data, **user_input})
            if not errors:
                return self.async_update_reload_and_abort(
                    entry, data_updates=user_input
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self.add_suggested_values_to_schema(
                CREDENTIALS_SCHEMA,
                user_input or {CONF_USERNAME: entry.data[CONF_USERNAME]},
            ),
            errors=errors,
            description_placeholders={CONF_HOST: entry.data[CONF_HOST]},
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the address of the switch."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            unique_id = _unique_id(user_input[CONF_HOST])
            if unique_id != entry.unique_id:
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
            errors = await _test_connection(self.hass, {**entry.data, **user_input})
            if not errors:
                return self.async_update_reload_and_abort(
                    entry, unique_id=unique_id, data_updates=user_input
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                RECONFIGURE_SCHEMA, user_input or entry.data
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: TpLinkSwitchConfigEntry,
    ) -> TpLinkSwitchOptionsFlowHandler:
        """Define the config flow to handle options."""
        return TpLinkSwitchOptionsFlowHandler()


class TpLinkSwitchOptionsFlowHandler(OptionsFlowWithReload):
    """Handle a TP-Link Easy Smart Switch options flow."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA, self.config_entry.options
            ),
        )


async def _test_connection(
    hass: HomeAssistant, config: Mapping[str, Any]
) -> dict[str, str]:
    """Log in and read the switch, returning the errors of the form."""
    switch = create_switch(hass, config)
    try:
        await switch.login()
        await switch.get_data()
    except TpLinkSwitchInvalidAuthError:
        return {"base": "invalid_auth"}
    except TpLinkSwitchCannotConnectError:
        return {"base": "cannot_connect"}
    except Exception:
        _LOGGER.exception("Unexpected error while connecting to the switch")
        return {"base": "unknown"}
    return {}
