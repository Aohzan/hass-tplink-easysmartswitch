"""Constant for the TP-Link Easy Smart Switch integration."""

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "tplink_easysmartswitch"

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]

DEFAULT_SCAN_INTERVAL = 30
DEFAULT_USERNAME = "admin"
# The switch allows a single web session: when another login takes it (most
# likely the web interface), wait this long before logging in again
LOGIN_GRACE_PERIOD = timedelta(minutes=5)

TIMESTAMP = "timestamp"

TPLINK_STATUS = {
    "0": "Link Down",
    "1": "Auto",
    "2": "10M Half",
    "3": "10M Full",
    "4": "100M Half",
    "5": "100M Full",
    "6": "1000M Full",
}
TPLINK_STATE = {"0": "Disabled", "1": "Enabled"}
# The switch counts the packets on 32 bits, and sends them as signed integers
TPLINK_COUNTER_MODULO = 1 << 32

TPLINK_PORT_STATE = "state"
TPLINK_PORT_LINK_STATUS = "link_status"
TPLINK_PORT_TX_GOOD_PKT = "TxGoodPkt"
TPLINK_PORT_TX_BAD_PKT = "TxBadPkt"
TPLINK_PORT_RX_GOOD_PKT = "RxGoodPkt"
TPLINK_PORT_RX_BAD_PKT = "RxBadPkt"
