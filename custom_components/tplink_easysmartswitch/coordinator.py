"""Data update coordinator of the TP-Link Easy Smart Switch integration."""

from collections.abc import Awaitable, Callable, Mapping
from datetime import datetime, timedelta
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
from homeassistant.util import dt as dt_util

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, LOGIN_GRACE_PERIOD
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
        # Last time the session was known to be open: login or page read
        self._session_alive_at: datetime | None = None
        # No login before this time: the session is in use by another login
        self._login_after: datetime | None = None

    async def _async_setup(self) -> None:
        """Log in and read the MAC address and versions of the switch."""
        await self._async_login()
        await self._async_call(self.controller.update_informations)

    async def _async_update_data(self) -> dict[Any, Any]:
        """Fetch the statistics of all ports."""
        if self._login_after is not None:
            if dt_util.utcnow() < self._login_after:
                raise self._session_in_use_error(self._login_after)
            self._login_after = None
            await self._async_login()
        try:
            data = await self._async_call(self.controller.get_data)
        except SessionLostError as err:
            if (
                self._session_alive_at is not None
                and dt_util.utcnow() - self._session_alive_at < LOGIN_GRACE_PERIOD
            ):
                # The session was open a moment ago: another login took it,
                # most likely the web interface, that a new login would close
                raise self._session_in_use_error(self._wait_before_login()) from err
            # The session expired: log in again, once
            _LOGGER.debug("Session lost on %s, logging in", self.controller.host)
            await self._async_login()
            try:
                data = await self._async_call(self.controller.get_data)
            except SessionLostError as err_after_login:
                raise self._session_in_use_error(
                    self._wait_before_login()
                ) from err_after_login
        except UpdateFailed:
            # The switch may restart, closing the session: a lost session is
            # then not taken for another login
            self._session_alive_at = None
            raise
        self._session_alive_at = dt_util.utcnow()
        return data

    async def async_reboot(self) -> None:
        """Reboot the switch, taking its session if another login has it."""
        try:
            await self._async_call(self.controller.reboot)
        except SessionLostError:
            await self._async_login()
            await self._async_call(self.controller.reboot)
        # The reboot closes every session: the next update logs in again,
        # without taking the lost session for a login in the web interface
        self._session_alive_at = None
        self._login_after = None

    async def _async_login(self) -> None:
        """Log in the switch."""
        if not await self._async_call(self.controller.login):
            self._wait_before_login()
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="login_refused"
            )
        self._session_alive_at = dt_util.utcnow()

    def _wait_before_login(self) -> datetime:
        """Leave the session of the switch to the other login for a while."""
        self._login_after = dt_util.utcnow() + LOGIN_GRACE_PERIOD
        _LOGGER.debug(
            "Session of %s in use, no login before %s",
            self.controller.host,
            self._login_after,
        )
        return self._login_after

    @staticmethod
    def _session_in_use_error(login_after: datetime) -> UpdateFailed:
        """Return the error of an update skipped to leave the session."""
        return UpdateFailed(
            translation_domain=DOMAIN,
            translation_key="session_in_use",
            translation_placeholders={
                "time": dt_util.as_local(login_after).strftime("%H:%M:%S")
            },
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
