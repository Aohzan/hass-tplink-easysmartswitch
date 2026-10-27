"""Query the TP-Link Easy Smart Switch."""

import logging
import re
import socket

import aiohttp
from bs4 import BeautifulSoup

from homeassistant.util.dt import utcnow

from .const import (
    TIMESTAMP,
    TPLINK_PORT_LINK_STATUS,
    TPLINK_PORT_RX_BAD_PKT,
    TPLINK_PORT_RX_GOOD_PKT,
    TPLINK_PORT_STATE,
    TPLINK_PORT_TX_BAD_PKT,
    TPLINK_PORT_TX_GOOD_PKT,
    TPLINK_STATE,
    TPLINK_STATUS,
)

_LOGGER = logging.getLogger(__name__)

# HTTP statuses of a rejected authentication
AUTH_ERROR_STATUSES = (401, 403)
# First value of logonInfo in the answer of logon.cgi: 0 is a successful login
LOGON_INFO = re.compile(r"logonInfo\s*=\s*new Array\(\s*(\d+)")
LOGON_WRONG_CREDENTIALS = 1


class EasySwitch:
    """Represent a TP-Link Easy Smart Switch."""

    def __init__(
        self,
        host: str,
        user: str,
        password: str,
        request_timeout: int = 10,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        """Init a switch."""
        self._host = host
        self._mac_address: str | None = None
        self._firmware_version: str | None = None
        self._hardware_version: str | None = None
        self._ports_count = 0
        self._url = f"http://{host}"
        self._user = user
        self._password = password

        self._timeout = aiohttp.ClientTimeout(total=request_timeout)
        self._session = session
        self._close_session = False

    @property
    def host(self) -> str:
        """Switch's host."""
        return self._host

    @property
    def mac_address(self) -> str | None:
        """Switch's mac address."""
        return self._mac_address

    @property
    def hardware_version(self) -> str | None:
        """Switch's hardware version."""
        return self._hardware_version

    @property
    def firmware_version(self) -> str | None:
        """Switch's firmware version."""
        return self._firmware_version

    @property
    def port_number(self) -> int:
        """Switch's ports number."""
        return self._ports_count

    async def login(self) -> bool:
        """Log on the switch.

        Return False when the switch refuses the login for another reason than
        the credentials, e.g. the maximum number of sessions.
        """
        if self._session is None:
            self._session = aiohttp.ClientSession()
            self._close_session = True

        data = {"logon": "Login", "username": self._user, "password": self._password}
        headers = {"Referer": f"{self._url}/Logout.htm"}

        try:
            async with self._session.post(
                f"{self._url}/logon.cgi",
                data=data,
                headers=headers,
                timeout=self._timeout,
            ) as response:
                # The switch answers 401 even to a successful login: only the
                # logonInfo code of the answer tells whether it was accepted
                if response.status >= 400 and response.status not in (401, 403):
                    raise TpLinkSwitchCannotConnectError(
                        f"HTTP error {response.status}"
                    )
                text = await response.text(errors="replace")
        except TimeoutError as exception:
            raise TpLinkSwitchCannotConnectError("Timeout error") from exception
        except (aiohttp.ClientError, socket.gaierror) as exception:
            raise TpLinkSwitchCannotConnectError(exception) from exception

        if (match := LOGON_INFO.search(text)) is None:
            return True
        code = int(match.group(1))
        if code == LOGON_WRONG_CREDENTIALS:
            raise TpLinkSwitchInvalidAuthError("Wrong user name or password")
        if code:
            _LOGGER.debug("%s refused the login with the code %s", self._host, code)
            return False
        return True

    async def _get_page(self, page: str, marker: str) -> BeautifulSoup:
        """Get a page of the switch, logged in.

        The switch answers its login page, with a 200 status, when the session
        expired or was taken by another login: the page must contain the marker.
        """
        headers = {
            "Referer": f"{self._url}/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Upgrade-Insecure-Requests": "1",
        }
        try:
            async with self._session.get(  # type: ignore[union-attr]
                f"{self._url}/{page}", headers=headers, timeout=self._timeout
            ) as response:
                if response.status in AUTH_ERROR_STATUSES:
                    raise TpLinkSwitchInvalidAuthError(f"HTTP error {response.status}")
                if response.status != 200:
                    raise TpLinkSwitchCannotConnectError(
                        f"HTTP error {response.status}"
                    )
                text = await response.text()
        except TimeoutError as exception:
            raise TpLinkSwitchCannotConnectError("Timeout error") from exception
        except (aiohttp.ClientError, socket.gaierror) as exception:
            raise TpLinkSwitchCannotConnectError(exception) from exception
        if marker not in text:
            raise TpLinkSwitchNotLoggedInError(f"No {marker} in {page}")
        return BeautifulSoup(text, "html.parser")

    async def update_informations(self) -> None:
        """Get switch information."""
        soup = await self._get_page("SystemInfoRpm.htm", "macStr")

        mac_address = firmware_version = hardware_version = None
        try:
            infos = str(soup.script.string).split("\n")  # type: ignore[union-attr]
            for idx, element in enumerate(infos):
                if "macStr" in element:
                    mac_address = infos[idx + 1].replace('"', "")
                elif "firmwareStr" in element:
                    firmware_version = infos[idx + 1].replace('"', "")
                elif "hardwareStr" in element:
                    hardware_version = infos[idx + 1].replace('"', "")
        except (AttributeError, IndexError) as exception:
            raise TpLinkSwitchParseError(
                f"Unexpected system information: {exception!r}"
            ) from exception
        if not mac_address:
            # The MAC address identifies the device and its entities
            raise TpLinkSwitchParseError("No MAC address in the system information")
        self._mac_address = mac_address
        self._firmware_version = firmware_version
        self._hardware_version = hardware_version

    async def get_data(self) -> dict:
        """Get all ports data."""
        soup = await self._get_page("PortStatisticsRpm.htm", "max_port_num")
        try:
            return self._parse_port_statistics(soup)
        except (AttributeError, IndexError, KeyError, TypeError, ValueError) as err:
            raise TpLinkSwitchParseError(
                f"Unexpected port statistics: {err!r}"
            ) from err

    def _parse_port_statistics(self, soup: BeautifulSoup) -> dict:
        """Return the data of all ports from their statistics page."""
        convoluted = soup.script == soup.head.script

        pattern = re.compile(r"var (max_port_num) = (.*?);$", re.MULTILINE)

        if convoluted:
            port_number = int(
                pattern.search(str(soup.head.find_all("script"))).group(2)  # type: ignore
            )
        else:
            port_number = int(pattern.search(str(soup.script)).group(2))  # type: ignore
        self._ports_count = port_number

        if convoluted:
            i1 = (
                re.compile(r'tmp_info = "(.*?)";$', re.MULTILINE | re.DOTALL)  # type: ignore
                .search(str(soup.body.script))
                .group(1)
            )
            i2 = (
                re.compile(r'tmp_info2 = "(.*?)";$', re.MULTILINE | re.DOTALL)  # type: ignore
                .search(str(soup.body.script))
                .group(1)
            )
            # We simulate bug for bug the way the variables are loaded on the "normal" switch models. In those, each
            # data array has two extra 0 cells at the end. To remain compatible with the balance of the code here,
            # we need to add in these redundant entries so they can be removed later. (smh)
            script_vars = (
                "tmp_info:[" + i1.rstrip() + " " + i2.rstrip() + ",0,0]"
            ).replace(" ", ",")
        else:
            script_vars = (
                re.compile(r"var all_info = {\n?(.*?)\n?};$", re.MULTILINE | re.DOTALL)  # type: ignore
                .search(str(soup.script))
                .group(1)
            )

        entries = re.split(",?\n+", script_vars)

        edict = {}
        drop2 = re.compile(r"\[(.*),0,0]")
        for entry in entries:
            e2 = re.split(":", entry)
            edict[str(e2[0])] = drop2.search(e2[1]).group(1)  # type: ignore

        if convoluted:
            e3 = {}
            e4 = {}
            e5 = {}
            ee = re.split(",", edict["tmp_info"])
            for port in range(port_number):
                e3[port] = ee[(port * 6)]
                e4[port] = ee[(port * 6) + 1]
                e5[(port * 4)] = ee[(port * 6) + 2]
                e5[(port * 4) + 1] = ee[(port * 6) + 3]
                e5[(port * 4) + 2] = ee[(port * 6) + 4]
                e5[(port * 4) + 3] = ee[(port * 6) + 5]
        else:
            e3 = re.split(",", edict["state"])  # type: ignore
            e4 = re.split(",", edict["link_status"])  # type: ignore
            e5 = re.split(",", edict["pkts"])  # type: ignore

        states = {TIMESTAMP: utcnow()}
        for port in range(1, port_number + 1):
            states[port] = {  # type: ignore
                TPLINK_PORT_STATE: TPLINK_STATE[e3[port - 1]],
                TPLINK_PORT_LINK_STATUS: TPLINK_STATUS[e4[port - 1]],
                TPLINK_PORT_TX_GOOD_PKT: e5[((port - 1) * 4)],
                TPLINK_PORT_TX_BAD_PKT: e5[((port - 1) * 4) + 1],
                TPLINK_PORT_RX_GOOD_PKT: e5[((port - 1) * 4) + 2],
                TPLINK_PORT_RX_BAD_PKT: e5[((port - 1) * 4) + 3],
            }
        return states

    async def close(self) -> None:
        """Close open client session."""
        if self._session and self._close_session:
            await self._session.close()

    async def __aenter__(self):
        """Async enter."""
        return self

    async def __aexit__(self, *_exc_info) -> None:
        """Async exit."""
        await self.close()


class TpLinkSwitchError(Exception):
    """Base exception of the switch client."""


class TpLinkSwitchCannotConnectError(TpLinkSwitchError):
    """Exception to indicate an error in connection."""


class TpLinkSwitchInvalidAuthError(TpLinkSwitchError):
    """Exception to indicate an error in authentication."""


class TpLinkSwitchNotLoggedInError(TpLinkSwitchError):
    """Exception to indicate the switch answered its login page."""


class TpLinkSwitchParseError(TpLinkSwitchError):
    """Exception to indicate an unexpected page content."""
