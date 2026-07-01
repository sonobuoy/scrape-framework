# Pytest configuration and fixtures
"""
Shared pytest fixtures and configuration for the test suite.
"""

import asyncio
from typing import Any, AsyncGenerator, Generator

import pytest
import pytest_asyncio

from src.core.interfaces import Item, Request, Response
from src.infrastructure.parser import HybridParser


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
