"""TP-Link Easy Smart Switch integration."""
import asyncio
from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONTROLLER, COORDINATOR, DOMAIN, PLATFORMS, UNDO_UPDATE_LISTENER
from .tplink import (
    EasySwitch,
    TpLinkSwitchCannotConnectError,
    TpLinkSwitchInvalidAuthError,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the TP-Link Easy Smart Switch integration."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up TP-Link Easy Smart Switch from a config entry."""
    config = entry.data
    options = entry.options

    scan_interval = options.get(CONF_SCAN_INTERVAL, config.get(CONF_SCAN_INTERVAL))
    username = options.get(CONF_USERNAME, config.get(CONF_USERNAME))
    password = options.get(CONF_PASSWORD, config.get(CONF_PASSWORD))

    session = async_get_clientsession(hass, False)

    controller = EasySwitch(
        host=config[CONF_HOST],
        user=username,
        password=password,
        session=session,
    )

    try:
        await controller.login()
    except TpLinkSwitchInvalidAuthError as error:
        raise Exception("Authentication error on TP-Link Easy Smart Switch") from error
    except TpLinkSwitchCannotConnectError as error:
        raise ConfigEntryNotReady from error

    async def async_update_data():
        """Fetch data."""
        try:
            return await controller.get_data()
        except TpLinkSwitchInvalidAuthError as err:
            raise UpdateFailed(
                "Authentication error on TP-Link Easy Smart Switch"
            ) from err
        except TpLinkSwitchCannotConnectError as err:
            raise UpdateFailed(f"Failed to communicating with API: {err}") from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=async_update_data,
        update_interval=timedelta(seconds=scan_interval),
    )

    await coordinator.async_refresh()

    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    await controller.update_informations()

    undo_listener = entry.add_update_listener(_async_update_listener)
    hass.data[DOMAIN][entry.entry_id] = {
        CONTROLLER: controller,
        COORDINATOR: coordinator,
        UNDO_UPDATE_LISTENER: undo_listener,
    }

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, controller.mac_address)},
        manufacturer="TP-Link",
        model=controller.hardware_version,
        default_name=f"Switch {controller.host}",
        sw_version=controller.firmware_version,
        connections={(dr.CONNECTION_NETWORK_MAC, controller.mac_address)},
        configuration_url=f"http://{config[CONF_HOST]}",
    )

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *(
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            )
        )
    )

    hass.data[DOMAIN][entry.entry_id][UNDO_UPDATE_LISTENER]()

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
