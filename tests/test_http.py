"""IsgClient against a fake ISG on 127.0.0.1 (cookie session, save.php)."""
import asyncio
import json
import urllib.parse

import aiohttp
from aiohttp import web

from conftest import read_fixture
from isg_cooling import isg_client
from isg_cooling.isg_client import IsgAuthError, IsgClient, IsgConnectionError

LOGIN_PAGE = "<html><form>User name: <input name=user> Password: <input name=pass></form></html>"


class FakeIsg:
    """login via POST /, session in a PHPSESSID cookie, like the real ISG"""

    def __init__(self):
        self.pages = {
            "1,2": read_fixture("energy_en.html"),
            "4,3,2": read_fixture("cooling_en.html"),
        }
        self.sessions: set[str] = set()
        self.saved: list[str] = []
        self.save_answer = '{"success":true}'
        self.delay = 0.0

    def logged_in(self, request) -> bool:
        return request.cookies.get("PHPSESSID") in self.sessions

    async def root(self, request):
        if request.method == "POST":
            form = await request.post()
            if form.get("user") == "user" and form.get("pass") == "secret":
                sid = f"s{len(self.sessions) + 1}"
                self.sessions.add(sid)
                resp = web.Response(text=self.pages["1,2"], content_type="text/html")
                resp.set_cookie("PHPSESSID", sid, path="/")
                return resp
            return web.Response(text=LOGIN_PAGE, content_type="text/html")
        await asyncio.sleep(self.delay)
        page = request.query.get("s")
        if not self.logged_in(request) or page not in self.pages:
            return web.Response(text=LOGIN_PAGE, content_type="text/html")
        return web.Response(text=self.pages[page], content_type="text/html")

    async def save(self, request):
        self.saved.append(await request.text())
        if not self.logged_in(request):
            return web.Response(text=LOGIN_PAGE, content_type="text/html")
        return web.Response(text=self.save_answer, content_type="text/html")


def with_fake_isg(test):
    """run `test(isg, host)` against a fake ISG on a free port"""

    async def run():
        isg = FakeIsg()
        app = web.Application()
        app.router.add_route("*", "/", isg.root)
        app.router.add_post("/save.php", isg.save)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        try:
            await test(isg, f"127.0.0.1:{port}")
        finally:
            await runner.cleanup()

    asyncio.run(run())


def ip_session() -> aiohttp.ClientSession:
    """like async_create_isg_session() in __init__.py"""
    return aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(unsafe=True))


def test_default_cookie_jar_loses_the_session_on_ip_hosts():
    # the reason for async_create_isg_session(): Home Assistant's shared
    # session uses aiohttp's default cookie jar
    async def test(isg, host):
        async with aiohttp.ClientSession() as session:
            client = IsgClient(session, host, "user", "secret")
            try:
                await client.async_get_cooling_consumption()
            except IsgConnectionError:
                return
            raise AssertionError("expected IsgConnectionError")

    with_fake_isg(test)


def test_read_values_on_ip_host():
    async def test(isg, host):
        async with ip_session() as session:
            client = IsgClient(session, host, "user", "secret")
            result = await client.async_get_cooling_consumption()
            assert (result.last_24h, result.last_12m, result.last_prev_12m) == (0.0, 313.0, 26.0)
            assert await client.async_get_cooling_state() is False

    with_fake_isg(test)


def test_wrong_password():
    async def test(isg, host):
        async with ip_session() as session:
            client = IsgClient(session, host, "user", "wrong")
            try:
                await client.async_login()
            except IsgAuthError:
                return
            raise AssertionError("expected IsgAuthError")

    with_fake_isg(test)


def test_save_like_the_servicewelt():
    async def test(isg, host):
        async with ip_session() as session:
            client = IsgClient(session, host, "user", "secret")
            before = (await client._async_get_cooling_form()).fields
            await client.async_set_cooling_state(True)

            body = isg.saved[-1]
            form = urllib.parse.parse_qs(body)
            assert list(form) == ["data"]
            # compact like JSON.stringify(), which the Servicewelt uses
            assert '": ' not in form["data"][0]
            sent = {d["name"]: d["value"] for d in json.loads(form["data"][0])}
            assert sent == {**before, "val73": "1"}

    with_fake_isg(test)


def test_special_characters_survive_the_encoding():
    async def test(isg, host):
        async with ip_session() as session:
            client = IsgClient(session, host, "user", "secret")
            isg.pages["4,3,2"] = isg.pages["4,3,2"].replace("'18,0'", "'a+b&c=d'")
            await client.async_set_cooling_state(True)
            sent = json.loads(urllib.parse.parse_qs(isg.saved[-1])["data"][0])
            assert {"name": "val103", "value": "a+b&c=d"} in sent

    with_fake_isg(test)


def test_rejected_save_raises():
    async def test(isg, host):
        async with ip_session() as session:
            client = IsgClient(session, host, "user", "secret")
            isg.save_answer = '{"success":false,"errors":{"103":"value out of range"}}'
            try:
                await client.async_set_cooling_state(False)
            except IsgConnectionError as err:
                assert "value out of range" in str(err)
                return
            raise AssertionError("expected IsgConnectionError")

    with_fake_isg(test)


def test_save_with_warning_counts_as_saved():
    async def test(isg, host):
        async with ip_session() as session:
            client = IsgClient(session, host, "user", "secret")
            isg.save_answer = '{"warning":true,"message":"saved with a warning"}'
            await client.async_set_cooling_state(False)

    with_fake_isg(test)


def test_session_expired_before_saving_raises():
    async def test(isg, host):
        async with ip_session() as session:
            client = IsgClient(session, host, "user", "secret")
            read_form = client._async_get_page

            async def read_form_then_expire(path):
                html = await read_form(path)
                isg.sessions.clear()
                return html

            client._async_get_page = read_form_then_expire
            try:
                await client.async_set_cooling_state(True)
            except IsgConnectionError:
                return
            raise AssertionError("expected IsgConnectionError")

    with_fake_isg(test)


def test_hanging_isg_times_out():
    async def test(isg, host):
        original = isg_client.REQUEST_TIMEOUT
        isg_client.REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=0.3)
        isg.delay = 2
        try:
            async with ip_session() as session:
                client = IsgClient(session, host, "user", "secret")
                await client.async_login()
                try:
                    await client.async_get_cooling_consumption()
                except IsgConnectionError:
                    return
                raise AssertionError("expected IsgConnectionError")
        finally:
            isg_client.REQUEST_TIMEOUT = original

    with_fake_isg(test)
