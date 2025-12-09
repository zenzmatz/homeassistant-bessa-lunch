"""The Bessa Lunch integration."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .bessa_api import BessaAPIClient

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Bessa Lunch from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    # Create API client
    api_client = BessaAPIClient(
        username=entry.data["username"],
        password=entry.data["password"],
        venue_id=entry.data["venue_id"],
        session=aiohttp_client.async_get_clientsession(hass),
    )
    
    # Create coordinator
    coordinator = BessaLunchDataUpdateCoordinator(hass, api_client)
    
    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()
    
    hass.data[DOMAIN][entry.entry_id] = coordinator
    
    # Forward the setup to the sensor platform
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    
    return unload_ok


class BessaLunchDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Bessa lunch data."""
    
    def __init__(self, hass: HomeAssistant, api_client: BessaAPIClient) -> None:
        """Initialize."""
        self.api_client = api_client
        
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=30),
        )
    
    async def _async_update_data(self):
        """Fetch data from API."""
        try:
            # Fetch today's orders
            orders_data = await self.api_client.get_today_orders()
            
            # Fetch menus for the next 7 days
            from datetime import datetime, timedelta
            result = orders_data.copy()
            
            for days_ahead in range(7):
                target_date = (datetime.now().date() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
                menu_data = await self.api_client.get_menu(target_date)
                # Extract the items array from the menu data
                result[f"menu_{target_date}"] = menu_data.get("items", [])
            
            return result
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
