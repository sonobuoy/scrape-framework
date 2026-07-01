# Core Exceptions Hierarchy
"""
Custom exception hierarchy for the scraping framework.

This module defines a structured set of exceptions to handle various error scenarios
during web scraping operations, enabling precise error handling and recovery strategies.
"""

from typing import Any


class ScrapingError(Exception):
    """Base exception for all scraping-related errors."""

    def __init__(self, message: str, context: dict[str, Any] | None = None) -> None:
        self.message = message
        self.context = context or {}
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for logging."""
        return {
            "exception_type": self.__class__.__name__,
            "message": self.message,
            "context": self.context,
        }


class ConfigurationError(ScrapingError):
    """Raised when configuration is invalid or missing."""


class DownloadError(ScrapingError):
    """Base exception for download-related errors."""


class DownloadTimeout(DownloadError):
    """Raised when a download request times out."""


class HTTPError(DownloadError):
    """Raised when an HTTP error response is received."""

    def __init__(
        self,
        status_code: int,
        message: str,
        url: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, context)
        self.status_code = status_code
        self.url = url


class ConnectionError(DownloadError):
    """Raised when a connection cannot be established."""


class ParseError(ScrapingError):
    """Base exception for parsing-related errors."""


class SelectorError(ParseError):
    """Raised when a selector fails to match or is invalid."""


class ContentError(ParseError):
    """Raised when content cannot be parsed due to format issues."""


class StorageError(ScrapingError):
    """Base exception for storage-related errors."""


class ValidationError(ScrapingError):
    """Raised when data validation fails."""

    def __init__(
        self,
        message: str,
        field: str | None = None,
        value: Any | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, context)
        self.field = field
        self.value = value


class RetryError(ScrapingError):
    """Raised when all retry attempts have been exhausted."""

    def __init__(
        self,
        message: str,
        attempts: int,
        last_exception: Exception | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, context)
        self.attempts = attempts
        self.last_exception = last_exception


class CircuitBreakerError(ScrapingError):
    """Raised when circuit breaker is open due to repeated failures."""


class RobotTxtError(ScrapingError):
    """Raised when robots.txt rules prevent access."""
