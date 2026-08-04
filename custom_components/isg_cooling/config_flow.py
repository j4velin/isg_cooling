from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, DOMAIN
from .isg_client import IsgAuthError, IsgConnectionError, IsgClient

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default="isg.lan"): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class IsgConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config Flow Handler."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None):
        errors: dict[str, str] = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            client = IsgClient(
                session,
                user_input[CONF_HOST],
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
            )
            try:
                await client.async_login()
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

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )
