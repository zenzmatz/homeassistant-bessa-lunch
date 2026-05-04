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

import re

from . import BessaLunchDataUpdateCoordinator
from .const import DOMAIN, DEVICE_NAME, DEVICE_MANUFACTURER, DEVICE_MODEL, ORDER_STATES

_ALLERGEN_RE = re.compile(
    r'(?:(?<!\w)[/(]?[A-Z]{2,10}\)?(?!\w)|\([A-Z]{1,10}(?:/[A-Z]{1,10})*\)|/[A-Z]\))'
)
_MERGED_BILINGUAL_BOUNDARY_RE = re.compile(r'(?<=[a-z])\s+(?=[A-ZÄÖÜ])')

# Keywords that identify an M6-style combo menu (soup + small salad + dessert placeholder).
_M6_KEYWORDS = ("kleiner salat", "kleines salat", "suppe / soup", "soup  salat", "salat / salad")

_EMPTY_COURSES: dict[str, str | None] = {
    "soup_de": None, "soup_en": None,
    "main_dish_de": None, "main_dish_en": None,
    "dessert_de": None, "dessert_en": None,
}


def _is_ascii_only(text: str) -> bool:
    return all(ord(c) < 128 for c in text)


def _is_m6_combo(description: str) -> bool:
    """Return True for M6-style combo menus (soup + small salad + dessert placeholder).

    The M6 description is always a generic label like:
      'Suppe / Soup  Salat / Salad  Dessert'
      'kleiner Salat mit Suppe und Dessert / small salad with soup and dessert'
    rather than an actual dish description.
    """
    d = description.lower()
    return any(kw in d for kw in _M6_KEYWORDS) and "dessert" in d


def _split_bilingual(text: str) -> tuple[str, str | None]:
    """Split 'German / English' into (de, en). Returns (text, None) if no slash."""
    idx = text.find("/")
    if idx == -1:
        return text.strip(), None
    return text[:idx].strip(), text[idx + 1:].strip() or None


def _parse_single_bilingual_main(description: str) -> dict[str, str | None] | None:
    """Parse a single-course bilingual menu with no allergen markers.

    Friday menus sometimes arrive as just "DE / EN" without any soup/dessert
    structure or allergen separators. Map those directly to the main dish.
    """
    if _is_m6_combo(description) or _ALLERGEN_RE.search(description) or description.count("/") != 1:
        return None

    de, en = _split_bilingual(description)
    if not de or not en:
        return None

    result = dict(_EMPTY_COURSES)
    result["main_dish_de"] = de
    result["main_dish_en"] = en
    return result


def _split_merged_bilingual_segment(
    segment: str,
) -> tuple[tuple[str, str | None], tuple[str, str | None]] | None:
    """Split a merged "DE / EN DE / EN" segment into two bilingual courses.

    Some Ginko menus miss the allergen separator between soup and main, leaving
    a single segment with two slashes, e.g.:
      "Karfiolcremesuppe / Cauliflower cream soup Brokkoli- Mandelrisotto / ..."
    """
    if segment.count("/") != 2:
        return None

    first_slash = segment.find("/")
    second_slash = segment.rfind("/")
    first_de = segment[:first_slash].strip()
    middle = segment[first_slash + 1:second_slash].strip()
    second_en = segment[second_slash + 1:].strip()
    boundary = _MERGED_BILINGUAL_BOUNDARY_RE.search(middle)

    if not first_de or not second_en or not boundary:
        return None

    first_en = middle[:boundary.start()].strip()
    second_de = middle[boundary.end():].strip()
    if not first_en or not second_de:
        return None

    return (first_de, first_en), (second_de, second_en)


