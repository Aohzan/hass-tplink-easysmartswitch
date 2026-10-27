"""Config flow to configure the TP-Link Easy Smart Switch integration."""

from collections.abc import Mapping
import logging
from typing import Any

import probatio

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
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import DEFAULT_SCAN_INTERVAL, DEFAULT_USERNAME, DOMAIN
from .coordinator import TpLinkSwitchConfigEntry, create_switch
from .tplink import (
    TpLinkSwitchCannotConnectError,
    TpLinkSwitchInvalidAuthError,
    TpLinkSwitchNotLoggedInError,
    TpLinkSwitchParseError,
)

_LOGGER = logging.getLogger(__name__)

USERNAME_SELECTOR = TextSelector(
    TextSelectorConfig(type=TextSelectorType.TEXT, autocomplete="username")
)
PASSWORD_SELECTOR = TextSelector(
    TextSelectorConfig(type=TextSelectorType.PASSWORD, autocomplete="current-password")
)
SCAN_INTERVAL_VALIDATOR = probatio.All(int, probatio.Range(min=1))

USER_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): str,
        probatio.Required(CONF_USERNAME, default=DEFAULT_USERNAME): USERNAME_SELECTOR,
        probatio.Optional(CONF_PASSWORD): PASSWORD_SELECTOR,
        probatio.Required(
            CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
        ): SCAN_INTERVAL_VALIDATOR,
    }
)
CREDENTIALS_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_USERNAME): USERNAME_SELECTOR,
        probatio.Optional(CONF_PASSWORD): PASSWORD_SELECTOR,
    }
)
RECONFIGURE_SCHEMA = probatio.Schema({probatio.Required(CONF_HOST): str})
OPTIONS_SCHEMA = probatio.Schema(
    {
        probatio.Required(
            CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
        ): SCAN_INTERVAL_VALIDATOR,
    }
)


def _unique_id(host: str) -> str:
    """Return the unique ID of the config entry of a switch."""
    return f"{DOMAIN}_{host}"


def _default_title(host: str) -> str:
    """Return the default title of the config entry of a switch."""
    return f"Switch {host}"


def _configured_mac(hass: HomeAssistant, entry: TpLinkSwitchConfigEntry) -> str | None:
    """Return the MAC address of the device of a config entry, if set up once."""
    for device in dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id):
        for domain, identifier in device.identifiers:
            if domain == DOMAIN:
                return identifier
    return None


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
            errors, _ = await _test_connection(self.hass, data)
            if not errors:
                return self.async_create_entry(
                    title=_default_title(user_input[CONF_HOST]),
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
            errors, _ = await _test_connection(self.hass, {**entry.data, **user_input})
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
            errors, mac = await _test_connection(
                self.hass, {**entry.data, **user_input}
            )
            if not errors:
                # The unique ID is the address: compare the MAC addresses, so
                # the entities of another switch don't replace these ones
                configured_mac = _configured_mac(self.hass, entry)
                if configured_mac and (
                    mac is None or format_mac(mac) != format_mac(configured_mac)
                ):
                    return self.async_abort(reason="wrong_device")
                title = entry.title
                if title == _default_title(entry.data[CONF_HOST]):
                    title = _default_title(user_input[CONF_HOST])
                return self.async_update_reload_and_abort(
                    entry, unique_id=unique_id, title=title, data_updates=user_input
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
) -> tuple[dict[str, str], str | None]:
    """Log in and read the switch, returning the errors of the form and its MAC."""
    switch = create_switch(hass, config)
    try:
        if not await switch.login():
            return {"base": "login_refused"}, None
        await switch.update_informations()
        await switch.get_data()
    except TpLinkSwitchInvalidAuthError:
        return {"base": "invalid_auth"}, None
    except TpLinkSwitchNotLoggedInError:
        return {"base": "not_logged_in"}, None
    except TpLinkSwitchCannotConnectError:
        return {"base": "cannot_connect"}, None
    except TpLinkSwitchParseError:
        _LOGGER.exception("Unexpected answer of the switch")
        return {"base": "invalid_response"}, None
    except Exception:
        _LOGGER.exception("Unexpected error while connecting to the switch")
        return {"base": "unknown"}, None
    return {}, switch.mac_address
