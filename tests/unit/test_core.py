# Unit Tests for Core Module
"""
Unit tests for the core framework components.
"""

import pytest

from src.core.exceptions import ScrapingError, HTTPError, DownloadTimeout
from src.core.interfaces import Request, Response, Item


class TestRequest:
    """Tests for Request dataclass."""

    def test_create_request(self) -> None:
        """Test basic request creation."""
        req = Request(url="https://example.com")
        assert req.url == "https://example.com"
        assert req.method == "GET"
        assert req.callback == "parse"

    def test_request_method_uppercase(self) -> None:
        """Test that method is converted to uppercase."""
        req = Request(url="https://example.com", method="post")
        assert req.method == "POST"

    def test_invalid_url_scheme(self) -> None:
        """Test that invalid URL scheme raises error."""
        with pytest.raises(ValueError, match="Invalid URL scheme"):
            Request(url="ftp://example.com")

    def test_request_with_headers(self) -> None:
        """Test request with custom headers."""
        headers = {"User-Agent": "TestBot/1.0"}
        req = Request(url="https://example.com", headers=headers)
        assert req.headers == headers

    def test_request_with_meta(self) -> None:
        """Test request with metadata."""
        meta = {"page": 1, "category": "test"}
        req = Request(url="https://example.com", meta=meta)
        assert req.meta["page"] == 1
        assert req.meta["category"] == "test"


class TestResponse:
    """Tests for Response dataclass."""

    def test_response_success(self) -> None:
        """Test response with success status."""
        resp = Response(
            url="https://example.com",
            status_code=200,
            headers={},
            body=b"OK",
        )
        assert resp.is_success is True
        assert resp.is_redirect is False

    def test_response_redirect(self) -> None:
        """Test response with redirect status."""
        resp = Response(
            url="https://example.com",
            status_code=301,
            headers={"Location": "https://new.example.com"},
            body=b"",
        )
        assert resp.is_success is False
        assert resp.is_redirect is True

    def test_response_error(self) -> None:
        """Test response with error status."""
        resp = Response(
            url="https://example.com",
            status_code=404,
            headers={},
            body=b"Not Found",
        )
        assert resp.is_success is False
        assert resp.is_redirect is False

    def test_response_text(self) -> None:
        """Test response text property."""
        resp = Response(
            url="https://example.com",
            status_code=200,
            headers={},
            body=b"Hello World",
        )
        assert resp.text == "Hello World"

    def test_response_text_encoding(self) -> None:
        """Test response text with encoding."""
        resp = Response(
            url="https://example.com",
            status_code=200,
            headers={},
            body="Héllo Wörld".encode("utf-8"),
            encoding="utf-8",
        )
        assert resp.text == "Héllo Wörld"


class TestItem:
    """Tests for Item dataclass."""

    def test_item_creation(self) -> None:
        """Test basic item creation."""
        item = Item()
        item["title"] = "Test"
        item["value"] = 123
        assert item["title"] == "Test"
        assert item["value"] == 123

    def test_item_to_dict(self) -> None:
        """Test item to_dict method."""
        item = Item()
        item["name"] = "Product"
        item["price"] = 99.99
        result = item.to_dict()
        assert isinstance(result, dict)
        assert result["name"] == "Product"
        assert result["price"] == 99.99

    def test_item_getitem(self) -> None:
        """Test item __getitem__ method."""
        item = Item()
        item["key"] = "value"
        assert item["key"] == "value"

    def test_item_setitem(self) -> None:
        """Test item __setitem__ method."""
        item = Item()
        item["dynamic_key"] = "dynamic_value"
        assert item.dynamic_key == "dynamic_value"  # type: ignore[attr-defined]


class TestExceptions:
    """Tests for exception hierarchy."""

    def test_scraping_error_basic(self) -> None:
        """Test basic ScrapingError."""
        error = ScrapingError("Test error")
        assert error.message == "Test error"
        assert error.context == {}

    def test_scraping_error_with_context(self) -> None:
        """Test ScrapingError with context."""
        context = {"url": "https://example.com", "status": 500}
        error = ScrapingError("Server error", context=context)
        assert error.context == context

    def test_scraping_error_to_dict(self) -> None:
        """Test ScrapingError to_dict method."""
        error = ScrapingError("Test", {"key": "value"})
        result = error.to_dict()
        assert result["exception_type"] == "ScrapingError"
        assert result["message"] == "Test"
        assert result["context"] == {"key": "value"}

    def test_http_error(self) -> None:
        """Test HTTPError."""
        error = HTTPError(status_code=404, message="Not Found", url="https://example.com")
        assert error.status_code == 404
        assert error.url == "https://example.com"

    def test_download_timeout(self) -> None:
        """Test DownloadTimeout."""
        error = DownloadTimeout("Request timed out")
        assert isinstance(error, ScrapingError)
