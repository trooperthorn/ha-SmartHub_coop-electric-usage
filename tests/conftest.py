"""Shared fixtures for the SmartHub integration tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

pytest_plugins = "pytest_homeassistant_custom_component"

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(recorder_mock, enable_custom_integrations):
    """Every test gets a recorder: the integration depends on it for statistics."""
    yield


@pytest.fixture
def poll_complete() -> dict[str, Any]:
    return json.loads((FIXTURES / "poll_complete.json").read_text())


class FakeCookie:
    def __init__(self, key: str, value: str) -> None:
        self.key = key
        self.value = value


class FakeResponse:
    def __init__(self, status: int = 200, body: Any = None) -> None:
        self.status = status
        self._body = body

    async def json(self, content_type=None):
        if isinstance(self._body, Exception):
            raise self._body
        return self._body

    async def read(self):
        return b""

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


class FakeSession:
    """Scripted aiohttp session: each call pops the next response for its path."""

    def __init__(self, routes: dict[str, list[Any]]) -> None:
        self.routes = routes
        self.cookie_jar = [FakeCookie("XSRF-TOKEN", "xsrf-value")]
        self.calls: list[tuple[str, str, dict]] = []

    def _next(self, method: str, url: str, **kwargs):
        path = url.split(".coop", 1)[1]
        self.calls.append((method, path, kwargs))
        item = self.routes[path].pop(0)
        if isinstance(item, Exception) and not isinstance(item, ValueError):
            raise item
        return item

    def get(self, url, **kwargs):
        return self._next("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self._next("POST", url, **kwargs)

    def request(self, method, url, **kwargs):
        return self._next(method, url, **kwargs)


LOGIN_OK = {
    "status": "SUCCESS",
    "authorizationToken": "tok",
    "expiration": 4102444800000,
}
