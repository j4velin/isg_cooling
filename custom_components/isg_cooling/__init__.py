"""ISG cooling integration for LWZ heat pumps."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_CONSUMPTION_SCAN_INTERVAL,
    CONF_HOST,
    CONF_LOGIN_MARKER,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    DEFAULT_CONSUMPTION_SCAN_INTERVAL_MINUTES,
    DEFAULT_SCAN_INTERVAL_HOURS,
    DOMAIN,
    LOGIN_SUCCESS_MARKER,
)
from .isg_client import (
    IsgAuthError,
    IsgClient,
    IsgConnectionError,
    IsgCoolingConsumption,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "switch"]


@dataclass
class IsgRuntimeData:
    """shared by the platforms of one config entry"""

    client: IsgClient
    cooling: DataUpdateCoordinator[bool]
    consumption: DataUpdateCoordinator[IsgCoolingConsumption]


def get_option(entry: ConfigEntry, key: str, default: Any) -> Any:
    """value from the options flow, else from the setup, else the default"""
    return entry.options.get(key, entry.data.get(key, default))


def async_create_isg_session(hass: HomeAssistant) -> aiohttp.ClientSession:
    """own session for the ISG, to be closed by the caller

    The ISG keeps the login in a cookie. The shared session of Home
    Assistant drops cookies of IP addresses, so a host like 192.168.1.50
    would never stay logged in.
    """
    return async_create_clientsession(
        hass, auto_cleanup=False, cookie_jar=aiohttp.CookieJar(unsafe=True)
    )


def create_client(session: aiohttp.ClientSession, data: dict[str, Any]) -> IsgClient:
    return IsgClient(
        session,
        data[CONF_HOST],
        data[CONF_USERNAME],
        data[CONF_PASSWORD],
        data.get(CONF_LOGIN_MARKER, LOGIN_SUCCESS_MARKER),
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    session = async_create_isg_session(hass)
    entry.async_on_unload(session.close)
    client = create_client(session, entry.data)

    async def _async_update_cooling() -> bool:
        try:
            return await client.async_get_cooling_state()
        except (IsgConnectionError, IsgAuthError) as err:
            raise UpdateFailed(str(err)) from err

    async def _async_update_consumption() -> IsgCoolingConsumption:
        try:
            return await client.async_get_cooling_consumption()
        except (IsgConnectionError, IsgAuthError) as err:
            raise UpdateFailed(str(err)) from err

    cooling = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="isg_cooling",
        update_method=_async_update_cooling,
        update_interval=timedelta(
            hours=get_option(entry, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_HOURS)
        ),
    )
    consumption = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="isg_cooling_consumption",
        update_method=_async_update_consumption,
        update_interval=timedelta(
            minutes=get_option(
                entry,
                CONF_CONSUMPTION_SCAN_INTERVAL,
                DEFAULT_CONSUMPTION_SCAN_INTERVAL_MINUTES,
            )
        ),
    )
    # raises ConfigEntryNotReady if the ISG can't be reached, so Home
    # Assistant retries the whole setup later
    await cooling.async_config_entry_first_refresh()
    await consumption.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = IsgRuntimeData(
        client, cooling, consumption
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unloaded


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """reload to apply changed options"""
    await hass.config_entries.async_reload(entry.entry_id)
