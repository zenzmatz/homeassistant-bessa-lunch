# Bessa Lunch Orders - Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)

Custom Home Assistant integration for checking lunch orders from the Bessa app (your company/venue).

**✅ Status: Fully Working!** Successfully tested with your company/venue Bessa system.

## Features

- 📅 **7-Day View**: Order and menu sensors for today through 6 days ahead
- 🍽️ **Menu Availability**: Shows how many portions are left for each meal
- 📊 **Order States**: Displays human-readable order status (Preparing, Ready, Done, etc.)
- 🔄 **Auto-Update**: Polls every 30 minutes for fresh data
- 🎯 **Efficient**: Server-side filtering and pagination for optimal performance
- 💰 **Price Tracking**: Full meal details with prices and allergens
- 🏢 **Device Architecture**: Single device with 14 entities (7 orders + 7 menus)

## Installation

### Via HACS (Recommended)

1. Open HACS in Home Assistant
2. Click on "Integrations"
3. Click the three dots in the top right corner
4. Select "Custom repositories"
5. Add this repository URL: `https://github.com/zenzmatz/homeassistant-bessa-lunch`
6. Category: `Integration`
7. Click "Add"
8. Find "Bessa Lunch Orders" in HACS and install it
9. Restart Home Assistant
10. Go to Settings → Devices & Services → Add Integration
11. Search for "Bessa Lunch" and configure with your credentials

### Manual Installation

1. Copy the `custom_components/bessa_lunch` folder to your Home Assistant's `config/custom_components/` directory
2. Restart Home Assistant
3. Go to Settings → Devices & Services → Add Integration
4. Search for "Bessa Lunch" and configure with your credentials

## Configuration

The integration is configured through the Home Assistant UI:

1. Go to **Settings** → **Devices & Services**
2. Click **Add Integration**
3. Search for **Bessa Lunch**
4. Enter your Bessa email and password (e.g., `company-1234@bessa.app`)

## Entities Created

The integration creates 14 entities under a single "Bessa Lunch" device:

### Order Sensors (7 entities)
- **Order Today** - Today's lunch order
- **Order Tomorrow** - Tomorrow's lunch order
- **Order Day +2** through **Order Day +6** - Future orders

**State**: Meal names or "No order"

**Attributes**:
- `order_id`: Order ID number
- `order_state`: Human-readable state (e.g., "Preparing", "Ready", "Done")
- `order_state_code`: Numeric state code (1-13)
- `meals`: List of ordered meals with details
- `total_price`: Total order amount
- `pickup_code`: Pickup code for collection
- `pickup_time`: Expected pickup time
- `currency`: Currency code (EUR)
- `payment_method`: Payment method used

### Menu Sensors (7 entities)
- **Menu Today** - Today's available menu
- **Menu Tomorrow** - Tomorrow's available menu
- **Menu Day +2** through **Menu Day +6** - Future menus

**State**: "X meals available" (e.g., "7 meals available")

**Attributes**:
- `meal_count`: Number of available meals
- `meal_names`: List of meals with availability (e.g., "M1F Herzhaftes (247 left)")
- `meals`: Detailed meal information including:
  - `name`: Meal name
  - `description`: Full meal description
  - `price`: Price in EUR
  - `available`: Stock count
  - `category`: Menu category
  - `allergens`: Allergen codes

## Example Automations

### Notify when order is ready

```yaml
automation:
  - alias: "Notify when order is ready"
    trigger:
      - platform: state
        entity_id: sensor.bessa_lunch_order_today
        attribute: order_state
        to: "Ready"
    action:
      - service: notify.mobile_app
        data:
          title: "🍽️ Lunch is Ready!"
          message: "Your {{ state_attr('sensor.bessa_lunch_order_today', 'pickup_code') }} order is ready for pickup"

### Check tomorrow's menu availability

```yaml
automation:
  - alias: "Check tomorrow's menu availability"
    trigger:
      - platform: time
        at: "09:00:00"
    condition:
      - condition: template
        value_template: >
          {{ state_attr('sensor.bessa_lunch_menu_tomorrow', 'meal_count') | int > 0 }}
    action:
      - service: notify.mobile_app
        data:
          title: "📋 Tomorrow's Menu"
          message: >
            {{ state_attr('sensor.bessa_lunch_menu_tomorrow', 'meal_count') }} meals available:
            {% for meal in state_attr('sensor.bessa_lunch_menu_tomorrow', 'meal_names')[:3] %}
            - {{ meal }}
            {% endfor %}
