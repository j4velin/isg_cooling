"""Parsing of the ISG pages (German and English) by IsgClient."""
import asyncio
import re

from conftest import read_fixture
from isg_cooling import isg_client
from isg_cooling.isg_client import (
    IsgClient,
    IsgConnectionError,
    _normalize_key,
    _parse_energy,
)


def client_for(page: str, login_marker: str = "angemeldet als") -> IsgClient:
    """client that gets `page` for every request, already logged in"""
    client = IsgClient(None, "isg.lan", "user", "secret", login_marker)
    client._logged_in = True

    async def fake_get(path):
        return page

    client._async_get = fake_get
    return client


def consumption(page: str):
    result = asyncio.run(client_for(page).async_get_cooling_consumption())
    return result.last_24h, result.last_12m, result.last_prev_12m


def test_parse_energy():
    assert _parse_energy("0,313MWh") == 313.0
    assert _parse_energy("1,216kWh") == 1.216
    assert _parse_energy("1.234,5kWh") == 1234.5
    assert _parse_energy("12.5 kWh") == 12.5
    assert _parse_energy("--") is None


def test_normalize_key():
    assert _normalize_key("KÜHLEN 1-24 h") == "KÜHLEN1-24H"
    assert _normalize_key("COOLING 1–24 h") == "COOLING1-24H"
    assert _normalize_key("LÜFTEN 1-24h") == "LÜFTEN1-24H"


def test_login_marker_detection():
    client = client_for("")
    assert client._is_logged_in(read_fixture("energy_de.html"))
    assert client._is_logged_in(read_fixture("energy_en.html"))
    assert client._is_logged_in(read_fixture("cooling_en.html"))
    assert not client._is_logged_in("<form>User name: Password:</form>")
    # a configured marker for another language
    other = client_for("", "connecté en tant que")
    assert other._is_logged_in("Vous êtes connecté en tant que")


def test_consumption_german():
    assert consumption(read_fixture("energy_de.html")) == (0.0, 313.0, 26.0)


def test_consumption_english():
    page = read_fixture("energy_en.html")
    assert "COOLING 1–24 h" in page  # the English page uses en-dashes
    assert consumption(page) == (0.0, 313.0, 26.0)


def test_consumption_german_alternative_title():
    page = read_fixture("energy_de.html").replace("LEISTUNGSAUFNAHME", "STROMVERBRAUCH")
    assert consumption(page) == (0.0, 313.0, 26.0)


def test_consumption_without_cooling_rows():
    # INFO > HEAT PUMP also has a POWER CONSUMPTION table, without cooling rows
    assert consumption(read_fixture("heat_pump_en.html")) == (None, None, None)
    page = re.sub(
        r'<tr[^>]*>\s*<td class="key">KÜHLEN[^<]*</td>\s*<td[^>]*>[^<]*</td>\s*</tr>',
        "",
        read_fixture("energy_de.html"),
    )
    assert consumption(page) == (None, None, None)


def test_consumption_table_missing():
    try:
        consumption("<html>Sie sind angemeldet als: user, but no tables</html>")
    except IsgConnectionError:
        return
    raise AssertionError("expected IsgConnectionError")


def test_cooling_form_english():
    state = asyncio.run(client_for(read_fixture("cooling_en.html"))._async_get_cooling_form())
    assert state.cooling_on is False
    assert state.fields == {"val73": "0", "val189": "0", "val103": "18,0", "val107": "1,0"}


def test_relogin_once_on_logged_out_page():
    logins = []
    client = client_for("<html>Login</html>")

    async def fake_login():
        logins.append(1)

    client.async_login = fake_login
    try:
        asyncio.run(client.async_get_cooling_consumption())
    except IsgConnectionError:
        pass
    assert len(logins) == 1

    logins.clear()
    client._async_get = client_for(read_fixture("energy_en.html"))._async_get
    asyncio.run(client.async_get_cooling_consumption())
    assert logins == []


def test_no_relogin_without_credentials():
    gets = []
    client = IsgClient(None, "isg.lan", "", "")

    async def fake_get(path):
        gets.append(path)
        return read_fixture("energy_de.html").replace("angemeldet als", "")

    client._async_get = fake_get
    assert asyncio.run(client.async_get_cooling_consumption()).last_12m == 313.0
    assert len(gets) == 1


def test_jsvalues_pattern_is_not_greedy():
    page = read_fixture("cooling_en.html").replace(
        "jsvalues['103']['val']='18,0';",
        "jsvalues['103']['val']='18,0'; jsvalues['999']['val']='x';",
    )
    state = asyncio.run(client_for(page)._async_get_cooling_form())
    assert state.fields["val103"] == "18,0"


def test_save_answer():
    isg_client._check_save_answer('{"success":true}')
    isg_client._check_save_answer('{"warning":true,"message":"ok"}')
    for answer in ('{"success":false,"errors":{"103":"out of range"}}', "<html>Login</html>", "[]"):
        try:
            isg_client._check_save_answer(answer)
        except IsgConnectionError:
            continue
        raise AssertionError(f"expected IsgConnectionError for {answer!r}")
