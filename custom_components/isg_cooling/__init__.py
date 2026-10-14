"""ISG cooling integration for LWZ heat pumps."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
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
    STIEBEL_ELTRON_ISG_DOMAIN,
)
from .isg_client import (
    IsgAuthError,
    IsgClient,
    IsgConnectionError,
    IsgCoolingConsumption,
    is_mac,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "switch"]


@dataclass
class IsgRuntimeData:
    """shared by the platforms of one config entry"""

    client: IsgClient
    cooling: DataUpdateCoordinator[bool]
    consumption: DataUpdateCoordinator[IsgCoolingConsumption]
    # the device the entities belong to, see _async_setup_device()
    device_info: DeviceInfo


def get_option(entry: ConfigEntry, key: str, default: Any) -> Any:
    """value from the options flow, else from the setup, else the default"""
    return entry.options.get(key, entry.data.get(key, default))


def _own_device_info(entry: ConfigEntry) -> DeviceInfo:
    """own device for the ISG, if it isn't linked to another one"""
    info = DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title,
        manufacturer="Stiebel Eltron",
        model="ISG",
        configuration_url=f"http://{entry.data[CONF_HOST]}/",
    )
    if is_mac(entry.unique_id):
        info["connections"] = {(CONNECTION_NETWORK_MAC, entry.unique_id)}
    return info


@callback
def _async_find_isg_device(hass: HomeAssistant, entry: ConfigEntry) -> dr.DeviceEntry | None:
    """the device of the Stiebel Eltron ISG integration for this ISG: the only
    one, or among several the one with the same host"""
    devices = [
        device
        for device in dr.async_get(hass).devices.values()
        if any(domain == STIEBEL_ELTRON_ISG_DOMAIN for domain, _ in device.identifiers)
    ]
    if len(devices) == 1:
        return devices[0]
    host = entry.data[CONF_HOST].rstrip("/")
    matching = [
        device
        for device in devices
        if (device.configuration_url or "").rstrip("/") == f"http://{host}"
    ]
    if len(matching) == 1:
        return matching[0]
    if devices:
        _LOGGER.info(
            "Several Stiebel Eltron ISG devices, none with host %s: using an own device",
            host,
        )
    return None


@callback
def _async_setup_device(hass: HomeAssistant, entry: ConfigEntry) -> DeviceInfo:
    """the device of the entities: the one of the Stiebel Eltron ISG
    integration if there is one, else an own device

    Also moves the entities when the device changed. Leaving a device makes
    Home Assistant delete the entities of this entry that are still on it,
    so the entities are moved to the new device first.
    """
    dev_reg = dr.async_get(hass)
    info = _own_device_info(entry)
    isg_device = _async_find_isg_device(hass, entry)
    if isg_device is not None:
        # only the identifiers: the entities join that device as it is
        info = DeviceInfo(identifiers=isg_device.identifiers)
    device = dev_reg.async_get_or_create(config_entry_id=entry.entry_id, **info)

    ent_reg = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(ent_reg, entry.entry_id):
        if entity.device_id != device.id:
            ent_reg.async_update_entity(entity.entity_id, device_id=device.id)
    for old in dr.async_entries_for_config_entry(dev_reg, entry.entry_id):
        if old.id != device.id:
            dev_reg.async_update_device(old.id, remove_config_entry_id=entry.entry_id)
    return info


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
    await _async_use_mac_as_unique_id(hass, entry, client)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = IsgRuntimeData(
        client, cooling, consumption, _async_setup_device(hass, entry)
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unloaded


async def _async_use_mac_as_unique_id(
    hass: HomeAssistant, entry: ConfigEntry, client: IsgClient
) -> None:
    """older versions identified the ISG by its host, so the same ISG could
    be added twice, e.g. as isg.lan and by its IP address"""
    if is_mac(entry.unique_id):
        return
    try:
        mac = await client.async_get_mac()
    except (IsgConnectionError, IsgAuthError) as err:
        _LOGGER.debug("MAC address not readable, trying again next start: %s", err)
        return
    if mac is None:
        return
    if any(
        other.unique_id == mac
        for other in hass.config_entries.async_entries(DOMAIN)
        if other.entry_id != entry.entry_id
    ):
        _LOGGER.warning(
            "The ISG at %s is set up twice, remove one of the entries",
            entry.data[CONF_HOST],
        )
        return
    hass.config_entries.async_update_entry(entry, unique_id=mac)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """reload to apply changed options"""
    await hass.config_entries.async_reload(entry.entry_id)
