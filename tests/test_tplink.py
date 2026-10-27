"""Tests of the client of the TP-Link Easy Smart Switch."""

import aiohttp
import pytest
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.tplink_easysmartswitch.const import TIMESTAMP
from custom_components.tplink_easysmartswitch.tplink import (
    EasySwitch,
    TpLinkSwitchCannotConnectError,
    TpLinkSwitchInvalidAuthError,
    TpLinkSwitchNotLoggedInError,
    TpLinkSwitchParseError,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

URL = "http://192.168.1.2"

SYSTEM_INFO = """<html><head><title>System Info</title></head><body>
<script type="text/javascript">
var info_ds = {
descriStr:[
"TL-SG108E"
],
macStr:[
"50:C7:BF:00:00:01"
],
firmwareStr:[
"1.0.0 Build 20171214 Rel.70905"
],
hardwareStr:[
"TL-SG108E 3.0"
]
};
</script>
</body></html>"""

# Port statistics of most models: the values are in a script of the body
PORT_STATISTICS = """<html><head><title>Port Statistics</title></head><body>
<script type="text/javascript">
var max_port_num = 2;
var all_info = {
state:[1,0,0,0],
link_status:[6,0,0,0],
pkts:[10,1,20,2,30,3,40,4,0,0]
};
</script>
</body></html>"""

# Port statistics of the models declaring the port number in the head
PORT_STATISTICS_HEAD = """<html><head><title>Port Statistics</title>
<script type="text/javascript">
var max_port_num = 2;
</script>
</head><body>
<script type="text/javascript">
var tmp_info = "1 6 10 1 20 2 ";
var tmp_info2 = "0 0 30 3 40 4 ";
</script>
</body></html>"""

# Answer of the switch when not logged in, and of logon.cgi
LOGIN_PAGE = """<html><head><title>Login</title>
<script type="text/javascript">
var logonInfo = new Array(
{code},
0,0);
</script>
</head><body><form action="logon.cgi" method="post"></form></body></html>"""

EXPECTED_PORTS = {
    1: {
        "state": "Enabled",
        "link_status": "1000M Full",
        "TxGoodPkt": "10",
        "TxBadPkt": "1",
        "RxGoodPkt": "20",
        "RxBadPkt": "2",
    },
    2: {
        "state": "Disabled",
        "link_status": "Link Down",
        "TxGoodPkt": "30",
        "TxBadPkt": "3",
        "RxGoodPkt": "40",
        "RxBadPkt": "4",
    },
}


@pytest.fixture
def switch(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> EasySwitch:
    """Return a client of the switch with a mocked session."""
    return EasySwitch(
        "192.168.1.2", "admin", "secret", session=async_get_clientsession(hass)
    )


async def test_login(switch: EasySwitch, aioclient_mock: AiohttpClientMocker) -> None:
    """Test the credentials are posted to the switch."""
    aioclient_mock.post(f"{URL}/logon.cgi")
    assert await switch.login()
    assert aioclient_mock.mock_calls[0][2] == {
        "logon": "Login",
        "username": "admin",
        "password": "secret",
    }


async def test_update_informations(
    switch: EasySwitch, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the MAC address and versions of the switch."""
    aioclient_mock.get(f"{URL}/SystemInfoRpm.htm", text=SYSTEM_INFO)
    await switch.update_informations()
    assert switch.host == "192.168.1.2"
    assert switch.mac_address == "50:C7:BF:00:00:01"
    assert switch.firmware_version == "1.0.0 Build 20171214 Rel.70905"
    assert switch.hardware_version == "TL-SG108E 3.0"


@pytest.mark.parametrize("page", [PORT_STATISTICS, PORT_STATISTICS_HEAD])
async def test_get_data(
    switch: EasySwitch, aioclient_mock: AiohttpClientMocker, page: str
) -> None:
    """Test the port statistics of both page layouts."""
    aioclient_mock.get(f"{URL}/PortStatisticsRpm.htm", text=page)
    data = await switch.get_data()
    assert data.pop(TIMESTAMP)
    assert data == EXPECTED_PORTS
    assert switch.port_number == 2


@pytest.mark.parametrize("code", [None, 0])
async def test_login_accepted(
    switch: EasySwitch, aioclient_mock: AiohttpClientMocker, code: int | None
) -> None:
    """Test a login answer without logonInfo or with the code 0 is a success."""
    text = "<html></html>" if code is None else LOGIN_PAGE.format(code=code)
    aioclient_mock.post(f"{URL}/logon.cgi", text=text)
    assert await switch.login()


async def test_login_wrong_credentials(
    switch: EasySwitch, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the logonInfo code of wrong credentials is an authentication error."""
    aioclient_mock.post(f"{URL}/logon.cgi", text=LOGIN_PAGE.format(code=1))
    with pytest.raises(TpLinkSwitchInvalidAuthError):
        await switch.login()


async def test_login_refused(
    switch: EasySwitch, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the other logonInfo codes are a refused login, not an auth error."""
    aioclient_mock.post(f"{URL}/logon.cgi", text=LOGIN_PAGE.format(code=3))
    assert not await switch.login()


@pytest.mark.parametrize(
    ("status", "exception"),
    [
        (401, TpLinkSwitchInvalidAuthError),
        (403, TpLinkSwitchInvalidAuthError),
        (404, TpLinkSwitchCannotConnectError),
        (500, TpLinkSwitchCannotConnectError),
    ],
)
async def test_login_http_errors(
    switch: EasySwitch,
    aioclient_mock: AiohttpClientMocker,
    status: int,
    exception: type[Exception],
) -> None:
    """Test only 401 and 403 on logon.cgi are authentication errors."""
    aioclient_mock.post(f"{URL}/logon.cgi", status=status)
    with pytest.raises(exception):
        await switch.login()


@pytest.mark.parametrize(
    ("status", "exception"),
    [
        (401, TpLinkSwitchInvalidAuthError),
        (403, TpLinkSwitchInvalidAuthError),
        (404, TpLinkSwitchCannotConnectError),
        (500, TpLinkSwitchCannotConnectError),
        (503, TpLinkSwitchCannotConnectError),
    ],
)
async def test_page_http_errors(
    switch: EasySwitch,
    aioclient_mock: AiohttpClientMocker,
    status: int,
    exception: type[Exception],
) -> None:
    """Test only 401 and 403 on a page are authentication errors."""
    aioclient_mock.get(f"{URL}/PortStatisticsRpm.htm", status=status)
    with pytest.raises(exception):
        await switch.get_data()


async def test_not_logged_in(
    switch: EasySwitch, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the login page answered with a 200 status is detected."""
    aioclient_mock.get(f"{URL}/SystemInfoRpm.htm", text=LOGIN_PAGE.format(code=5))
    aioclient_mock.get(f"{URL}/PortStatisticsRpm.htm", text=LOGIN_PAGE.format(code=5))
    with pytest.raises(TpLinkSwitchNotLoggedInError):
        await switch.update_informations()
    with pytest.raises(TpLinkSwitchNotLoggedInError):
        await switch.get_data()


@pytest.mark.parametrize(
    "page",
    [
        # No values
        "<script>var max_port_num = 2;</script>",
        # Unknown port state
        PORT_STATISTICS.replace("state:[1,0,0,0]", "state:[9,0,0,0]"),
        # Missing port values
        PORT_STATISTICS.replace("var max_port_num = 2;", "var max_port_num = 8;"),
    ],
)
async def test_get_data_unexpected_page(
    switch: EasySwitch, aioclient_mock: AiohttpClientMocker, page: str
) -> None:
    """Test an unexpected port statistics page is a parsing error."""
    aioclient_mock.get(f"{URL}/PortStatisticsRpm.htm", text=page)
    with pytest.raises(TpLinkSwitchParseError):
        await switch.get_data()


@pytest.mark.parametrize(
    "page",
    [
        # The values are not in the first script
        "<script>var a = 1;</script><script>macStr:[\n]</script>",
        # Empty MAC address
        '<script>var info_ds = {\nmacStr:[\n""\n]\n};</script>',
    ],
)
async def test_update_informations_without_mac(
    switch: EasySwitch, aioclient_mock: AiohttpClientMocker, page: str
) -> None:
    """Test the MAC address is required."""
    aioclient_mock.get(f"{URL}/SystemInfoRpm.htm", text=page)
    with pytest.raises(TpLinkSwitchParseError):
        await switch.update_informations()
    assert switch.mac_address is None


@pytest.mark.parametrize("exception", [aiohttp.ClientError, TimeoutError])
async def test_connection_errors(
    switch: EasySwitch,
    aioclient_mock: AiohttpClientMocker,
    exception: type[Exception],
) -> None:
    """Test the connection errors and timeouts."""
    aioclient_mock.post(f"{URL}/logon.cgi", exc=exception())
    aioclient_mock.get(f"{URL}/SystemInfoRpm.htm", exc=exception())
    with pytest.raises(TpLinkSwitchCannotConnectError):
        await switch.login()
    with pytest.raises(TpLinkSwitchCannotConnectError):
        await switch.update_informations()
