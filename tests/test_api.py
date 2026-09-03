"""Tests for the SmartHub API client."""
from unittest.mock import MagicMock

import pytest

from custom_components.ha_electric_usage_downloader.api import (
    ElectricUsageAPI,
    ElectricUsageAuthError,
    ElectricUsageConnectionError,
)

LOGIN_URL = "https://bluebonnet.smarthub.coop/Login.html"
USAGE_URL = "https://bluebonnet.smarthub.coop/Usage/Usage.htm"


class _FakeResponse:
    def __init__(self, status: int, text: str = "", cookies=None):
        self.status = status
        self._text = text
        self.cookies = cookies or {}

    async def text(self):
        return self._text

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


def _session_with(response: _FakeResponse) -> MagicMock:
    session = MagicMock()
    session.post = MagicMock(return_value=response)
    session.get = MagicMock(return_value=response)
    return session


async def test_login_success():
    response = _FakeResponse(200, cookies={"session": "abc"})
    session = _session_with(response)
    api = ElectricUsageAPI(session, "user", "pass", LOGIN_URL, USAGE_URL)

    await api.login()

    assert api.cookies == {"session": "abc"}


async def test_login_rejected_raises_auth_error():
    response = _FakeResponse(403)
    session = _session_with(response)
    api = ElectricUsageAPI(session, "user", "wrong", LOGIN_URL, USAGE_URL)

    with pytest.raises(ElectricUsageAuthError):
        await api.login()


async def test_get_usage_data_parses_value():
    html = '<table><tr><td class="highcharts-tooltip">42.5</td></tr></table>'
    response = _FakeResponse(200, text=html)
    session = _session_with(response)
    api = ElectricUsageAPI(session, "user", "pass", LOGIN_URL, USAGE_URL)
    api.cookies = {"session": "abc"}

    data = await api.get_usage_data()

    assert data == {"usage": 42.5}


async def test_get_usage_data_missing_element_raises():
    html = "<html><body>no usage here</body></html>"
    response = _FakeResponse(200, text=html)
    session = _session_with(response)
    api = ElectricUsageAPI(session, "user", "pass", LOGIN_URL, USAGE_URL)
    api.cookies = {"session": "abc"}

    with pytest.raises(ElectricUsageConnectionError):
        await api.get_usage_data()


async def test_get_usage_data_bad_status_raises():
    response = _FakeResponse(500)
    session = _session_with(response)
    api = ElectricUsageAPI(session, "user", "pass", LOGIN_URL, USAGE_URL)
    api.cookies = {"session": "abc"}

    with pytest.raises(ElectricUsageConnectionError):
        await api.get_usage_data()
