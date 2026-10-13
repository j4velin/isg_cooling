from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback

from . import async_create_isg_session, create_client, get_option
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
from .isg_client import IsgAuthError, IsgConnectionError


def _interval_fields(scan_interval: int, consumption_scan_interval: int) -> dict:
    """poll interval fields, shared by the config and the options flow"""
    return {
        vol.Required(
            CONF_SCAN_INTERVAL, default=scan_interval
        ): vol.All(vol.Coerce(int), vol.Range(min=1)),
        vol.Required(
            CONF_CONSUMPTION_SCAN_INTERVAL, default=consumption_scan_interval
        ): vol.All(vol.Coerce(int), vol.Range(min=1)),
    }


DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default="isg.lan"): str,
        vol.Optional(CONF_USERNAME, default=""): str,
        vol.Optional(CONF_PASSWORD, default=""): str,
        # an empty marker would be found on every page, so a failed login
        # would go unnoticed
        vol.Required(CONF_LOGIN_MARKER, default=LOGIN_SUCCESS_MARKER): vol.All(
            str, vol.Length(min=1)
        ),
        **_interval_fields(
            DEFAULT_SCAN_INTERVAL_HOURS, DEFAULT_CONSUMPTION_SCAN_INTERVAL_MINUTES
        ),
    }
)


class IsgConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config Flow Handler."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> IsgOptionsFlow:
        return IsgOptionsFlow(config_entry)

    async def async_step_user(self, user_input: dict | None = None):
        errors: dict[str, str] = {}

        if user_input is not None:
            session = async_create_isg_session(self.hass)
            client = create_client(session, user_input)
            try:
                # read the cooling page instead of only logging in: this also
                # checks the host when no credentials are set (no login then)
                await client.async_get_cooling_state()
            except IsgAuthError:
                errors["base"] = "invalid_auth"
            except IsgConnectionError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(user_input[CONF_HOST])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"ISG Cooling ({user_input[CONF_HOST]})",
                    data=user_input,
                )
            finally:
                await session.close()

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class IsgOptionsFlow(config_entries.OptionsFlow):
    """change the poll intervals after setup"""

    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        # not stored as self.config_entry, which newer HA versions set itself
        self._entry = entry

    async def async_step_init(self, user_input: dict | None = None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                _interval_fields(
                    get_option(
                        self._entry, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_HOURS
                    ),
                    get_option(
                        self._entry,
                        CONF_CONSUMPTION_SCAN_INTERVAL,
                        DEFAULT_CONSUMPTION_SCAN_INTERVAL_MINUTES,
                    ),
                )
            ),
        )
