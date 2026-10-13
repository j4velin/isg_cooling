# LWZ Kühlbetrieb (ISG Cooling)

Home Assistant custom integration for controlling the **cooling** setting of a **Stiebel Eltron LWZ** heat pump via the device's ISG / Servicewelt web interface.

> **Looking for general Stiebel Eltron ISG support?** For broad monitoring and control of Stiebel Eltron ISG heat pumps, use the excellent [**pail23/stiebel_eltron_isg_component**](https://github.com/pail23/stiebel_eltron_isg_component) integration. It covers ISG functionality extensively but does **not** expose the cooling toggle for **LWZ**-type heat pumps — that gap is exactly what this integration fills. The two can be installed side by side.

## What it does

This integration adds a Home Assistant switch that reflects and controls the cooling mode of the heat pump.

- **On** = cooling enabled
- **Off** = cooling disabled

It also adds two energy sensors (in kWh) for the electrical power used for cooling, read from **INFO → ENERGIEBILANZ** (table *LEISTUNGSAUFNAHME*, rows *KÜHLEN*; in English: **INFO → ENERGY FOOTPRINT**, table *POWER CONSUMPTION*, rows *COOLING*):

- **Stromverbrauch Kühlen gesamt**: a lifetime total, similar to the *consumed heating total* sensor of the Stiebel Eltron ISG integration. The ISG has no such value, so the integration keeps it itself (see below). It changes once a day, shortly after midnight, and can be used in the Home Assistant **Energy dashboard**.
- **Stromverbrauch Kühlen 1-24 h** *(disabled by default)*: the consumption of the last 24 hours. The ISG updates it every hour, a few minutes after the full hour, so it is the only value that shows consumption within a day. It goes up and down as the window moves, so it has no state class and keeps no long-term statistics. Enable it under the entity's settings if you need it.

Daily, monthly or yearly consumption doesn't need its own sensor: Home Assistant calculates it from the total, e.g. in the Energy dashboard or with a *utility meter* helper.

Not every heat pump / ISG version shows these values; if they are missing, the 1-24 h sensor is *unknown* and the total keeps its last value.

#### How the total is calculated

The ISG only shows the consumption of the last 24 hours, the last 12 months and the 12 months before (13-24 M). The total starts at *1-12 M + 13-24 M*, read at 00:15 after the sensor was created; until then it is *unknown*. This matches the real lifetime consumption only if the heat pump is less than 24 months old; otherwise older consumption is missing. From then on, the 1-24 h value is added once a day: at 00:15 the integration reads it, independent of the regular polling (and again every 10 minutes until 00:55 if the ISG cannot be read), and it then contains exactly the 24 hours before midnight. Reading the window once every 24 hours means the periods neither overlap nor leave gaps, so nothing is counted twice or lost. The total is stored across Home Assistant restarts. If the ISG cannot be read between 00:10 and 01:00, e.g. because Home Assistant is offline, the consumption of the previous day is missing from the total.

The integration communicates directly with the heat pump's local web interface and does not require any cloud service.

> **Note:** This integration has so far only been tested with **Servicewelt version 12.2.3**, set to **German** or **English**. Other Servicewelt versions may work but are untested. For other languages, adjust the **Login success marker** field during setup (see [Configuration](#configuration)); the power consumption sensors only support German and English.

## Requirements

- A **Stiebel Eltron LWZ** heat pump with an accessible **ISG / Servicewelt** interface
- The IP address or hostname of the ISG device
- Optionally, a username and password for the ISG web interface (only if your ISG requires a login)
- Home Assistant with support for custom integrations

## Installation

### Option A — HACS (recommended)

This repository is a valid [HACS](https://hacs.xyz/) custom repository.

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=j4velin&repository=isg_cooling&category=integration)

Click the button above to open this repository in HACS, then click **Download** and **restart Home Assistant**. Afterwards continue with [Configuration](#configuration).

To add it manually instead:

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
   - **Login success marker** *(defaults to `angemeldet als`; the German and English markers are always recognized, so only change it if your ISG uses another language)*
   - **Poll interval (hours)** *(defaults to 24; how often the cooling state is read from the ISG)*
   - **Power consumption poll interval (minutes)** *(defaults to 10; how often the 1-24 h sensor is read from the ISG, which updates it hourly. The ISG is only polled while that sensor is enabled; the total does not depend on it; see [How the total is calculated](#how-the-total-is-calculated))*
4. Finish setup.

Both poll intervals can be changed later: go to **Settings** → **Devices & services** → **LWZ Kühlbetrieb** and click **Configure**. The integration reloads with the new intervals; the cooling power consumption total is kept.

## Usage

After setup, Home Assistant will expose a switch named **Kühlbetrieb**.

Use the switch to enable or disable cooling on the heat pump.

To track the cooling power consumption in the Energy dashboard, add **Stromverbrauch Kühlen gesamt** as an individual device under **Settings** → **Dashboards** → **Energy**.

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

To support another ISG language, add its texts (login text, title of the power consumption table and the cooling rows) to `ISG_TEXTS` in `custom_components/isg_cooling/const.py`, and test them against a saved copy of the ISG page **INFO → ENERGIEBILANZ** (`?s=1,2`) in that language. The texts of all languages in `ISG_TEXTS` are accepted, so no setting is needed.

## License

No license file is currently included in this repository.
