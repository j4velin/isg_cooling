"""http client for the Stiebel Eltron HTTP-Servicewelt"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import aiohttp
from bs4 import BeautifulSoup

import re

from .const import COOLING_PAGE_PATH, VAL_COOLING

_LOGGER = logging.getLogger(__name__)


class IsgAuthError(Exception):
    """Login failed"""


class IsgConnectionError(Exception):
    """Network or parsing error"""


@dataclass
class IsgFormState:
    """fields for the cooling page"""

    fields: dict[str, str]
    cooling_on: bool

class IsgClient:
    """client for http://<host>/ (ISG Servicewelt)."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        username: str,
        password: str,
    ) -> None:
        self._session = session
        self._base = f"http://{host.rstrip('/')}/"
        self._username = username
        self._password = password
        self._logged_in = False

    async def async_login(self) -> None:
        """login"""
        payload = {
            "user": self._username,
            "pass": self._password,
        }
        try:
            async with self._session.post(self._base, data=payload) as resp:
                text = await resp.text()
        except aiohttp.ClientError as err:
            raise IsgConnectionError(f"Connection to {self._base} failed: {err}") from err

        if "angemeldet als" not in text.lower():
            raise IsgAuthError(
                "Login failed"
            )
        self._logged_in = True

    async def _async_get_cooling_form(self) -> IsgFormState:
        url = self._base + COOLING_PAGE_PATH
        try:
            async with self._session.get(url) as resp:
                if resp.status != 200:
                    raise IsgConnectionError(f"Unknown status {resp.status} from {url}")
                html = await resp.text()
        except aiohttp.ClientError as err:
            raise IsgConnectionError(f"GET {url} failed: {err}") from err

        soup = BeautifulSoup(html, "html.parser")
        form = soup.find("form", id="werte")
        if form is None:
            raise IsgConnectionError(
                "Form 'werte' not found - session expired?"
            )
        scripts = soup.find_all("script")
        

        fields: dict[str, str] = {}
        cooling_on = False

        for inp in form.find_all("input"):
            name = inp.get("name")
            if not name:
                continue
            itype = inp.get("type", "text")
            if itype == "radio":
                if inp.has_attr("checked"):
                    value = inp.get("value", "")
                    fields[name] = value
                    if name == VAL_COOLING and value == "1":
                        cooling_on = True
            elif itype in ("text", "hidden"):
                search = "jsvalues['" + name[3:] + "']['val']"
                for script in scripts:
                    if script.string is not None:
                        for line in script.string.splitlines():
                            if search in line:
                                match = re.search(r"='(.+)';", line)
                                if match is None:
                                    continue
                                value = match.group(1)
                                fields[name] = value
                
        return IsgFormState(fields=fields, cooling_on=cooling_on)

    async def async_get_cooling_state(self) -> bool:
        """True, if cooling (KÜHLBETRIEB, val73) is on"""
        if not self._logged_in:
            await self.async_login()
        state = await self._async_get_cooling_form()
        return state.cooling_on

    async def async_set_cooling_state(self, turn_on: bool) -> None:
        """toggle val73, keep other fields unchanged."""
        if not self._logged_in:
            await self.async_login()

        state = await self._async_get_cooling_form()
        fields = dict(state.fields)
        fields[VAL_COOLING] = "1" if turn_on else "0"

        url = self._base + "/save.php"
                
        payload = "data=["
        for key, value in fields.items():
            payload += '{"name":"' + key + '", "value":"' + value + '"},'
        payload = payload[:-1] + "]"
        
        headers = {'content-type': 'application/x-www-form-urlencoded'}
                
        try:
            async with self._session.post(url, data=payload, headers=headers) as resp:
                if resp.status != 200:
                    raise IsgConnectionError(f"Saving failed, status {resp.status}")
        except aiohttp.ClientError as err:
            raise IsgConnectionError(f"POST {url} failed: {err}") from err

