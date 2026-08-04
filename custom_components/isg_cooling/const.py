DOMAIN = "isg_cooling"

CONF_HOST = "host"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_LOGIN_MARKER = "login_marker"

# Servicewelt path "EINSTELLUNGEN > KÜHLEN > KÜHLBETRIEB HK1"
COOLING_PAGE_PATH = "?s=4,3,2"

# cooling setting field name (0=AUS, 1=EIN)
VAL_COOLING = "val73"

# default marker in the Servicewelt HTML that indicates a successful login.
# NOTE: this is a token from the device firmware's response, not a UI
# string - it depends on the device language, not on Home Assistant's,
# which is why it is user-configurable (CONF_LOGIN_MARKER) with this value
# as the default.
LOGIN_SUCCESS_MARKER = "angemeldet als"
