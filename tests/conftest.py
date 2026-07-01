# Pytest configuration and fixtures
"""
Shared pytest fixtures and configuration for the test suite.
"""

import asyncio
from typing import Any, AsyncGenerator, Generator, Callable
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import Request as HttpxRequest
from httpx import Response as HttpxResponse

from src.core.interfaces import Item, Request, Response
from src.core.config import ScraperSettings
from src.infrastructure.parser import HybridParser
from tests.fixtures.sample_html import (
    SAMPLE_BOOK_PAGE,
    SAMPLE_INVALID_HTML,
    SAMPLE_EMPTY_PAGE,
    SAMPLE_BOOK_LIST,
)


@pytest.fixture
def default_settings() -> ScraperSettings:
    """Return default scraper settings for testing."""
    return ScraperSettings()


@pytest.fixture
def custom_settings() -> ScraperSettings:
    """Return custom settings for testing specific scenarios."""
    return ScraperSettings(
        timeout=5,
        max_retries=2,
        concurrency_limit=3,
        retry_status_codes=[408, 429, 500, 502, 503],
    )


@pytest.fixture
def sample_html() -> str:
    """Provide sample HTML content for testing."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Test Page</title>
    </head>
    <body>
        <h1 class="title">Hello World</h1>
        <div class="content">
            <p class="paragraph">First paragraph</p>
            <p class="paragraph">Second paragraph</p>
        </div>
        <ul class="links">
            <li><a href="/page1">Link 1</a></li>
            <li><a href="/page2">Link 2</a></li>
            <li><a href="/page3">Link 3</a></li>
        </ul>
        <div class="item" data-id="123">
            <span class="name">Item Name</span>
            <span class="price">$99.99</span>
        </div>
    </body>
    </html>
    """


@pytest.fixture
def sample_request() -> Request:
    """Create a sample Request object."""
    return Request(
        url="https://example.com/test",
        method="GET",
        headers={"User-Agent": "TestBot/1.0"},
        meta={"test": True},
    )


@pytest.fixture
def sample_response(sample_request: Request) -> Response:
    """Create a sample Response object."""
    return Response(
        url="https://example.com/test",
        status_code=200,
        headers={"Content-Type": "text/html; charset=utf-8"},
        body=b"<html><body><h1>Test</h1></body></html>",
        request=sample_request,
    )


@pytest.fixture
def mock_httpx_response() -> HttpxResponse:
    """Create a mock httpx Response for testing infrastructure layer."""
    return HttpxResponse(
        status_code=200,
        headers={"content-type": "text/html; charset=utf-8"},
        content=SAMPLE_BOOK_PAGE.encode("utf-8"),
        request=HttpxRequest("GET", "https://example.com"),
    )


@pytest.fixture
def mock_httpx_error_response() -> HttpxResponse:
    """Create a mock httpx Response with error status code."""
    return HttpxResponse(
        status_code=500,
        headers={"content-type": "text/html"},
        content=b"Internal Server Error",
        request=HttpxRequest("GET", "https://example.com"),
    )


@pytest.fixture
def mock_httpx_timeout_response() -> HttpxResponse:
    """Create a mock httpx Response that simulates timeout."""
    return HttpxResponse(
        status_code=408,
        headers={},
        content=b"Request Timeout",
        request=HttpxRequest("GET", "https://example.com"),
    )


@pytest.fixture
def parser() -> HybridParser:
    """Create a parser instance for testing."""
    return HybridParser()


@pytest.fixture
def sample_item() -> Item:
    """Create a sample Item object."""
    item = Item()
    item["title"] = "Test Title"
    item["url"] = "https://example.com/item/1"
    item["price"] = 99.99
    return item


@pytest_asyncio.fixture
async def async_sleep() -> AsyncGenerator[None, None]:
    """Fixture for async sleep in tests."""
    yield
    await asyncio.sleep(0)


@pytest.fixture
def mock_http_client() -> Any:
    """Create a mock HTTP client for testing."""
    class MockClient:
        def __init__(self) -> None:
            self.requests_made: list[Request] = []
            
        async def fetch(self, request: Request) -> Response:
            self.requests_made.append(request)
            return Response(
                url=request.url,
                status_code=200,
                headers={"Content-Type": "text/html"},
                body=b"<html><body>Mocked</body></html>",
                request=request,
            )
    
    return MockClient()


@pytest.fixture
def html_fixtures() -> dict[str, str]:
    """Return dictionary of HTML fixtures for parameterized tests."""
    return {
        "valid": SAMPLE_BOOK_PAGE,
        "invalid": SAMPLE_INVALID_HTML,
        "empty": SAMPLE_EMPTY_PAGE,
        "list": SAMPLE_BOOK_LIST,
    }


@pytest.fixture
def patch_http_client() -> Callable:
    """Context manager to patch HTTP client for testing."""

    def _patch(response: HttpxResponse | None = None):
        if response is None:
            response = mock_httpx_response()

        return patch(
            "src.infrastructure.http_client.httpx.AsyncClient.send",
            new_callable=AsyncMock,
            return_value=response,
        )

    return _patch


@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
