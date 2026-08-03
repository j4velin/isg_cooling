"""HTTP client for the Stiebel Eltron HTTP-Servicewelt"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from typing import Optional

import aiohttp
from bs4 import BeautifulSoup

from .const import COOLING_PAGE_PATH, VAL_COOLING

_LOGGER = logging.getLogger(__name__)

# Regex pattern to extract values from JavaScript: jsvalues['fieldname']['val']='value';
_JSVALUE_PATTERN = re.compile(r"jsvalues\['[^']+'\]\['val'\]='([^']+)';")


class IsgAuthError(Exception):
    """Login failed"""


class IsgConnectionError(Exception):
    """Network or parsing error"""


class IsgParsingError(Exception):
    """HTML form parsing error"""


@dataclass
class IsgFormState:
    """State of the cooling settings form"""

    fields: dict[str, str]
    cooling_on: bool


class IsgClient:
    """Client for http://<host>/ (ISG Servicewelt).
    
    Handles authentication, form parsing, and state management for the ISG device.
    """

    # Maximum number of automatic re-login attempts on session expiration
    MAX_RETRY_ATTEMPTS = 2

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        username: str,
        password: str,
    ) -> None:
        """Initialize the ISG client.
        
        Args:
            session: aiohttp ClientSession for making HTTP requests
            host: ISG device hostname or IP address
            username: Authentication username
            password: Authentication password
        """
        self._session = session
        self._base = f"http://{host.rstrip('/')}/"
        self._username = username
        self._password = password
        self._logged_in = False

    async def async_login(self) -> None:
        """Authenticate with the ISG device.
        
        Raises:
            IsgConnectionError: If connection to the device fails
            IsgAuthError: If authentication credentials are invalid
        """
        payload = {
            "user": self._username,
            "pass": self._password,
        }
        
        try:
            async with self._session.post(
                self._base, data=payload, timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status != 200:
                    raise IsgConnectionError(
                        f"Unexpected HTTP status {resp.status} during login"
                    )
                text = await resp.text()
        except asyncio.TimeoutError as err:
            raise IsgConnectionError(f"Login timeout for {self._base}") from err
        except aiohttp.ClientError as err:
            raise IsgConnectionError(f"Connection to {self._base} failed: {err}") from err

        # Check if login was successful by looking for the "logged in as" indicator
        if "angemeldet als" not in text.lower():
            _LOGGER.error("Login failed - invalid credentials or unexpected response")
            raise IsgAuthError("Login failed - check credentials")
        
        self._logged_in = True
        _LOGGER.debug("Successfully authenticated with ISG device")

    async def _async_get_cooling_form(self) -> IsgFormState:
        """Fetch and parse the cooling settings form from the ISG device.
        
        Returns:
            IsgFormState containing the form fields and cooling state
            
        Raises:
            IsgConnectionError: If the request fails or session is expired
            IsgParsingError: If the HTML form cannot be parsed
        """
        url = self._base + COOLING_PAGE_PATH

        try:
            async with self._session.get(
                url, timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 401:
                    # Session expired, force re-login
                    _LOGGER.debug("Session expired (401), clearing login state")
                    self._logged_in = False
                    raise IsgConnectionError("Session expired")
                
                if resp.status != 200:
                    raise IsgConnectionError(
                        f"Failed to fetch cooling form: HTTP {resp.status}"
                    )
                
                html = await resp.text()
        except asyncio.TimeoutError as err:
            raise IsgConnectionError(f"Timeout fetching cooling form from {url}") from err
        except aiohttp.ClientError as err:
            raise IsgConnectionError(f"Failed to fetch cooling form: {err}") from err

        # Parse the HTML response
        try:
            form_state = self._parse_cooling_form(html)
        except IsgParsingError:
            # If parsing fails and we're logged in, session might have expired
            self._logged_in = False
            raise

        return form_state

    def _parse_cooling_form(self, html: str) -> IsgFormState:
        """Parse the cooling form from HTML content.
        
        Args:
            html: HTML content from the cooling settings page
            
        Returns:
            IsgFormState with parsed form fields and cooling state
            
        Raises:
            IsgParsingError: If the form cannot be parsed or required fields are missing
        """
        soup = BeautifulSoup(html, "html.parser")
        form = soup.find("form", id="werte")
        
        if form is None:
            raise IsgParsingError(
                "Form 'werte' not found in response - session may have expired or "
                "device configuration has changed"
            )

        # Extract all script tags for parsing JavaScript values
        scripts = soup.find_all("script")
        script_content = "\n".join(
            script.string for script in scripts if script.string is not None
        )

        fields: dict[str, str] = {}
        cooling_on = False

        # Parse form inputs
        for inp in form.find_all("input"):
            name = inp.get("name")
            if not name:
                continue

            input_type = inp.get("type", "text")

            if input_type == "radio":
                # Radio buttons: only include if checked
                if inp.has_attr("checked"):
                    value = inp.get("value", "")
                    fields[name] = value
                    
                    if name == VAL_COOLING and value == "1":
                        cooling_on = True
                        _LOGGER.debug("Cooling is ON")
                    elif name == VAL_COOLING:
                        _LOGGER.debug("Cooling is OFF")

            elif input_type in ("text", "hidden"):
                # Text/hidden fields: extract value from JavaScript
                value = self._extract_js_value(name, script_content)
                if value is not None:
                    fields[name] = value
                else:
                    _LOGGER.warning(
                        f"Could not extract value for field '{name}' from JavaScript"
                    )

        # Validate that we got the cooling field
        if VAL_COOLING not in fields:
            raise IsgParsingError(
                f"Required field '{VAL_COOLING}' not found in form"
            )

        _LOGGER.debug(f"Parsed form with {len(fields)} fields")
        return IsgFormState(fields=fields, cooling_on=cooling_on)

    def _extract_js_value(self, field_name: str, script_content: str) -> Optional[str]:
        """Extract a field value from JavaScript content.
        
        Args:
            field_name: The form field name (e.g., "fld123")
            script_content: Combined JavaScript content from all script tags
            
        Returns:
            The extracted value, or None if not found
        """
        # Build the search pattern for this field
        # Pattern: jsvalues['field_name_suffix']['val']='value';
        search_pattern = f"jsvalues['{field_name[3:]}']["

        try:
            # Find the line containing this field
            for line in script_content.splitlines():
                if search_pattern in line:
                    # Use the pre-compiled regex to extract the value
                    match = _JSVALUE_PATTERN.search(line)
                    if match:
                        return match.group(1)
                    else:
                        _LOGGER.warning(
                            f"Field '{field_name}' found but value could not be parsed from: {line}"
                        )
                        return None
        except Exception as err:
            _LOGGER.error(f"Error extracting value for field '{field_name}': {err}")
            return None

        return None

    async def async_get_cooling_state(self, retry_on_auth: bool = True) -> bool:
        """Get the current cooling state.
        
        Args:
            retry_on_auth: If True, automatically retry after re-login on auth errors
            
        Returns:
            True if cooling is enabled, False otherwise
            
        Raises:
            IsgConnectionError: If unable to connect to the device
            IsgAuthError: If authentication fails
            IsgParsingError: If the response cannot be parsed
        """
        if not self._logged_in:
            await self.async_login()

        try:
            state = await self._async_get_cooling_form()
            return state.cooling_on
        except IsgConnectionError as err:
            if retry_on_auth and "Session expired" in str(err):
                _LOGGER.info("Retrying after session expiration")
                self._logged_in = False
                await self.async_login()
                state = await self._async_get_cooling_form()
                return state.cooling_on
            raise

    async def async_set_cooling_state(self, turn_on: bool) -> None:
        """Set the cooling state.
        
        Args:
            turn_on: True to enable cooling, False to disable
            
        Raises:
            IsgConnectionError: If unable to connect or save fails
            IsgAuthError: If authentication fails
            IsgParsingError: If the response cannot be parsed
        """
        if not self._logged_in:
            await self.async_login()

        # Get current form state to preserve other fields
        state = await self._async_get_cooling_form()
        fields = dict(state.fields)

        # Update the cooling field
        fields[VAL_COOLING] = "1" if turn_on else "0"

        # Save to device
        await self._async_save_form(fields)

        # Log the action
        state_str = "ON" if turn_on else "OFF"
        _LOGGER.info(f"Set cooling to {state_str}")

    async def _async_save_form(self, fields: dict[str, str]) -> None:
        """Save form fields to the ISG device.
        
        Args:
            fields: Dictionary of field names and values to save
            
        Raises:
            IsgConnectionError: If the save operation fails
        """
        url = self._base + "save.php"

        # Build JSON payload - the device expects a JSON array of {name, value} objects
        payload_data = [{"name": key, "value": value} for key, value in fields.items()]
        payload = json.dumps({"data": payload_data})

        headers = {"content-type": "application/json"}

        try:
            async with self._session.post(
                url, data=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 401:
                    self._logged_in = False
                    raise IsgConnectionError("Session expired during save")
                
                if resp.status != 200:
                    response_text = await resp.text()
                    _LOGGER.error(f"Save failed with status {resp.status}: {response_text}")
                    raise IsgConnectionError(
                        f"Failed to save form: HTTP {resp.status}"
                    )

                # Verify response (optional - device may return empty response)
                try:
                    response_text = await resp.text()
                    if response_text:
                        _LOGGER.debug(f"Save response: {response_text}")
                except Exception as err:
                    _LOGGER.warning(f"Could not read save response: {err}")

        except asyncio.TimeoutError as err:
            raise IsgConnectionError(f"Timeout saving form to {url}") from err
        except aiohttp.ClientError as err:
            raise IsgConnectionError(f"Failed to save form: {err}") from err
