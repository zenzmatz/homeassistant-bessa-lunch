# Bessa Lunch Order Integration for Home Assistant

A custom Home Assistant integration to check your lunch orders from the Bessa app (web.bessa.app/your-company/).

**✅ Status: Fully Working!** Successfully tested with your company/venue Bessa system.

## Features

- 📅 Check if you have a lunch order for today
- 🍽️ See what meal you ordered
- 📊 Binary sensor showing order status
- 🔄 Automatic updates every 30 minutes
- 💰 Price and meal details in attributes
- ⏰ Order timestamp tracking

## Quick Start

**🚀 [See INSTALLATION.md for complete setup instructions](INSTALLATION.md)**

1. Copy `custom_components/bessa_lunch` to your Home Assistant `config/custom_components/`
2. Restart Home Assistant
3. Add integration via UI (Settings → Devices & Services → Add Integration)
4. Enter your Bessa credentials (email format: `knapp-xxxx@bessa.app`)

## Installation

### Manual Installation

1. Copy the `custom_components/bessa_lunch` folder to your Home Assistant `custom_components` directory
2. Restart Home Assistant
3. Go to Settings → Devices & Services → Add Integration
4. Search for "Bessa Lunch Orders"
5. Enter your Bessa credentials

### HACS Installation (Future)

This integration is not yet available through HACS.

## Configuration

The integration is configured through the Home Assistant UI:

1. Go to **Settings** → **Devices & Services**
2. Click **Add Integration**
3. Search for **Bessa Lunch Orders**
4. Enter your credentials:
   - Username/Email: Your Bessa login
   - Password: Your Bessa password

## Sensors

### Bessa Lunch Today's Order

Shows what meal you ordered for today.

**State**: Meal name or "No order"

**Attributes**:
- `order_id`: Unique order identifier
- `meal_name`: Name of the meal
- `meal_description`: Description of the meal
- `price`: Price of the meal
- `pickup_time`: When to pick up the order
- `order_date`: Date of the order

### Bessa Lunch Order Status

Binary status of whether you have an order for today.

**State**: `ordered` or `no_order`

**Attributes**:
- `order_count`: Number of orders for today
- `has_order`: Boolean indicating if an order exists
- `last_update`: Last time data was fetched

## Automation Examples

### Notify when no lunch is ordered

```yaml
automation:
  - alias: "Notify if no lunch ordered"
    trigger:
      - platform: time
        at: "09:00:00"
    condition:
      - condition: state
        entity_id: sensor.bessa_lunch_order_status
        state: "no_order"
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
  - entity: sensor.bessa_lunch_today_s_order
    name: Today's Lunch
  - entity: sensor.bessa_lunch_order_status
    name: Order Status
```

## Important Notes

⚠️ **API Reverse Engineering Required**

This integration includes placeholder code for the Bessa API. You'll need to:

1. Open your browser's Developer Tools (F12)
2. Go to the Network tab
3. Log into web.bessa.app/your-company/
4. Observe the API calls to understand:
   - Authentication endpoint and method
   - Token/session handling
   - Orders API endpoint
   - Response structure

**📖 See [FIND_API_GUIDE.md](FIND_API_GUIDE.md) for detailed step-by-step instructions!**

### Quick Test Without Home Assistant

You can test the API connection independently:

```bash
# Install dependencies
pip install aiohttp

# Run the test script
python3 test_bessa_standalone.py
```

This will try various common API patterns and show you what's working. However, you'll still need to use browser DevTools to find the exact endpoints.

Update the `bessa_api.py` file with the actual API details once you've found them.

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

## Troubleshooting

### Authentication Fails

- Verify your credentials are correct
- Check the `bessa_api.py` file has the correct login endpoint
- Look at Home Assistant logs for error messages

### No Data Showing

- Enable debug logging
- Check if the API endpoints are correct
- Verify the response parsing matches the actual API structure

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Test your changes thoroughly
4. Submit a pull request

## License

MIT License - See LICENSE file for details

## Credits

Created by @zenzmatz for personal use with the your company/venue Bessa system.

## Disclaimer

This is an unofficial integration and is not affiliated with or endorsed by Bessa.
