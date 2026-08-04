"""Switch for the cooling setting (val73)."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, DOMAIN
from .isg_client import IsgAuthError, IsgConnectionError, IsgClient

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(hours=24)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """create switch entity from config."""
    data = entry.data
    session = async_get_clientsession(hass)
    client = IsgClient(
        session, data[CONF_HOST], data[CONF_USERNAME], data[CONF_PASSWORD]
    )

    async def _async_update_data():
        try:
            return await client.async_get_cooling_state()
        except (IsgConnectionError, IsgAuthError) as err:
            raise UpdateFailed(str(err)) from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="isg_cooling",
        update_method=_async_update_data,
        update_interval=SCAN_INTERVAL,
    )
    await coordinator.async_config_entry_first_refresh()

    async_add_entities([IsgCoolingSwitch(coordinator, client, entry)])


class IsgCoolingSwitch(CoordinatorEntity, SwitchEntity):
    """represents the cooling switch in the Servicewelt (val73)."""

    _attr_has_entity_name = True
    _attr_name = "Kühlbetrieb"
    _attr_icon = "mdi:snowflake"

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        client: IsgClient,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._client = client
        self._attr_unique_id = f"{entry.entry_id}_val73"

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data)

    async def async_turn_on(self, **kwargs) -> None:
        await self._client.async_set_cooling_state(True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        await self._client.async_set_cooling_state(False)
        await self.coordinator.async_request_refresh()
