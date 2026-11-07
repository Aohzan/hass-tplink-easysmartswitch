# TP-Link Easy Smart Switch integration for Home Assistant

This a _custom component_ for [Home Assistant](https://www.home-assistant.io/).
The `tplink_easysmartswitch` integration allows you to get port information from [TP-Link Easy Smart Switch](https://www.tp-link.com/fr/business-networking/easy-smart-switch/).

You will get two sensors by input enabled with all attributes availables, and a button to restart the switch.

## Installation

### Marketplace

[![Open your Home Assistant instance and open this repository in the Marketplace.](https://my.home-assistant.io/badges/marketplace_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=Aohzan&repository=hass-tplink-easysmartswitch&category=integration)

Settings > Marketplace > Add from link > `Aohzan/hass-tplink-easysmartswitch` > Add, then Install.

### Manually

Copy the `custom_components/tplink_easysmartswitch` folder into the config folder.

## Configuration

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=tplink_easysmartswitch)

Or go to Settings > Devices & services > Add integration and select TP-Link Easy Smart Switch.

## Web interface of the switch

The switch allows a single web session: logging in its web interface closes the session of Home Assistant, and the other way round.

When the session of Home Assistant is closed less than 5 minutes after it was last used, the integration takes it as a login in the web interface: it leaves the switch alone for 5 minutes, and its entities are unavailable meanwhile. Then it logs in again, which closes the session of the web interface if it is still open. Log in again in the web interface to get 5 more minutes.

When the session was unused for longer (scan interval of 5 minutes or more, or switch unreachable meanwhile), the integration considers it expired and logs in again right away.

## Lovelace Card example

With `multiple-entity-row` custom card:

```yaml
entities:
  - entities:
      - entity: sensor.port_01_ingress
        name: Down
      - entity: sensor.port_01_egress
        name: Up
      - attribute: link_status
        name: Status
    entity: binary_sensor.port_01
    type: custom:multiple-entity-row
type: entities

```

![Card example](lovelave-card-example.jpg)

## Credits

https://github.com/psmode/essstat
