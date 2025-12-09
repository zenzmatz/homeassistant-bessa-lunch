"""Config flow for Bessa Lunch integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .bessa_api import BessaAPIClient
from .const import CONF_VENUE_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_VENUE_ID): int,
    }
)


class BessaLunchConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Bessa Lunch."""
    
    VERSION = 1
    
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        
        if user_input is not None:
            # Validate the credentials
            session = async_get_clientsession(self.hass)
            api_client = BessaAPIClient(
                username=user_input[CONF_USERNAME],
                password=user_input[CONF_PASSWORD],
                session=session,
            )
            
            try:
                if await api_client.authenticate():
                    # Create the config entry
                    await self.async_set_unique_id(user_input[CONF_USERNAME])
                    self._abort_if_unique_id_configured()
                    
                    return self.async_create_entry(
                        title=f"Bessa Lunch ({user_input[CONF_USERNAME]})",
                        data=user_input,
                    )
                else:
                    errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
        
        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
