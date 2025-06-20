# Qutel Car Events

A simple ERPNext application for managing car events and business opportunities with enhanced UOM (Unit of Measure) integration.

## About

Qutel Car Events is a Frappe/ERPNext app that extends the standard Opportunity module to support car event management with advanced Unit of Measure calculations and participant tracking.

## Features

- Enhanced Opportunity management for car events
- Advanced UOM conversion with ERPNext Stock Settings integration
- Participant quantity tracking and capacity management
- Automatic stock quantity and rate calculations
- Event date validation and timeline management
- Real-time amount calculations using ERPNext standard logic

## Custom Fields Added

### Opportunity Fields
- `custom_opportunity_start_date` - Start date for the opportunity
- `custom_opportunity_people_qty` - Maximum participants allowed
- `custom_opportunity_duration` - Duration in days (auto-calculated)
- `custom_total_people_qty_till_now` - Total participants count (auto-calculated)

### Opportunity Item Fields
- `custom_stock_qty` - Stock quantity (qty × conversion_factor)
- `custom_stock_uom_rate` - Rate in stock UOM (rate ÷ conversion_factor)
- `custom__people_qty` - People quantity for this item
- `custom_event_start_date` - Event start date
- `custom_event_end_date` - Event end date
- `custom_event_duration` - Event duration in days (auto-calculated)

## API Endpoints

The app provides 5 comprehensive API endpoints:

- `get_item_uoms_with_conversion()` - Fetch available UOMs for item
- `get_uom_conversion_factor()` - Get specific conversion factor
- `get_opportunity_calculations()` - Calculate amounts with ERPNext logic
- `validate_opportunity_data()` - Validate business rules and dates
- `validate_integration_status()` - System health check

## Installation

```bash
bench get-app https://github.com/abdopcnet/qutel_car_events
bench install-app qutel_car_events
bench migrate && bench restart
```

## Requirements

- ERPNext v15.x
- Frappe Framework v15.x
- Python 3.10+

## Configuration

Enable "Allow UOM with conversion rate defined in Item" in Stock Settings for full functionality.

## License

MIT License
