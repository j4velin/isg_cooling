"""MAC address (PROFIL > NETZWERK) and host of the ISG, which identify it."""
import asyncio

from conftest import read_fixture
from isg_cooling.isg_client import IsgClient, _find_mac, is_mac, normalize_host


def test_mac_from_the_network_page():
    client = IsgClient(None, "isg.lan", "user", "secret")
    client._logged_in = True

    async def fake_get(path):
        assert path == "?s=5,0"
        return read_fixture("network_en.html")

    client._async_get = fake_get
    assert asyncio.run(client.async_get_mac()) == "00:1a:2b:3c:4d:5e"


def test_find_mac():
    assert _find_mac("MAC <div>00-1A-2B-3C-4D-5E</div>") == "00:1a:2b:3c:4d:5e"
    assert _find_mac(read_fixture("energy_en.html")) is None
    # longer hex sequences are no MAC address
    assert _find_mac("00:1a:2b:3c:4d:5e:6f") is None


def test_is_mac():
    assert is_mac("00:1a:2b:3c:4d:5e")
    assert not is_mac("isg.lan")
    assert not is_mac("192.168.1.50")
    assert not is_mac("isg.lan:8080")
    assert not is_mac(None)
    assert is_mac("00-1a-2b-3c-4d-5e")
    # one separator throughout
    assert not is_mac("00:1a-2b:3c-4d:5e")
    assert _find_mac("MAC 00:1a-2b:3c-4d:5e") is None


def test_normalize_host():
    assert normalize_host("isg.lan") == "isg.lan"
    assert normalize_host("isg.lan/") == "isg.lan"
    assert normalize_host("  ISG.lan ") == "isg.lan"
    assert normalize_host("http://isg.lan/") == "isg.lan"
    assert normalize_host("HTTPS://192.168.1.50") == "192.168.1.50"
    assert normalize_host("isg.lan:8080") == "isg.lan:8080"
    # the Stiebel Eltron ISG integration's device has configuration_url http://<host>
    assert normalize_host("http://isg.lan") == normalize_host("isg.lan/")


def test_client_uses_the_normalized_host():
    assert IsgClient(None, "http://ISG.lan/", "", "")._base == "http://isg.lan/"
