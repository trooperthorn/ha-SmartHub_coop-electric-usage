import logging

import aiohttp
from bs4 import BeautifulSoup

_LOGGER = logging.getLogger(__name__)


class ElectricUsageAuthError(Exception):
    """Raised when the SmartHub portal rejects the configured credentials."""


class ElectricUsageConnectionError(Exception):
    """Raised when the SmartHub portal cannot be reached or returns unparseable data."""


class ElectricUsageAPI:
    """Handles communication with the PEC SmartHub portal."""

    def __init__(self, session: aiohttp.ClientSession, username: str, password: str, login_url: str, usage_url: str):
        """Initialize the API client."""
        self.session = session
        self.username = username
        self.password = password
        self.login_url = login_url
        self.usage_url = usage_url
        self.cookies = None

    async def login(self):
        """Log in to the PEC SmartHub and retrieve session cookies."""
        payload = {
            "UserName": self.username,
            "Password": self.password
        }
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        try:
            async with self.session.post(self.login_url, data=payload, headers=headers) as response:
                if response.status != 200:
                    raise ElectricUsageAuthError(f"Login rejected with status {response.status}")
                self.cookies = response.cookies
        except aiohttp.ClientError as err:
            raise ElectricUsageConnectionError(f"Error connecting to the SmartHub login page: {err}") from err

    async def get_usage_data(self):
        """Fetch electric usage data by scraping the PEC SmartHub portal."""
        if not self.cookies:
            await self.login()

        headers = {
            "User-Agent": "Mozilla/5.0"
        }
        try:
            async with self.session.get(self.usage_url, cookies=self.cookies, headers=headers) as response:
                if response.status != 200:
                    raise ElectricUsageConnectionError(f"Failed to fetch usage data: status {response.status}")
                html_content = await response.text()
        except aiohttp.ClientError as err:
            raise ElectricUsageConnectionError(f"Error fetching usage data: {err}") from err

        soup = BeautifulSoup(html_content, "html.parser")
        return self._parse_usage_data(soup)

    def _parse_usage_data(self, soup):
        """Parse the electric usage data from the HTML soup."""
        tag = soup.find("td", class_="highcharts-tooltip")
        if tag is None:
            raise ElectricUsageConnectionError("Usage page did not contain the expected usage element")
        try:
            usage_value = float(tag.get_text())
        except ValueError as err:
            raise ElectricUsageConnectionError(f"Could not parse usage value: {err}") from err
        return {"usage": usage_value}
