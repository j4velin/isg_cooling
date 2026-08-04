# isg_cooling

Home Assistant custom integration for controlling the **cooling** setting of a **Stiebel Eltron LWZ** heat pump via the device's ISG / Servicewelt web interface.

## What it does

This integration adds a single Home Assistant switch that reflects and controls the cooling mode of the heat pump.

- **On** = cooling enabled
- **Off** = cooling disabled

The integration communicates directly with the heat pump's local web interface and does not require any cloud service.

> **Note:** This integration has so far only been tested with a **German** ISG interface and **Servicewelt version 12.2.3**. Other languages and Servicewelt versions may work but are untested. If your ISG is set to a different language, adjust the **Login success marker** field during setup (see [Configuration](#configuration)).

## Requirements

- A **Stiebel Eltron LWZ** heat pump with an accessible **ISG / Servicewelt** interface
- The IP address or hostname of the ISG device
- A valid username and password for the ISG web interface
- Home Assistant with support for custom integrations

## Installation

### Option A — HACS (recommended)

This repository is a valid [HACS](https://hacs.xyz/) custom repository.

1. Make sure [HACS is installed](https://hacs.xyz/docs/use/download/download/) in your Home Assistant instance.
2. In Home Assistant, go to **HACS**.
3. Open the **⋮** (top-right) menu and choose **Custom repositories**.
4. Add the repository:
   - **Repository**: `https://github.com/j4velin/isg_cooling`
   - **Type**: `Integration`
5. Click **Add**, then search for **LWZ Kühlbetrieb (ISG Cooling)** in HACS and click **Download**.
6. **Restart Home Assistant.**
7. Go to **Settings** → **Devices & services** → **Add integration** and continue with the configuration steps below.

Once installed via HACS, you will be notified of new releases and can update with a single click.

### Option B — Manual installation

1. Copy the `custom_components/isg_cooling` folder from this repository into your Home Assistant `config/custom_components/` directory, so that the final path is `config/custom_components/isg_cooling/`.
2. Restart Home Assistant.

### Configuration

1. In Home Assistant, go to **Settings** → **Devices & services** → **Add integration**.
2. Search for **LWZ Kühlbetrieb**.
3. Enter:
   - **Host**: the ISG hostname or IP address
   - **Username** *(optional — leave empty, together with the password, if your ISG does not require a login; the login request is then skipped entirely)*
   - **Password** *(optional)*
   - **Login success marker** *(defaults to `angemeldet als`; only change it if your ISG uses a different language)*
   - **Poll interval (hours)** *(defaults to 24; how often the cooling state is read from the ISG)*
4. Finish setup.

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