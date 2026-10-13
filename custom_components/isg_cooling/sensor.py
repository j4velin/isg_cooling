"""Sensors for the cooling power consumption (INFO > ENERGIEBILANZ)."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoredExtraData
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util import dt as dt_util

from .consumption_total import CoolingConsumptionTotal
from .const import (
    CONF_CONSUMPTION_SCAN_INTERVAL,
    CONF_HOST,
    CONF_LOGIN_MARKER,
    CONF_PASSWORD,
    CONF_USERNAME,
    DEFAULT_CONSUMPTION_SCAN_INTERVAL_MINUTES,
    LOGIN_SUCCESS_MARKER,
)
from .isg_client import (
    IsgAuthError,
    IsgClient,
    IsgConnectionError,
    IsgCoolingConsumption,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """create consumption sensors from config."""
    data = entry.data
    session = async_get_clientsession(hass)
    client = IsgClient(
        session,
        data[CONF_HOST],
        data[CONF_USERNAME],
        data[CONF_PASSWORD],
        data.get(CONF_LOGIN_MARKER, LOGIN_SUCCESS_MARKER),
    )

    async def _async_update_data() -> IsgCoolingConsumption:
        try:
            return await client.async_get_cooling_consumption()
        except (IsgConnectionError, IsgAuthError) as err:
            raise UpdateFailed(str(err)) from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="isg_cooling_consumption",
        update_method=_async_update_data,
        update_interval=timedelta(
            minutes=data.get(
                CONF_CONSUMPTION_SCAN_INTERVAL,
                DEFAULT_CONSUMPTION_SCAN_INTERVAL_MINUTES,
            )
        ),
    )
    await coordinator.async_config_entry_first_refresh()

    async_add_entities(
        [
            IsgCoolingConsumption24hSensor(coordinator, entry),
            IsgCoolingConsumption12mSensor(coordinator, entry),
            IsgCoolingConsumptionTotalSensor(coordinator, entry),
        ]
    )


class IsgCoolingConsumptionSensor(CoordinatorEntity, SensorEntity):
    """cooling row of LEISTUNGSAUFNAHME in the Servicewelt."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:snowflake"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[IsgCoolingConsumption],
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{self._attr_translation_key}"


class IsgCoolingConsumption24hSensor(IsgCoolingConsumptionSensor):
    """KÜHLEN 1-24 h, resets daily - use this one for the energy dashboard."""

    _attr_translation_key = "cooling_consumption_24h"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_suggested_display_precision = 3

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.last_24h


class IsgCoolingConsumption12mSensor(IsgCoolingConsumptionSensor):
    """KÜHLEN 1-12 M, only 1 kWh resolution."""

    _attr_translation_key = "cooling_consumption_12m"
    _attr_state_class = SensorStateClass.TOTAL
    _attr_suggested_display_precision = 0

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.last_12m


class IsgCoolingConsumptionTotalSensor(IsgCoolingConsumptionSensor, RestoreSensor):
    """lifetime total, the ISG has no such value - see consumption_total.py"""

    _attr_translation_key = "cooling_consumption_total"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_suggested_display_precision = 3

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[IsgCoolingConsumption],
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator, entry)
        self._total = CoolingConsumptionTotal()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        extra = await self.async_get_last_extra_data()
        if extra is not None:
            restored = CoolingConsumptionTotal.from_dict(extra.as_dict())
            if restored is not None:
                self._total = restored
        self._update_total()

    @callback
    def _handle_coordinator_update(self) -> None:
        self._update_total()
        super()._handle_coordinator_update()

    def _update_total(self) -> None:
        data = self.coordinator.data
        self._total.update(
            data.last_24h, data.last_12m, data.last_prev_12m, dt_util.now()
        )

    @property
    def native_value(self) -> float | None:
        return self._total.value

    @property
    def extra_restore_state_data(self) -> RestoredExtraData:
        return RestoredExtraData(self._total.as_dict())