def _parse_menu_description(description: str) -> dict[str, str | None]:
    """Split a combined Bessa menu description into course attributes.

    Handles three encoding formats used by the canteen:

    Format A – bilingual per course with allergen codes as delimiters:
        'DE soup / EN soup(ALLERGENS) DE main / EN main(ALLERGENS) DE dessert / EN dessert(ALLERGENS)'

    Format B – all-German courses + English block appended at end:
        'DE soup(A) DE main(A) DE dessert(A) en soup, en main, en dessert'

    Format C – inline English soup name leaks into segment after soup's allergen code:
        'DE soup(ALLERGENS) EN soup, DE main(ALLERGENS) DE dessert(ALLERGENS) EN main, EN dessert'

    Falls back to German text when no English translation is available.
    """
    if not description:
        return dict(_EMPTY_COURSES)

    single_bilingual_main = _parse_single_bilingual_main(description)
    if single_bilingual_main is not None:
        return single_bilingual_main

    # Step 1: split by allergen codes to get raw segments
    raw_segs: list[str] = []
    last_pos = 0
    for m in _ALLERGEN_RE.finditer(description):
        seg = description[last_pos:m.start()].strip().rstrip("(/").strip()
        if seg:
            raw_segs.append(seg)
        last_pos = m.end()
    tail = description[last_pos:].strip()

    # Step 2: build (de, en) pairs per course
    de_parts: list[str] = []
    en_parts: list[str | None] = []

    for i, seg in enumerate(raw_segs):
        merged_courses = _split_merged_bilingual_segment(seg)
        if merged_courses is not None:
            for de, en in merged_courses:
                de_parts.append(de)
                en_parts.append(en)
            continue

        # For non-first segments: try inline English-prefix detection FIRST.
        # Pattern: "english phrase, German Dish Name" where the english prefix
        # leaked from the previous segment's allergen boundary.
        # Heuristic: prefix is all-lowercase ASCII (English), suffix starts uppercase (German noun).
        if i > 0:
            ci = seg.find(", ")
            if ci > 0:
                prefix = seg[:ci].strip()
                suffix = seg[ci + 2:].strip()
                if (
                    _is_ascii_only(prefix)
                    and prefix
                    and prefix[0].islower()
                    and suffix
                    and suffix[0].isupper()
                    and len(prefix.split()) <= 7
                ):
                    # prefix = English name for the previous course
                    if en_parts and en_parts[-1] is None:
                        en_parts[-1] = prefix
                    # suffix may itself be bilingual (e.g., "DE main / EN main")
                    if "/" in suffix:
                        de, en = _split_bilingual(suffix)
                        de_parts.append(de)
                        en_parts.append(en)
                    else:
                        de_parts.append(suffix)
                        en_parts.append(None)
                    continue

        # Default: bilingual slash split or plain German segment
        if "/" in seg:
            de, en = _split_bilingual(seg)
            de_parts.append(de)
            en_parts.append(en)
        else:
            de_parts.append(seg)
            en_parts.append(None)

    # Step 3: collapse when ingredient-level allergen codes produced > 3 segments.
    # Keep first (soup) and last (dessert), merge everything in between as main_dish.
    if len(de_parts) > 3:
        de_parts = [de_parts[0], " ".join(de_parts[1:-1]), de_parts[-1]]
        en_first = en_parts[0]
        en_middle = next((e for e in en_parts[1:-1] if e), None)
        en_last = en_parts[-1]
        en_parts = [en_first, en_middle, en_last]

    # Step 4: assign trailing English block to courses that still lack translation.
    # Prefer semicolons as separator (courses with commas in names won't be split).
    if tail and de_parts:
        if ";" in tail:
            tail_parts = [p.strip() for p in tail.split(";") if p.strip()]
        else:
            tail_parts = [p.strip() for p in tail.split(", ") if p.strip()]
        j = 0
        for i in range(len(de_parts)):
            if en_parts[i] is None and j < len(tail_parts):
                en_parts[i] = tail_parts[j]
                j += 1

    # Step 5: map first three courses to soup / main_dish / dessert.
    # Fall back to German when no English translation was found.
    keys = ["soup", "main_dish", "dessert"]
    result: dict[str, str | None] = {}
    for i, key in enumerate(keys):
        if i < len(de_parts):
            de = de_parts[i]
            en = en_parts[i] if en_parts[i] else de
            result[f"{key}_de"] = de
            result[f"{key}_en"] = en
        else:
            result[f"{key}_de"] = None
            result[f"{key}_en"] = None
    return result


