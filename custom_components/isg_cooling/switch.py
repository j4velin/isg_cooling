"""Switch for the cooling setting (val73)."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import IsgRuntimeData
from .const import DOMAIN
from .isg_client import IsgAuthError, IsgClient, IsgConnectionError


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """create switch entity from config."""
    runtime: IsgRuntimeData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [IsgCoolingSwitch(runtime.cooling, runtime.client, entry, runtime.device_info)]
    )


class IsgCoolingSwitch(CoordinatorEntity, SwitchEntity):
    """represents the cooling switch in the Servicewelt (val73)."""

    _attr_has_entity_name = True
    _attr_translation_key = "cooling"
    _attr_icon = "mdi:snowflake"

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[bool],
        client: IsgClient,
        entry: ConfigEntry,
        device_info: DeviceInfo,
    ) -> None:
        super().__init__(coordinator)
        self._client = client
        self._attr_unique_id = f"{entry.entry_id}_val73"
        self._attr_device_info = device_info

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data)

    async def async_turn_on(self, **kwargs) -> None:
        await self._async_set(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._async_set(False)

    async def _async_set(self, turn_on: bool) -> None:
        try:
            await self._client.async_set_cooling_state(turn_on)
        except (IsgConnectionError, IsgAuthError) as err:
            raise HomeAssistantError(
                f"Could not switch cooling {'on' if turn_on else 'off'}: {err}"
            ) from err
        await self.coordinator.async_request_refresh()
