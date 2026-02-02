# Vanderbilt SPC (Web UI)

This integration connects Home Assistant to a Vanderbilt SPC alarm panel using its built-in web UI.

Unlike the [official integration](https://www.home-assistant.io/integrations/spc/), it does not
require a gateway.

- Provides a global `alarm_control_panel` entity
- Supports "Armed away" / "Disarmed" states only
- Binary state sensors for all zones (motion/door detection)
- Enum sensors for zone status (tamper detection)
- State updates implemented by polling (configurable interval)

---

## Security

SPC panels use a **very old TLS implementation** that is considered unsafe nowadays.

The integration deliberately relaxes OpenSSL security settings to interface with the panel.

**Never expose your SPC panel to the public internet.**
Use this integration only on trusted local networks or via VPN.

---

## Installation

### Manual

1. Copy the `custom_components/spc_webui` folder in `config/custom_components` in Home Assistant.
2. Restart Home Assistant.

### HACS

1. Add this repository to HACS.
2. Search for it by name and install it.

---

## Disclaimer

This integration is not affiliated with Vanderbilt.

Use at your own risk. Alarm systems are security-critical infrastructure.

---

## License

MIT
