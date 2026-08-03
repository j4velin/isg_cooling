# isg_cooling

Home Assistant custom integration for controlling the **cooling** setting of a **Stiebel Eltron LWZ** heat pump via the device's ISG / Servicewelt web interface.

## What it does

This integration adds a single Home Assistant switch that reflects and controls the cooling mode of the heat pump.

- **On** = cooling enabled
- **Off** = cooling disabled

The integration communicates directly with the heat pump's local web interface and does not require any cloud service.

## Requirements

- A **Stiebel Eltron LWZ** heat pump with an accessible **ISG / Servicewelt** interface
- The IP address or hostname of the ISG device
- A valid username and password for the ISG web interface
- Home Assistant with support for custom integrations

## Installation

1. Copy the `isg_cooling` folder into your Home Assistant `custom_components/` directory.
2. Restart Home Assistant.
3. In Home Assistant, go to **Settings** → **Devices & services** → **Add integration**.
4. Search for **LWZ Kühlbetrieb**.
5. Enter:
   - **Host**: the ISG hostname or IP address
   - **Username**
   - **Password**
6. Finish setup.

## Usage

After setup, Home Assistant will expose a switch named **Kühlbetrieb**.

Use the switch to enable or disable cooling on the heat pump.

## Notes

- The integration uses the local ISG interface over HTTP.
- The current implementation targets the cooling toggle exposed as `val73` in the Servicewelt UI.
- The integration is configured through Home Assistant's config flow; no YAML configuration is required.

## Troubleshooting

If setup fails:

- Verify the host is reachable from Home Assistant.
- Make sure the username and password are correct.
- Confirm that the ISG web interface is available on the local network.
- Check Home Assistant logs for connection or authentication errors.

## Development

This repository is a Python Home Assistant integration.

## License

No license file is currently included in this repository.