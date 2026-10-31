"""TP-Link Easy Smart Switch integration."""

import logging

from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant

from .const import DEFAULT_SCAN_INTERVAL, DEFAULT_USERNAME, PLATFORMS
from .coordinator import TpLinkSwitchConfigEntry, TpLinkSwitchCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_migrate_entry(
    hass: HomeAssistant, entry: TpLinkSwitchConfigEntry
) -> bool:
    """Migrate an old config entry."""
    if entry.version == 1:
        # The options overrode the credentials and scan interval of the data:
        # the credentials move to the data, the scan interval to the options
        config = {**entry.data, **entry.options}
        hass.config_entries.async_update_entry(
            entry,
            data={
                CONF_HOST: config[CONF_HOST],
                CONF_USERNAME: config.get(CONF_USERNAME, DEFAULT_USERNAME),
                CONF_PASSWORD: config.get(CONF_PASSWORD) or "",
            },
            options={
                CONF_SCAN_INTERVAL: config.get(
                    CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                )
            },
            version=2,
        )
        _LOGGER.debug("Migration to version %s successful", entry.version)

    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: TpLinkSwitchConfigEntry
) -> bool:
    """Set up TP-Link Easy Smart Switch from a config entry."""
    coordinator = TpLinkSwitchCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: TpLinkSwitchConfigEntry
) -> bool:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
    return True