```

### Alert if no lunch ordered by 10 AM

```yaml
automation:
  - alias: "Notify if no lunch ordered"
    trigger:
      - platform: time
        at: "10:00:00"
    condition:
      - condition: state
        entity_id: sensor.bessa_lunch_order_today
        state: "No order"
    action:
      - service: notify.mobile_app
        data:
          title: "Lunch Reminder"
          message: "You haven't ordered lunch for today!"
```

### Display lunch info on dashboard

```yaml
type: entities
entities:
  - entity: sensor.bessa_lunch_order_today
    name: Today's Lunch
  - entity: sensor.bessa_lunch_menu_today
    name: Today's Menu
  - entity: sensor.bessa_lunch_order_tomorrow
    name: Tomorrow's Order
```

## Order States

The integration displays these order states:

| Code | State | Description |
|------|-------|-------------|
| 1 | New | Order just created |
| 2 | Payment Processing | Payment being processed |
| 3 | Transmittable | Ready to be sent to kitchen |
| 4 | Transmitted | Sent to kitchen system |
| 5 | Accepted | Kitchen accepted the order |
| 6 | Preparing | Being prepared |
| 7 | Ready | Ready for pickup |
| 8 | Done | Order completed |
| 9 | Cancelled | Order cancelled |
| 10 | Rejected | Order rejected |
| 11 | Failed | Order failed |
| 12 | Expired | Order expired |
| 13 | Pre-ordered | Scheduled for future |

## Standalone CLI Tool

A standalone Python script (`bessa_lunch.py`) is also available for command-line usage:

```bash
# Show today's orders
python3 bessa_lunch.py orders -e your-email@bessa.app

# Show tomorrow's menu
python3 bessa_lunch.py menu --tomorrow -e your-email@bessa.app

# Show menu for specific date
python3 bessa_lunch.py menu --date 2025-12-15 -e your-email@bessa.app
```

The CLI tool shows:
- 🟢 Green indicators for available meals with stock counts
- 🔴 Red "Sold out" indicators for unavailable meals
- Meal categories and descriptions
- Prices and allergen information

## Technical Details

- **Update Interval**: 30 minutes
- **API Base**: `https://api.bessa.app/v1/`
- **Venue**: Your venue (configure during setup)
- **Menu Type**: Canteen menu (Type: 7)
- **Authentication**: Token-based (REST API)
- **Home Assistant**: 2024.1.0+
- **Python**: 3.11+
- **Dependencies**: aiohttp>=3.9.0

### API Optimizations
- Server-side filtering by venue and date range
- Excludes deleted orders
- Automatic pagination handling
- Results sorted by date (newest first)
- Efficient availability tracking

## Troubleshooting

### No menu data showing
- Check that you're using the correct Bessa credentials
- Verify the venue has published menus for the requested dates
- Check Home Assistant logs for authentication errors

### Orders not updating
- The integration polls every 30 minutes - wait for the next update cycle
- Force a refresh by reloading the integration in Settings → Devices & Services

### Authentication failed
- Verify your email and password are correct
- Some accounts may require special permissions - contact Bessa support

## Development

### Project Structure

```
custom_components/bessa_lunch/
├── __init__.py          # Integration setup and coordinator
├── manifest.json        # Integration metadata
├── const.py            # Constants and configuration
├── config_flow.py      # Configuration UI flow
├── bessa_api.py        # API client for Bessa
├── sensor.py           # Sensor entities
├── types.py            # Pydantic models (optional)
└── strings.json        # UI strings and translations
```

### Testing Locally

1. Copy the integration to your Home Assistant config:
   ```bash
   cp -r custom_components/bessa_lunch /path/to/homeassistant/config/custom_components/
   ```

2. Restart Home Assistant

3. Check logs for any errors:
   ```bash
   tail -f /path/to/homeassistant/home-assistant.log | grep bessa_lunch
   ```

### Debugging

Enable debug logging by adding to `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.bessa_lunch: debug
```

## Support

For issues, feature requests, or contributions, please visit the [GitHub repository](https://github.com/zenzmatz/homeassistant-bessa-lunch/issues).

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Test your changes thoroughly
4. Submit a pull request

## License

MIT License - See LICENSE file for details.

## Credits

Created for the your company/venue community. This is an unofficial integration and is not affiliated with Bessa GmbH.

## Disclaimer

This is an unofficial integration and is not affiliated with or endorsed by Bessa.
