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

# Servicewelt path "INFO > ENERGIEBILANZ"
ENERGY_PAGE_PATH = "?s=1,2"

# title of the power consumption table (differs between ISG versions)
CONSUMPTION_TABLE_TITLES = ("LEISTUNGSAUFNAHME", "STROMVERBRAUCH")

# normalized row keys in the power consumption table
KEY_COOLING_24H = "KÜHLEN1-24H"
KEY_COOLING_12M = "KÜHLEN1-12M"
KEY_COOLING_PREV_12M = "KÜHLEN13-24M"

# default marker in the Servicewelt HTML that indicates a successful login.
# NOTE: this is a token from the device firmware's response, not a UI
# string - it depends on the device language, not on Home Assistant's,
# which is why it is user-configurable (CONF_LOGIN_MARKER) with this value
# as the default.
LOGIN_SUCCESS_MARKER = "angemeldet als"

# default polling interval (in hours) for reading the cooling state
DEFAULT_SCAN_INTERVAL_HOURS = 24

# default polling interval (in minutes) for the power consumption sensors.
# consumption after the last reading before midnight is lost for the total.
DEFAULT_CONSUMPTION_SCAN_INTERVAL_MINUTES = 10
