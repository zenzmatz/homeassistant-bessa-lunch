# Bessa Lunch Orders

Check your daily lunch orders and menus from the Bessa app (your company/venue) directly in Home Assistant.

## Features

✅ **7-Day View** - Order and menu sensors for today through 6 days ahead  
✅ **Menu Availability** - Shows how many portions are left for each meal  
✅ **Order States** - Human-readable status (Preparing, Ready, Done, etc.)  
✅ **Auto-Update** - Polls every 30 minutes for fresh data  

## Quick Start

1. Add your Bessa credentials (e.g., `company-1234@bessa.app`)
2. 14 entities will be created (7 order + 7 menu sensors)
3. Use in automations to get notified when lunch is ready!

## Example Automation

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
          message: "Pickup code: {{ state_attr('sensor.bessa_lunch_order_today', 'pickup_code') }}"
```

For full documentation, visit the [GitHub repository](https://github.com/zenzmatz/homeassistant-bessa-lunch).
