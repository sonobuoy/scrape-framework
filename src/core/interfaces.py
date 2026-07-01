# Core Interfaces (Ports)
"""
Abstract Base Classes defining the core interfaces for the scraping framework.

This module implements the Dependency Inversion Principle by defining contracts
that concrete implementations must follow. The core logic depends only on these
abstractions, not on concrete implementations.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class Request:
    """Represents an HTTP request to be processed by the scraper."""

    url: str
    method: str = "GET"
    headers: dict[str, str] | None = None
    params: dict[str, Any] | None = None
    body: bytes | str | None = None
    cookies: dict[str, str] | None = None
    callback: str = "parse"
    meta: dict[str, Any] = field(default_factory=dict)
    priority: int = 0
    dont_retry: bool = False
    max_retries: int | None = None

    def __post_init__(self) -> None:
        if not self.url.startswith(("http://", "https://")):
            raise ValueError(f"Invalid URL scheme: {self.url}")
        self.method = self.method.upper()


@dataclass
class Response:
    """Represents an HTTP response received from a request."""

    url: str
    status_code: int
    headers: dict[str, str]
    body: bytes
    cookies: dict[str, str] = field(default_factory=dict)
    request: Request | None = None
    elapsed_ms: float = 0.0
    encoding: str = "utf-8"

    @property
    def text(self) -> str:
        """Get response body as text."""
        return self.body.decode(self.encoding, errors="replace")

    @property
    def is_success(self) -> bool:
        """Check if response status indicates success."""
        return 200 <= self.status_code < 300

    @property
    def is_redirect(self) -> bool:
        """Check if response is a redirect."""
        return 300 <= self.status_code < 400


@dataclass
class Item:
    """Base class for scraped data items."""

    def to_dict(self) -> dict[str, Any]:
        """Convert item to dictionary."""
        return {
            key: value
            for key, value in self.__dict__.items()
            if not key.startswith("_")
        }

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def __setitem__(self, key: str, value: Any) -> None:
        setattr(self, key, value)


class IDownloader(Protocol):
    """Protocol for HTTP downloader implementations."""

    async def fetch(self, request: Request) -> Response:
        """
        Execute an HTTP request and return the response.

        Args:
            request: The request object containing URL, method, headers, etc.

        Returns:
            Response object with status code, headers, and body.

        Raises:
            DownloadError: If the request fails.
            DownloadTimeout: If the request times out.
            HTTPError: If the server returns an error status code.
        """
        ...


class IParser(Protocol):
    """Protocol for HTML/XML parser implementations."""

    def parse(self, content: str | bytes, content_type: str = "text/html") -> Any:
        """
        Parse raw content into a structured document.

        Args:
            content: Raw HTML or XML content.
            content_type: Type of content ('text/html', 'application/xml', etc.).

        Returns:
            Parsed document object.
        """
        ...

    def css(self, doc: Any, selector: str) -> list[Any]:
        """
        Select elements using CSS selector.

        Args:
            doc: Parsed document object.
            selector: CSS selector string.

        Returns:
            List of matched elements.
        """
        ...

    def xpath(self, doc: Any, selector: str) -> list[Any]:
        """
        Select elements using XPath expression.

        Args:
            doc: Parsed document object.
            selector: XPath expression string.

        Returns:
            List of matched elements.
        """
        ...

    def extract_text(self, element: Any) -> str:
        """
        Extract text content from an element.

        Args:
            element: Parsed element object.

        Returns:
            Text content as string.
        """
        ...

    def extract_attr(self, element: Any, attr_name: str) -> str | None:
        """
        Extract attribute value from an element.

        Args:
            element: Parsed element object.
            attr_name: Name of the attribute to extract.

        Returns:
            Attribute value or None if not found.
        """
        ...


class IStorage(Protocol):
    """Protocol for storage backend implementations."""

    async def initialize(self) -> None:
        """Initialize storage connection/resources."""
        ...

    async def save(self, item: Item) -> None:
        """
        Save a single item to storage.

        Args:
            item: The item to save.
        """
        ...

    async def save_many(self, items: list[Item]) -> None:
        """
        Save multiple items to storage.

        Args:
            items: List of items to save.
        """
        ...

    async def close(self) -> None:
        """Close storage connection/resources."""
        ...


class IMiddleware(Protocol):
    """Protocol for middleware implementations."""

    async def process_request(self, request: Request) -> Request | None:
        """
        Process outgoing request.

        Args:
            request: The request to process.

        Returns:
            Modified request, or None to continue processing chain.
        """
        ...

    async def process_response(
        self, request: Request, response: Response
    ) -> Response | None:
        """
        Process incoming response.

        Args:
            request: The original request.
            response: The response to process.

        Returns:
            Modified response, or None to continue processing chain.
        """
        ...


class IItemPipeline(Protocol):
    """Protocol for item pipeline stages."""

    async def process_item(self, item: Item, spider: Any) -> Item | None:
        """
        Process an extracted item.

        Args:
            item: The item to process.
            spider: The spider that extracted the item.

        Returns:
            Modified item, or None to drop the item.
        """
        ...


class ISpider(ABC):
    """Abstract base class for spider implementations."""

    name: str = ""
    start_urls: list[str] = []
    allowed_domains: list[str] = []

    @abstractmethod
    def parse(self, response: Response) -> Any:
        """
        Main parsing method to be implemented by subclasses.

        Args:
            response: The response to parse.

        Yields:
            Request objects for following pages or Item objects for data.
        """
        pass

    def start_requests(self) -> list[Request]:
        """Generate initial requests for the spider."""
        return [Request(url=url, callback="parse") for url in self.start_urls]
