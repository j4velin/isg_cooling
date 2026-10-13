"""http client for the Stiebel Eltron HTTP-Servicewelt"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass

import aiohttp
from bs4 import BeautifulSoup

import re

from .const import (
    COOLING_PAGE_PATH,
    ENERGY_PAGE_PATH,
    ISG_TEXTS,
    LOGIN_SUCCESS_MARKER,
    VAL_COOLING,
    IsgTexts,
)

_LOGGER = logging.getLogger(__name__)

# per request; the ISG answers within a few seconds
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30)


class IsgAuthError(Exception):
    """Login failed"""


class IsgConnectionError(Exception):
    """Network or parsing error"""


@dataclass
class IsgFormState:
    """fields for the cooling page"""

    fields: dict[str, str]
    cooling_on: bool


@dataclass
class IsgCoolingConsumption:
    """cooling power consumption in kWh, None if not shown by the ISG"""

    last_24h: float | None
    last_12m: float | None
    last_prev_12m: float | None


def _parse_energy(text: str) -> float | None:
    """'0,313MWh' -> 313.0 (kWh)"""
    match = re.search(r"([\d.,]+)\s*(kWh|MWh)", text)
    if match is None:
        return None
    number = match.group(1)
    if "," in number:
        number = number.replace(".", "").replace(",", ".")
    value = float(number)
    if match.group(2) == "MWh":
        value *= 1000
    return round(value, 3)


def _normalize_key(text: str) -> str:
    """'KÜHLEN 1–24 h' -> 'KÜHLEN1-24H'"""
    return re.sub(r"\s+", "", text).replace("–", "-").upper()


def _check_save_answer(answer: str) -> None:
    """save.php answers with JSON: success, warning or errors per field"""
    try:
        result = json.loads(answer)
    except ValueError as err:
        raise IsgConnectionError(
            f"Saving failed, unexpected answer: {answer[:200]!r}"
        ) from err
    if not isinstance(result, dict):
        raise IsgConnectionError(f"Saving failed, unexpected answer: {answer[:200]!r}")
    if result.get("success") is True:
        return
    if result.get("warning") is True:
        _LOGGER.warning("ISG saved with a warning: %s", result.get("message"))
        return
    raise IsgConnectionError(
        f"Saving failed: {result.get('message') or result.get('errors') or result}"
    )


def _texts_for_consumption_table(title: str) -> IsgTexts | None:
    """the language whose power consumption table has this title"""
    title = title.upper()
    for texts in ISG_TEXTS.values():
        if title in texts.consumption_table_titles:
            return texts
    return None


class IsgClient:
    """client for http://<host>/ (ISG Servicewelt)."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        username: str,
        password: str,
        login_marker: str = LOGIN_SUCCESS_MARKER,
    ) -> None:
        self._session = session
        self._base = f"http://{host.rstrip('/')}/"
        self._username = username
        self._password = password
        self._login_marker = login_marker
        self._logged_in = False

    @property
    def _has_credentials(self) -> bool:
        return bool(self._username or self._password)

    def _is_logged_in(self, html: str) -> bool:
        """configured marker or the marker of any known language"""
        html = html.lower()
        markers = (self._login_marker, *(t.login_marker for t in ISG_TEXTS.values()))
        return any(marker.lower() in html for marker in markers)

    async def async_login(self) -> None:
        """login (skipped when no credentials are configured)"""
        if not self._has_credentials:
            # no credentials configured -> the Servicewelt is used without a
            # login, so skip the login request entirely.
            self._logged_in = True
            return

        payload = {
            "user": self._username,
            "pass": self._password,
        }
        try:
            async with self._session.post(
                self._base, data=payload, timeout=REQUEST_TIMEOUT
            ) as resp:
                text = await resp.text()
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise IsgConnectionError(
                f"Connection to {self._base} failed: {err!r}"
            ) from err

        if not self._is_logged_in(text):
            raise IsgAuthError(
                "Login failed"
            )
        self._logged_in = True

    async def _async_get_page(self, path: str) -> str:
        """GET a page, login again once if the session expired"""
        if not self._logged_in:
            await self.async_login()
        html = await self._async_get(path)
        if self._has_credentials and not self._is_logged_in(html):
            await self.async_login()
            html = await self._async_get(path)
        return html

    async def _async_get(self, path: str) -> str:
        url = self._base + path
        try:
            async with self._session.get(url, timeout=REQUEST_TIMEOUT) as resp:
                if resp.status != 200:
                    raise IsgConnectionError(f"Unknown status {resp.status} from {url}")
                return await resp.text()
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise IsgConnectionError(f"GET {url} failed: {err!r}") from err

    async def _async_get_cooling_form(self) -> IsgFormState:
        html = await self._async_get_page(COOLING_PAGE_PATH)

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
                                match = re.search(r"='([^']*)';", line)
                                if match is None:
                                    continue
                                value = match.group(1)
                                fields[name] = value
                
        return IsgFormState(fields=fields, cooling_on=cooling_on)

    async def async_get_cooling_consumption(self) -> IsgCoolingConsumption:
        """cooling rows of LEISTUNGSAUFNAHME in INFO > ENERGIEBILANZ"""
        html = await self._async_get_page(ENERGY_PAGE_PATH)
        soup = BeautifulSoup(html, "html.parser")

        values: dict[str, float | None] | None = None
        texts: IsgTexts | None = None
        for table in soup.find_all("table", class_="info"):
            header = table.find("th")
            if header is None:
                continue
            texts = _texts_for_consumption_table(header.get_text(strip=True))
            if texts is None:
                continue
            values = {}
            for row in table.find_all("tr"):
                key = row.find("td", class_="key")
                value = row.find("td", class_="value")
                if key is None or value is None:
                    continue
                values[_normalize_key(key.get_text())] = _parse_energy(
                    value.get_text(strip=True)
                )
            break

        if values is None or texts is None:
            raise IsgConnectionError(
                "Power consumption table not found - session expired or "
                "unknown ISG language?"
            )
        # not every heat pump / ISG version shows the cooling rows
        return IsgCoolingConsumption(
            last_24h=values.get(texts.key_cooling_24h),
            last_12m=values.get(texts.key_cooling_12m),
            last_prev_12m=values.get(texts.key_cooling_prev_12m),
        )

    async def async_get_cooling_state(self) -> bool:
        """True, if cooling (KÜHLBETRIEB, val73) is on"""
        state = await self._async_get_cooling_form()
        return state.cooling_on

    async def async_set_cooling_state(self, turn_on: bool) -> None:
        """toggle val73, keep other fields unchanged."""
        state = await self._async_get_cooling_form()
        fields = dict(state.fields)
        fields[VAL_COOLING] = "1" if turn_on else "0"

        url = self._base + "save.php"
        # like the Servicewelt itself: $.post("save.php", {data: JSON of
        # $("#werte").serializeArray()}), sent form-encoded
        payload = {
            "data": json.dumps(
                [{"name": key, "value": value} for key, value in fields.items()],
                separators=(",", ":"),
            )
        }
        try:
            async with self._session.post(
                url, data=payload, timeout=REQUEST_TIMEOUT
            ) as resp:
                if resp.status != 200:
                    raise IsgConnectionError(f"Saving failed, status {resp.status}")
                answer = await resp.text()
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise IsgConnectionError(f"POST {url} failed: {err!r}") from err
        _check_save_answer(answer)

