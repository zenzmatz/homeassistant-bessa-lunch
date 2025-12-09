"""Constants for the Bessa Lunch integration."""

DOMAIN = "bessa_lunch"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"

# Bessa API URLs
BESSA_BASE_URL = "https://api.bessa.app"
BESSA_LOGIN_URL = f"{BESSA_BASE_URL}/v1/auth/login/"
BESSA_ORDERS_URL = f"{BESSA_BASE_URL}/v1/user/orders"

# Bessa API configuration
VENUE_ID = VENUE_ID  # Configurable venue
MENU_TYPE = 7   # Canteen menu type

# Device info constants
DEVICE_NAME = "Bessa Lunch"
DEVICE_MANUFACTURER = "Bessa"
DEVICE_MODEL = "Lunch Order System"

# Order state mapping based on official API documentation
ORDER_STATES = {
    1: "New",
    2: "Payment Processing",
    3: "Transmittable",
    4: "Transmitted",
    5: "Accepted",
    6: "Preparing",
    7: "Ready",
    8: "Done",
    9: "Cancelled",
    10: "Rejected",
    11: "Failed",
    12: "Expired",
    13: "Pre-ordered"
}

