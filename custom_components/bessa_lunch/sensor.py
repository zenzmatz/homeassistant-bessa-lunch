"""Sensor platform for Bessa Lunch integration."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import BessaLunchDataUpdateCoordinator
from .const import DOMAIN, DEVICE_NAME, DEVICE_MANUFACTURER, DEVICE_MODEL, ORDER_STATES


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Bessa Lunch sensors based on a config entry."""
    coordinator: BessaLunchDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    
    entities = []
    
    # Add 2 entities for each day (7 days total = 14 entities)
    for days_ahead in range(7):
        entities.append(BessaLunchDailyOrderSensor(coordinator, entry, days_ahead))
        entities.append(BessaLunchDailyMenuSensor(coordinator, entry, days_ahead))
    
    async_add_entities(entities)


class BessaLunchDailyOrderSensor(CoordinatorEntity, SensorEntity):
    """Sensor for daily order status."""
    
    def __init__(
        self,
        coordinator: BessaLunchDataUpdateCoordinator,
        entry: ConfigEntry,
        days_ahead: int,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._days_ahead = days_ahead
        
        # Create descriptive name based on days ahead
        if days_ahead == 0:
            day_name = "Today"
        elif days_ahead == 1:
            day_name = "Tomorrow"
        else:
            day_name = f"Day +{days_ahead}"
        
        self._attr_name = f"Order {day_name}"
        self._attr_unique_id = f"{entry.entry_id}_order_day_{days_ahead}"
        self._attr_has_entity_name = True
    
    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=DEVICE_NAME,
            manufacturer=DEVICE_MANUFACTURER,
            model=DEVICE_MODEL,
            entry_type="service",
        )
    
    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        order = self._get_order_for_day()
        if not order:
            return "No order"
        
        # Get meal names from order
        items = order.get("items", [])
        if items:
            item_names = [item.get("name", "") for item in items]
            return ", ".join(filter(None, item_names)) or "Ordered"
        return "Ordered"
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        order = self._get_order_for_day()
        target_date = self._get_target_date()
        
        attrs = {
            "date": target_date,
            "day_name": self._get_day_name(),
            "has_order": order is not None,
        }
        
        if order:
            # Extract items (actual meals)
            items = order.get("items", [])
            meals = []
            total_price = 0
            
            for item in items:
                meal_info = {
                    "name": item.get("name"),
                    "description": item.get("description"),
                    "price": float(item.get("price", 0)),
                    "quantity": item.get("amount", 1),
                }
                meals.append(meal_info)
                total_price += float(item.get("price", 0)) * item.get("amount", 1)
            
            # Get order state
            states = order.get("states", [])
            current_state = states[0] if states else {}
            order_state_code = order.get("order_state")
            
            # Extract date from "date" field
            order_date = order.get("date", "")
            pickup_time = order_date[11:16] if len(order_date) > 11 else None
            
            attrs.update({
                "order_id": order.get("id"),
                "meals": meals,
                "total_price": round(total_price, 2),
                "state": current_state.get("state"),
                "state_name": self._get_state_name(current_state.get("state")),
                "order_state": ORDER_STATES.get(order_state_code, "Unknown"),
                "order_state_code": order_state_code,
                "pickup_time": pickup_time,
                "pickup_code": order.get("pickup_code"),
                "number": order.get("number"),
                "currency": order.get("currency", "EUR"),
                "payment_method": order.get("payment_method"),
            })
        
        return attrs
    
    def _get_target_date(self) -> str:
        """Get the target date for this sensor."""
        target = datetime.now().date() + timedelta(days=self._days_ahead)
        return target.strftime("%Y-%m-%d")
    
    def _get_day_name(self) -> str:
        """Get the day name for this sensor."""
        target = datetime.now().date() + timedelta(days=self._days_ahead)
        if self._days_ahead == 0:
            return "Today"
        elif self._days_ahead == 1:
            return "Tomorrow"
        else:
            return target.strftime("%A")
    
    def _get_order_for_day(self) -> dict[str, Any] | None:
        """Get order data for the specific day."""
        if not self.coordinator.data:
            return None
        
        target_date = self._get_target_date()
        orders = self.coordinator.data.get("orders", [])
        
        # Find order for this specific date
        for order in orders:
            order_date = order.get("date", "")[:10]
            if order_date == target_date:
                # Check if not cancelled (state 9)
                states = order.get("states", [])
                if states and states[0].get("state") != 9:
                    return order
        
        return None
    
    def _get_state_name(self, state: int | None) -> str:
        """Convert state number to human-readable name."""
        state_names = {
            4: "Ordered",
            5: "Confirmed",
            9: "Cancelled",
        }
        return state_names.get(state, f"State {state}" if state else "Unknown")
    
    @property
    def icon(self) -> str:
        """Return the icon of the sensor."""
        if self.state != "No order":
            return "mdi:checkbox-marked-circle"
        return "mdi:checkbox-blank-circle-outline"


