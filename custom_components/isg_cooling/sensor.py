"""Sensors for the cooling power consumption (INFO > ENERGIEBILANZ)."""
from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.restore_state import RestoredExtraData
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.util import dt as dt_util

from . import IsgRuntimeData
from .consumption_total import (
    DAILY_READING_HOUR,
    DAILY_READING_MINUTES,
    CoolingConsumptionTotal,
)
from .const import DOMAIN
from .isg_client import IsgCoolingConsumption


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """create consumption sensors from config."""
    runtime: IsgRuntimeData = hass.data[DOMAIN][entry.entry_id]
    coordinator = runtime.consumption

    # the 1-12 M sensor was removed, the total covers it
    registry = er.async_get(hass)
    if entity_id := registry.async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_cooling_consumption_12m"
    ):
        registry.async_remove(entity_id)

    async_add_entities(
        [
            IsgCoolingConsumption24hSensor(coordinator, entry),
            IsgCoolingConsumptionTotalSensor(coordinator, entry),
        ]
    )


class IsgCoolingConsumptionSensor(SensorEntity):
    """cooling row of LEISTUNGSAUFNAHME in the Servicewelt."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:snowflake"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR


class IsgCoolingConsumption24hSensor(CoordinatorEntity, IsgCoolingConsumptionSensor):
    """KÜHLEN 1-24 h, the last 24 hours, updated hourly by the ISG.

    No state class: the window goes up and down, so neither "total" nor
    "total_increasing" gives correct statistics. Disabled by default, the
    total covers everything except the consumption within a day. The
    coordinator only polls while this sensor is enabled.
    """

    _attr_translation_key = "cooling_consumption_24h"
    _attr_suggested_display_precision = 3
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[IsgCoolingConsumption],
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{self._attr_translation_key}"

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.last_24h


class IsgCoolingConsumptionTotalSensor(IsgCoolingConsumptionSensor, RestoreSensor):
    """lifetime total, the ISG has no such value - see consumption_total.py

    Use this one for the energy dashboard. It changes once a day, at about
    23:15. Not a coordinator listener, so it doesn't keep the
    coordinator polling: it fetches the page itself for the daily reading.
    """

    _attr_translation_key = "cooling_consumption_total"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_suggested_display_precision = 3
    # only the daily reading changes it, Home Assistant mustn't poll it
    _attr_should_poll = False

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[IsgCoolingConsumption],
        entry: ConfigEntry,
    ) -> None:
        self._coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_{self._attr_translation_key}"
        self._total = CoolingConsumptionTotal()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        extra = await self.async_get_last_extra_data()
        if extra is not None:
            restored = CoolingConsumptionTotal.from_dict(extra.as_dict())
            if restored is not None:
                self._total = restored
        # the reading of the setup, in case Home Assistant starts at night
        self._update_total(self._coordinator.data)
        self.async_on_remove(
            async_track_time_change(
                self.hass,
                self._async_daily_reading,
                hour=DAILY_READING_HOUR,
                minute=DAILY_READING_MINUTES,
                second=0,
            )
        )

    async def _async_daily_reading(self, now: datetime) -> None:
        """fetch the page for the daily reading, retried until it worked"""
        if self._total.is_read(dt_util.now()):
            return
        await self._coordinator.async_refresh()
        if self._coordinator.last_update_success:
            self._update_total(self._coordinator.data)
            self.async_write_ha_state()

    def _update_total(self, data: IsgCoolingConsumption | None) -> None:
        if data is None:
            return
        self._total.update(
            data.last_24h, data.last_12m, data.last_prev_12m, dt_util.now()
        )

    @property
    def native_value(self) -> float | None:
        return self._total.value

    @property
    def extra_restore_state_data(self) -> RestoredExtraData:
        return RestoredExtraData(self._total.as_dict())
