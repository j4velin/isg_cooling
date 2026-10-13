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

# title of the power consumption table (differs between ISG versions and
# device languages)
CONSUMPTION_TABLE_TITLES = ("LEISTUNGSAUFNAHME", "STROMVERBRAUCH", "POWER CONSUMPTION")

# normalized row keys in the power consumption table, german and english
KEYS_COOLING_24H = ("KÜHLEN1-24H", "COOLING1-24H")
KEYS_COOLING_12M = ("KÜHLEN1-12M", "COOLING1-12M")
KEYS_COOLING_PREV_12M = ("KÜHLEN13-24M", "COOLING13-24M")

# default marker in the Servicewelt HTML that indicates a successful login.
# NOTE: this is a token from the device firmware's response, not a UI
# string - it depends on the device language, not on Home Assistant's,
# which is why it is user-configurable (CONF_LOGIN_MARKER) with this value
# as the default.
LOGIN_SUCCESS_MARKER = "angemeldet als"

# markers of the known device languages, accepted in addition to the
# configured one so a language switch on the ISG doesn't break the login
KNOWN_LOGIN_SUCCESS_MARKERS = ("angemeldet als", "you are registered as")

# default polling interval (in hours) for reading the cooling state
DEFAULT_SCAN_INTERVAL_HOURS = 24

# default polling interval (in minutes) for the power consumption sensors.
# the ISG updates the 1-24 h value hourly; the total has its own daily refresh.
DEFAULT_CONSUMPTION_SCAN_INTERVAL_MINUTES = 10
