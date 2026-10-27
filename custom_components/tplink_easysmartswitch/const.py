"""Constant for the TP-Link Easy Smart Switch integration."""

from homeassistant.const import Platform

DOMAIN = "tplink_easysmartswitch"

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]

DEFAULT_SCAN_INTERVAL = 30
DEFAULT_USERNAME = "admin"

TIMESTAMP = "timestamp"

TPLINK_STATUS = {
    "0": "Link Down",
    "1": "LS 1",
    "2": "10M Half",
    "3": "10M Full",
    "4": "LS 4",
    "5": "100M Full",
    "6": "1000M Full",
}
TPLINK_STATE = {"0": "Disabled", "1": "Enabled"}

TPLINK_PORT_STATE = "state"
TPLINK_PORT_LINK_STATUS = "link_status"
TPLINK_PORT_TX_GOOD_PKT = "TxGoodPkt"
TPLINK_PORT_TX_BAD_PKT = "TxBadPkt"
TPLINK_PORT_RX_GOOD_PKT = "RxGoodPkt"
TPLINK_PORT_RX_BAD_PKT = "RxBadPkt"