class BessaLunchDailyMenuSensor(CoordinatorEntity, SensorEntity):
    """Sensor for daily available menu."""
    
    def __init__(
        self,
        coordinator: BessaLunchDataUpdateCoordinator,
        entry: ConfigEntry,
        days_ahead: int,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._days_ahead = days_ahead
        
        # Create descriptive name based on days ahead
        if days_ahead == 0:
            day_name = "Today"
        elif days_ahead == 1:
            day_name = "Tomorrow"
        else:
            day_name = f"Day +{days_ahead}"
        
        self._attr_name = f"Menu {day_name}"
        self._attr_unique_id = f"{entry.entry_id}_menu_day_{days_ahead}"
        self._attr_has_entity_name = True
    
    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=DEVICE_NAME,
            manufacturer=DEVICE_MANUFACTURER,
            model=DEVICE_MODEL,
            entry_type="service",
        )
    
    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        menu_data = self._get_menu_for_day()
        if not menu_data:
            return "No menu available"
        
        # Return count of available meals
        return f"{len(menu_data)} meals available"
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        menu_data = self._get_menu_for_day()
        target_date = self._get_target_date()
        
        attrs = {
            "date": target_date,
            "day_name": self._get_day_name(),
            "meal_count": len(menu_data) if menu_data else 0,
        }
        
        if menu_data:
            # Parse and format meals with availability
            meals = []
            meal_names = []
            
            for item in menu_data:
                available = item.get("available")
                meal = {
                    "name": item.get("name", ""),
                    "description": item.get("description", ""),
                    "price": float(item.get("price", 0)),
                    "available": available,
                    "category": item.get("category", ""),
                    "allergens": item.get("allergens", ""),
                }
                meals.append(meal)
                
                # Add availability info to name if present
                meal_name = item.get("name", "")
                if available is not None:
                    meal_name = f"{meal_name} ({available} left)"
                meal_names.append(meal_name)
            
            attrs.update({
                "meals": meals,
                "meal_names": meal_names,
            })
        else:
            attrs.update({
                "meals": [],
                "meal_names": [],
            })
        
        return attrs
    
    def _get_target_date(self) -> str:
        """Get the target date for this sensor."""
        target = datetime.now().date() + timedelta(days=self._days_ahead)
        return target.strftime("%Y-%m-%d")
    
    def _get_day_name(self) -> str:
        """Get the day name for this sensor."""
        target = datetime.now().date() + timedelta(days=self._days_ahead)
        if self._days_ahead == 0:
            return "Today"
        elif self._days_ahead == 1:
            return "Tomorrow"
        else:
            return target.strftime("%A")
    
    def _get_menu_for_day(self) -> list[dict[str, Any]]:
        """Get menu data for the specific day."""
        if not self.coordinator.data:
            return []
        
        target_date = self._get_target_date()
        menu_key = f"menu_{target_date}"
        
        return self.coordinator.data.get(menu_key, [])
    
    @property
    def icon(self) -> str:
        """Return the icon of the sensor."""
        return "mdi:food-variant"



class BessaLunchTodayOrderSensor(CoordinatorEntity, SensorEntity):
    """Sensor for today's lunch order."""
    
    def __init__(
        self,
        coordinator: BessaLunchDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_name = "Today's Order"
        self._attr_unique_id = f"{entry.entry_id}_today_order"
        self._attr_has_entity_name = True
    
    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=DEVICE_NAME,
            manufacturer=DEVICE_MANUFACTURER,
            model=DEVICE_MODEL,
            entry_type="service",
        )
    
    @property
    def state(self) -> str | None:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return "No order"
        
        # Extract order information from the API response
        orders = self.coordinator.data.get("orders", [])
        if orders:
            order = orders[0]
            # Get meal information from items array
            items = order.get("items", [])
            if items:
                item_names = [item.get("name", "") for item in items]
                return ", ".join(filter(None, item_names)) or "Order placed"
            return "Order placed"
        return "No order"
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        if not self.coordinator.data:
            return {}
        
        orders = self.coordinator.data.get("orders", [])
        if orders:
            order = orders[0]
            # Extract items (actual meals)
            items = order.get("items", [])
            meals = []
            total_price = 0
            
            for item in items:
                meal_info = {
                    "name": item.get("name"),
                    "description": item.get("description"),
                    "price": float(item.get("price", 0)),
                    "quantity": item.get("amount", 1),
                }
                meals.append(meal_info)
                total_price += float(item.get("price", 0)) * item.get("amount", 1)
            
            # Get order state
            states = order.get("states", [])
            current_state = states[0] if states else {}
            
            # Extract date from "date" field
            order_date = order.get("date", "")
            pickup_date = order_date[:10] if order_date else None
            pickup_time = order_date[11:16] if len(order_date) > 11 else None
            
            return {
                "order_id": order.get("id"),
                "venue": order.get("venue"),
                "meals": meals,
                "total_price": round(total_price, 2),
                "state": current_state.get("state"),
                "state_name": self._get_state_name(current_state.get("state")),
                "order_timestamp": current_state.get("timestamp"),
                "pickup_date": pickup_date,
                "pickup_time": pickup_time,
                "pickup_code": order.get("pickup_code"),
                "number": order.get("number"),
                "customer_name": f"{order.get('customer', {}).get('first_name', '')} {order.get('customer', {}).get('last_name', '')}".strip(),
                "preorder": order.get("preorder", False),
                "payment_method": order.get("payment_method"),
            }
        return {}
    
    def _get_state_name(self, state: int | None) -> str:
        """Convert state number to human-readable name."""
        state_names = {
            4: "Ordered",
            5: "Confirmed",
            9: "Cancelled",
            # Add more states as you discover them
        }
        return state_names.get(state, f"State {state}" if state else "Unknown")
    
    @property
    def icon(self) -> str:
        """Return the icon of the sensor."""
        return "mdi:food"


