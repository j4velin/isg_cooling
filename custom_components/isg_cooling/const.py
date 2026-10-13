from __future__ import annotations

from dataclasses import dataclass

DOMAIN = "isg_cooling"

CONF_HOST = "host"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_LOGIN_MARKER = "login_marker"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_CONSUMPTION_SCAN_INTERVAL = "consumption_scan_interval"

# Servicewelt path "EINSTELLUNGEN > KÜHLEN > KÜHLBETRIEB HK1"
COOLING_PAGE_PATH = "?s=4,3,2"

# cooling setting field name (0=AUS, 1=EIN)
VAL_COOLING = "val73"

# Servicewelt path "INFO > ENERGIEBILANZ" (english: "INFO > ENERGY FOOTPRINT")
ENERGY_PAGE_PATH = "?s=1,2"


@dataclass(frozen=True)
class IsgTexts:
    """texts of the Servicewelt in one device language"""

    # shown after a successful login, compared in lower case
    login_marker: str
    # titles of the power consumption table (differ between ISG versions)
    consumption_table_titles: tuple[str, ...]
    # normalized row keys of the cooling rows in that table, see
    # isg_client._normalize_key()
    key_cooling_24h: str
    key_cooling_12m: str
    key_cooling_prev_12m: str


# all known device languages; the texts of every language are accepted, so
# the ISG language needs no setting. To add a language, add an entry here
# and test it against a saved copy of the INFO > ENERGIEBILANZ page.
ISG_TEXTS = {
    "de": IsgTexts(
        login_marker="angemeldet als",
        consumption_table_titles=("LEISTUNGSAUFNAHME", "STROMVERBRAUCH"),
        key_cooling_24h="KÜHLEN1-24H",
        key_cooling_12m="KÜHLEN1-12M",
        key_cooling_prev_12m="KÜHLEN13-24M",
    ),
    "en": IsgTexts(
        login_marker="you are registered as",
        consumption_table_titles=("POWER CONSUMPTION",),
        key_cooling_24h="COOLING1-24H",
        key_cooling_12m="COOLING1-12M",
        key_cooling_prev_12m="COOLING13-24M",
    ),
}

# default marker in the Servicewelt HTML that indicates a successful login.
# NOTE: this is a token from the device firmware's response, not a UI
# string - it depends on the device language, not on Home Assistant's,
# which is why it is user-configurable (CONF_LOGIN_MARKER) with this value
# as the default.
LOGIN_SUCCESS_MARKER = ISG_TEXTS["de"].login_marker

# default polling interval (in hours) for reading the cooling state
DEFAULT_SCAN_INTERVAL_HOURS = 24

# default polling interval (in minutes) for the power consumption sensors.
# the ISG updates the 1-24 h value hourly; the total has its own daily refresh.
DEFAULT_CONSUMPTION_SCAN_INTERVAL_MINUTES = 10
