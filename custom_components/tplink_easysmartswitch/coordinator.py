"""Data update coordinator of the TP-Link Easy Smart Switch integration."""

from collections.abc import Awaitable, Callable, Mapping
from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
from .tplink import (
    EasySwitch,
    TpLinkSwitchCannotConnectError,
    TpLinkSwitchInvalidAuthError,
    TpLinkSwitchNotLoggedInError,
    TpLinkSwitchParseError,
)

_LOGGER = logging.getLogger(__name__)

type TpLinkSwitchConfigEntry = ConfigEntry[TpLinkSwitchCoordinator]


class SessionLostError(UpdateFailed):
    """The switch answered its login page: the session expired or was taken."""


def create_switch(hass: HomeAssistant, config: Mapping[str, Any]) -> EasySwitch:
    """Return the client of the switch of the given connection settings."""
    return EasySwitch(
        config[CONF_HOST],
        config[CONF_USERNAME],
        config[CONF_PASSWORD],
        session=async_get_clientsession(hass, verify_ssl=False),
    )


class TpLinkSwitchCoordinator(DataUpdateCoordinator[dict[Any, Any]]):
    """Fetch the port statistics of a switch."""

    config_entry: TpLinkSwitchConfigEntry

    def __init__(self, hass: HomeAssistant, entry: TpLinkSwitchConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(
                seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
        )
        self.controller = create_switch(hass, entry.data)

    async def _async_setup(self) -> None:
        """Log in and read the MAC address and versions of the switch."""
        await self._async_login()
        await self._async_call(self.controller.update_informations)

    async def _async_update_data(self) -> dict[Any, Any]:
        """Fetch the statistics of all ports."""
        try:
            return await self._async_call(self.controller.get_data)
        except SessionLostError:
            # The session on the switch expired: log in again, once
            _LOGGER.debug("Session lost on %s, logging in", self.controller.host)
        await self._async_login()
        return await self._async_call(self.controller.get_data)

    async def _async_login(self) -> None:
        """Log in the switch."""
        if not await self._async_call(self.controller.login):
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="login_refused"
            )

    async def _async_call[T](self, method: Callable[[], Awaitable[T]]) -> T:
        """Call the switch, raising the Home Assistant exceptions."""
        try:
            return await method()
        except TpLinkSwitchInvalidAuthError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="invalid_auth"
            ) from err
        except TpLinkSwitchNotLoggedInError as err:
            raise SessionLostError(
                translation_domain=DOMAIN, translation_key="session_lost"
            ) from err
        except TpLinkSwitchCannotConnectError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"error": str(err)},
            ) from err
        except TpLinkSwitchParseError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_response",
                translation_placeholders={"error": str(err)},
            ) from err
