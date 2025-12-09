"""Bessa API client."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Optional

import aiohttp

from .const import BESSA_BASE_URL, BESSA_LOGIN_URL, BESSA_ORDERS_URL, MENU_TYPE

_LOGGER = logging.getLogger(__name__)


class AuthenticationError(Exception):
    """Exception raised for authentication errors."""
    pass


class BessaAPIClient:
    """API client for Bessa lunch orders."""
    
    def __init__(
        self,
        username: str,
        password: str,
        venue_id: int,
        session: aiohttp.ClientSession,
    ) -> None:
        """Initialize the API client."""
        self.username = username
        self.password = password
        self.venue_id = venue_id
        self.session = session
        self._token: str | None = None
    
    async def authenticate(self) -> bool:
        """Authenticate with Bessa API."""
        try:
            # Clean up username (remove any whitespace)
            email = self.username.strip()
            
            _LOGGER.debug("Attempting authentication with email: '%s'", email)
            
            # Login uses email field (not username) and returns sessionid cookie
            async with self.session.post(
                BESSA_LOGIN_URL,
                json={
                    "email": email,
                    "password": self.password,
                },
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            ) as response:
                if response.status == 200 or response.status == 201:
                    data = await response.json()
                    _LOGGER.debug("Login successful: %s", data)
                    
                    # Token is in 'key' field, use with "Token" prefix
                    self._token = data.get("key")
                    
                    if self._token:
                        _LOGGER.debug("Authentication token received")
                        return True
                    else:
                        _LOGGER.error("No token in response")
                        return False
                elif response.status == 400:
                    # Handle validation errors from official API spec
                    error_data = await response.json()
                    error_msg = "Login failed: "
                    if "non_field_errors" in error_data:
                        error_msg += ", ".join(error_data["non_field_errors"])
                    elif "email" in error_data:
                        error_msg += ", ".join(error_data["email"])
                    elif "password" in error_data:
                        error_msg += ", ".join(error_data["password"])
                    else:
                        error_msg += str(error_data)
                    _LOGGER.error(error_msg)
                    return False
                else:
                    _LOGGER.error("Authentication failed with status %s", response.status)
                    response_text = await response.text()
                    _LOGGER.error("Response: %s", response_text)
                    return False
        except Exception as err:
            _LOGGER.error("Authentication error: %s", err)
            return False
    
    async def get_today_orders(self) -> dict[str, Any]:
        """Get recent lunch orders with optimized API query.
        
        Returns orders from the last 7 days for our venue,
        filtered and sorted server-side for efficiency.
        """
        # Ensure we're authenticated
        if not self._token:
            if not await self.authenticate():
                raise AuthenticationError("Authentication failed")
        
        try:
            # Optimized query with server-side filtering
            start_date = datetime.now() - timedelta(days=7)
            
            # Bessa API uses "Token" prefix (not "Bearer")
            headers = {
                "Authorization": f"Token {self._token}",
                "Accept": "application/json",
            }
            
            # Add query parameters for efficient filtering
            params = {
                "venue": self.venue_id,  # Filter by configured venue
                "deleted__isnull": "true",  # Exclude deleted orders
                "date__gte": start_date.isoformat(),  # Orders from last 7 days
                "ordering": "-date",  # Newest first
            }
            
            async with self.session.get(
                BESSA_ORDERS_URL,
                headers=headers,
                params=params,
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    # API returns paginated response with "results" array
                    all_orders = data.get("results", [])
                    
                    # Handle pagination if needed (fetch all pages)
                    next_url = data.get("next")
                    while next_url:
                        async with self.session.get(
                            next_url,
                            headers=headers,
                        ) as next_response:
                            if next_response.status == 200:
                                next_data = await next_response.json()
                                all_orders.extend(next_data.get("results", []))
                                next_url = next_data.get("next")
                            else:
                                break
                    
                    return {"orders": all_orders}
                elif response.status == 401:
                    # Token expired, re-authenticate
                    self._token = None
                    return await self.get_today_orders()
                else:
                    _LOGGER.error("Failed to fetch orders: %s", response.status)
                    return {"orders": []}
        except Exception as err:
            _LOGGER.error("Error fetching orders: %s", err)
            raise
    
    def _is_cancelled(self, order: dict) -> bool:
        """Check if an order is cancelled."""
        # State 9 means cancelled
        states = order.get("states", [])
        if states:
            latest_state = states[0].get("state")
            return latest_state == 9
        return False
    
    def _is_order_for_date(self, order: dict, date_str: str) -> bool:
        """Check if an order is for a specific date."""
        # Orders have a "date" field with the pickup/delivery date
        order_date = order.get("date", "")
        if order_date:
            # Extract YYYY-MM-DD from ISO format (e.g., "2025-12-09T10:15:00Z")
            order_date_only = order_date[:10]
            return order_date_only == date_str
        
        return False
    
    async def get_order_for_date(self, date: str) -> dict[str, Any]:
        """Get lunch orders for a specific date."""
        if not self._token:
            if not await self.authenticate():
                raise AuthenticationError("Authentication failed")
        
        try:
            headers = {
                "Authorization": f"Token {self._token}",
                "Accept": "application/json",
            }
            
            async with self.session.get(
                BESSA_ORDERS_URL,
                headers=headers,
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    all_orders = data.get("results", [])
                    date_orders = [
                        order for order in all_orders
                        if self._is_order_for_date(order, date)
                    ]
                    return {"orders": date_orders}
                else:
                    _LOGGER.error("Failed to fetch orders for %s: %s", date, response.status)
                    return {}
        except Exception as err:
            _LOGGER.error("Error fetching orders for %s: %s", date, err)
            raise
    
    async def get_menu(self, date: str) -> dict[str, Any]:
        """Get menu for a specific date.
        
        Returns menu data including categories, items, and availability counts.
        """
        # Ensure we're authenticated
        if not self._token:
            if not await self.authenticate():
                raise AuthenticationError("Authentication failed")
        
        try:
            # Bessa API endpoint for menu
            # menu_type 7 = canteen menu
            url = f"{BESSA_BASE_URL}/v1/venues/{self.venue_id}/menu/{MENU_TYPE}/{date}/"
            
            headers = {
                "Authorization": f"Token {self._token}",
                "Accept": "application/json",
            }
            
            async with self.session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    results = data.get("results", [])
                    
                    # Process menu data to extract items with availability
                    menu_items = []
                    for category in results:
                        items = category.get("items", [])
                        for item in items:
                            # Extract availability (use available_amount, not available)
                            available_amount = item.get("available_amount")
                            available = None
                            if available_amount:
                                try:
                                    available = int(available_amount)
                                except (ValueError, TypeError):
                                    available = None
                            
                            menu_items.append({
                                "id": item.get("id"),
                                "name": item.get("name", "Unknown"),
                                "description": item.get("description", ""),
                                "price": item.get("price", "0"),
                                "allergens": item.get("allergens", ""),
                                "available": available,  # Now correctly extracted
                                "category": category.get("name", ""),
                            })
                    
                    return {
                        "categories": results,
                        "items": menu_items,
                        "raw_data": data,
                    }
                elif response.status == 401:
                    # Token expired, re-authenticate
                    self._token = None
                    return await self.get_menu(date)
                else:
                    _LOGGER.debug("No menu available for %s: %s", date, response.status)
                    return {"categories": [], "items": []}
        except Exception as err:
            _LOGGER.error("Error fetching menu for %s: %s", date, err)
            return {"categories": [], "items": []}