def _fill_m6_from_reference(
    items: list[dict[str, Any]],
    parsed: list[dict[str, str | None]],
) -> list[dict[str, str | None]]:
    """For M6 combo items, substitute soup/dessert from the first non-M6 reference item.

    M6 is always: same soup as M1/M2/M3/M5 + small salad + same dessert as M1.
    The M6 description is a generic placeholder and carries no real course info.
    """
    # Find the reference: first non-M6 item that has a valid soup
    ref_soup_de = ref_soup_en = ref_dessert_de = ref_dessert_en = None
    for item, courses in zip(items, parsed):
        if not _is_m6_combo(item.get("description", "")) and courses.get("soup_de"):
            ref_soup_de = courses["soup_de"]
            ref_soup_en = courses["soup_en"] or ref_soup_de
            ref_dessert_de = courses["dessert_de"]
            ref_dessert_en = courses["dessert_en"] or ref_dessert_de
            break

    result = []
    for item, courses in zip(items, parsed):
        if _is_m6_combo(item.get("description", "")):
            updated = dict(courses)
            if ref_soup_de:
                updated["soup_de"] = ref_soup_de
                updated["soup_en"] = ref_soup_en
            if ref_dessert_de:
                updated["dessert_de"] = ref_dessert_de
                updated["dessert_en"] = ref_dessert_en
            updated["main_dish_de"] = "Kleiner Salat"
            updated["main_dish_en"] = "Small salad"
            result.append(updated)
        else:
            result.append(courses)
    return result


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
            
            # Parse courses from the order item's description.
            # If the ordered item is an M6 combo (soup + salad + dessert),
            # substitute the real soup/dessert from the day's full menu.
            combined_description = ""
            if len(items) == 1:
                combined_description = items[0].get("description") or items[0].get("name", "")
            else:
                combined_description = " ".join(
                    item.get("description") or item.get("name", "") for item in items
                )

            courses = _parse_menu_description(combined_description)
            if _is_m6_combo(combined_description):
                menu_items = self._get_menu_for_day()
                if menu_items:
                    menu_parsed = [_parse_menu_description(m.get("description", "")) for m in menu_items]
                    filled = _fill_m6_from_reference(menu_items, menu_parsed)
                    for mitem, mc in zip(menu_items, filled):
                        if _is_m6_combo(mitem.get("description", "")):
                            courses = mc
                            break

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
                "menu": combined_description,
                "soup_de": courses["soup_de"],
                "soup_en": courses["soup_en"],
                "main_dish_de": courses["main_dish_de"],
                "main_dish_en": courses["main_dish_en"],
                "dessert_de": courses["dessert_de"],
                "dessert_en": courses["dessert_en"],
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
    
    def _get_menu_for_day(self) -> list[dict[str, Any]]:
        """Get menu data for the specific day."""
        if not self.coordinator.data:
            return []
        target_date = self._get_target_date()
        return self.coordinator.data.get(f"menu_{target_date}", [])

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
            
            # Parse each menu item individually, then apply M6 substitution.
            all_parsed = [_parse_menu_description(item.get("description", "")) for item in menu_data]
            all_parsed = _fill_m6_from_reference(menu_data, all_parsed)

            # Enrich each meal dict with its own parsed courses.
            for meal, parsed in zip(meals, all_parsed):
                meal["soup_de"] = parsed["soup_de"]
                meal["soup_en"] = parsed["soup_en"]
                meal["main_dish_de"] = parsed["main_dish_de"]
                meal["main_dish_en"] = parsed["main_dish_en"]
                meal["dessert_de"] = parsed["dessert_de"]
                meal["dessert_en"] = parsed["dessert_en"]

            # Top-level course attributes = first non-M6 item (M1-style primary menu).
            courses = all_parsed[0] if all_parsed else dict(_EMPTY_COURSES)
            for item, parsed in zip(menu_data, all_parsed):
                if not _is_m6_combo(item.get("description", "")):
                    courses = parsed
                    break

            combined = menu_data[0].get("description", "") if menu_data else ""

            attrs.update({
                "meals": meals,
                "meal_names": meal_names,
                "menu": combined,
                "soup_de": courses["soup_de"],
                "soup_en": courses["soup_en"],
                "main_dish_de": courses["main_dish_de"],
                "main_dish_en": courses["main_dish_en"],
                "dessert_de": courses["dessert_de"],
                "dessert_en": courses["dessert_en"],
            })
        else:
            attrs.update({
                "meals": [],
                "meal_names": [],
                "menu": None,
                "soup_de": None, "soup_en": None,
                "main_dish_de": None, "main_dish_en": None,
                "dessert_de": None, "dessert_en": None,
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
