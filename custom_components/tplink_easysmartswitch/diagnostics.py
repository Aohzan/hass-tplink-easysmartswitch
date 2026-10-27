"""Diagnostics support for the TP-Link Easy Smart Switch integration."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .coordinator import TpLinkSwitchConfigEntry

TO_REDACT = {CONF_PASSWORD, CONF_USERNAME}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: TpLinkSwitchConfigEntry
) -> dict[str, Any]:
    """Return the diagnostics of a config entry."""
    coordinator = entry.runtime_data
    controller = coordinator.controller
    return {
        "entry": {
            "data": async_redact_data(entry.data, TO_REDACT),
            "options": dict(entry.options),
        },
        "device": {
            "hardware_version": controller.hardware_version,
            "firmware_version": controller.firmware_version,
            "port_number": controller.port_number,
        },
        "data": {str(key): value for key, value in coordinator.data.items()},
    }