class BessaLunchOrderStatusSensor(CoordinatorEntity, SensorEntity):
    """Sensor for order status."""
    
    def __init__(
        self,
        coordinator: BessaLunchDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_name = "Order Status"
        self._attr_unique_id = f"{entry.entry_id}_order_status"
        self._attr_has_entity_name = True
    
    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=DEVICE_NAME,
            manufacturer=DEVICE_MANUFACTURER,
            model=DEVICE_MODEL,
            entry_type="service",
        )
    
    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return "unknown"
        
        orders = self.coordinator.data.get("orders", [])
        if orders:
            return "ordered"
        return "no_order"
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        if not self.coordinator.data:
            return {}
        
        orders = self.coordinator.data.get("orders", [])
        return {
            "order_count": len(orders),
            "has_order": len(orders) > 0,
            "last_update": datetime.now().isoformat(),
        }
    
    @property
    def icon(self) -> str:
        """Return the icon of the sensor."""
        if self.state == "ordered":
            return "mdi:checkbox-marked-circle"
        return "mdi:checkbox-blank-circle-outline"


class BessaLunchMenuSensor(CoordinatorEntity, SensorEntity):
    """Sensor for daily menu."""
    
    def __init__(
        self,
        coordinator: BessaLunchDataUpdateCoordinator,
        entry: ConfigEntry,
        days_ahead: int,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._days_ahead = days_ahead
        
        # Create descriptive name based on days ahead
        if days_ahead == 0:
            day_name = "Today"
        elif days_ahead == 1:
            day_name = "Tomorrow"
        else:
            day_name = f"Day +{days_ahead}"
        
        self._attr_name = f"Menu {day_name}"
        self._attr_unique_id = f"{entry.entry_id}_menu_day_{days_ahead}"
        self._attr_has_entity_name = True
    
    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=DEVICE_NAME,
            manufacturer=DEVICE_MANUFACTURER,
            model=DEVICE_MODEL,
            entry_type="service",
        )
    
    @property
    def state(self) -> str | None:
        """Return the state of the sensor."""
        menu_data = self._get_menu_for_day()
        if not menu_data:
            return "No menu available"
        
        # Count available meals
        meal_count = len(menu_data)
        return f"{meal_count} meals available"
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        menu_data = self._get_menu_for_day()
        if not menu_data:
            return {
                "date": self._get_target_date(),
                "meals": [],
            }
        
        # Parse and format meals
        meals = []
        for item in menu_data:
            meal = {
                "name": item.get("name", ""),
                "description": item.get("description", ""),
                "price": float(item.get("price", 0)),
            }
            meals.append(meal)
        
        return {
            "date": self._get_target_date(),
            "day_name": self._get_day_name(),
            "meals": meals,
            "meal_count": len(meals),
        }
    
    def _get_target_date(self) -> str:
        """Get the target date for this sensor."""
        target = datetime.now().date() + timedelta(days=self._days_ahead)
        return target.strftime("%Y-%m-%d")
    
    def _get_day_name(self) -> str:
        """Get the day name for this sensor."""
        target = datetime.now().date() + timedelta(days=self._days_ahead)
        if self._days_ahead == 0:
            return "Today"
        elif self._days_ahead == 1:
            return "Tomorrow"
        else:
            return target.strftime("%A")
    
    def _get_menu_for_day(self) -> list[dict[str, Any]]:
        """Get menu data for the specific day."""
        if not self.coordinator.data:
            return []
        
        target_date = self._get_target_date()
        menu_key = f"menu_{target_date}"
        
        return self.coordinator.data.get(menu_key, [])
    
    @property
    def icon(self) -> str:
        """Return the icon of the sensor."""
        return "mdi:food-variant"
