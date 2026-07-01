# Scrapers Base Spider
"""
Base spider implementation for creating custom scrapers.

This module provides the base Spider class that users should inherit from
when creating their own scrapers. It includes helper methods and integration
with the core pipeline.
"""

from typing import Any, Generator
from urllib.parse import urlparse

import structlog

from src.core.interfaces import ISpider, Item, Request, Response
from src.core.exceptions import ScrapingError

logger = structlog.get_logger(__name__)


class Spider(ISpider):
    """
    Base class for all spiders.

    Users should inherit from this class and override:
    - name: Unique identifier for the spider
    - start_urls: List of URLs to begin scraping
    - parse(): Main parsing method

    Example:
        class MySpider(Spider):
            name = "my_spider"
            start_urls = ["https://example.com"]

            def parse(self, response: Response):
                title = response.parser.css(response.body, "h1")
                yield Item(title=title)
    """

    name: str = ""
    start_urls: list[str] = []
    allowed_domains: list[str] = []
    custom_settings: dict[str, Any] | None = None

    def __init__(self) -> None:
        if not self.name:
            raise ValueError("Spider must have a name")

        if not self.start_urls:
            logger.warning(f"Spider {self.name} has no start_urls")

        self._stats: dict[str, int] = {
            "pages_scraped": 0,
            "items_extracted": 0,
            "requests_followed": 0,
        }

    def start_requests(self) -> list[Request]:
        """
        Generate initial requests for the spider.

        Override this method to customize request generation (e.g., add headers,
        set callbacks, etc.).

        Returns:
            List of Request objects to start scraping.
        """
        requests = []
        for url in self.start_urls:
            if self._is_allowed_url(url):
                requests.append(
                    Request(
                        url=url,
                        callback="parse",
                        meta={"spider": self.name},
                    )
                )
            else:
                logger.debug(
                    f"URL not in allowed domains: {url}",
                    spider=self.name,
                )
        return requests

    def _is_allowed_url(self, url: str) -> bool:
        """Check if URL is in allowed domains."""
        if not self.allowed_domains:
            return True

        parsed = urlparse(url)
        domain = parsed.netloc

        # Remove 'www.' prefix for comparison
        domain = domain.replace("www.", "")

        return any(
            domain == allowed_domain.replace("www.", "") or
            domain.endswith("." + allowed_domain.replace("www.", ""))
            for allowed_domain in self.allowed_domains
        )

    def parse(self, response: Response) -> Generator[Item | Request | None, None, None]:
        """
        Main parsing method - MUST be overridden by subclasses.

        This method is called for each response received. It should:
        1. Extract data from the response
        2. Yield Item objects for data to be saved
        3. Yield Request objects for URLs to follow

        Args:
            response: Response object containing HTML content.

        Yields:
            Item objects or Request objects.

        Raises:
            NotImplementedError: If not overridden.
        """
        raise NotImplementedError("Spider.parse() must be overridden")

    def log(self, message: str, level: str = "info", **kwargs: Any) -> None:
        """
        Log a message with spider context.

        Args:
            message: Log message.
            level: Log level (debug, info, warning, error).
            **kwargs: Additional context for logging.
        """
        log_method = getattr(logger, level.lower(), logger.info)
        log_method(message, spider=self.name, **kwargs)

    @property
    def stats(self) -> dict[str, int]:
        """Get spider statistics."""
        return self._stats.copy()

    def _update_stats(self, key: str, value: int = 1) -> None:
        """Update internal statistics."""
        if key in self._stats:
            self._stats[key] += value


class BookSpider(Spider):
    """
    Example spider for scraping book information.

    This is a demonstration spider that shows how to implement
    a concrete scraper using the framework.

    Target: Books to Scrape (http://books.toscrape.com/)
    """

    name = "book_spider"
    start_urls = ["http://books.toscrape.com/"]
    allowed_domains = ["books.toscrape.com"]

    def parse(self, response: Response) -> Generator[Item | Request | None, None, None]:
        """
        Parse book listing page.

        Extracts book links and follows them to detail pages.
        """
        # Import parser here to avoid circular imports
        from src.infrastructure.parser import HybridParser

        parser = HybridParser()
        doc = parser.parse(response.text)

        # Extract book links
        book_links = parser.css(doc, "article.product_pod h3 a")

        for link in book_links:
            book_url = parser.extract_attr(link, "href")
            if book_url:
                # Convert relative URL to absolute
                full_url = response.urljoin(book_url) if hasattr(response, "urljoin") else book_url
                yield Request(
                    url=full_url,
                    callback="parse_book_detail",
                    meta={"spider": self.name},
                )

        # Follow pagination
        next_page = parser.css(doc, "li.next a")
        if next_page:
            next_url = parser.extract_attr(next_page[0], "href")
            if next_url:
                yield Request(
                    url=next_url,
                    callback="parse",
                    meta={"spider": self.name},
                )

    def parse_book_detail(self, response: Response) -> Generator[Item, None, None]:
        """
        Parse book detail page.

        Extracts book information and yields as Item.
        """
        from src.infrastructure.parser import HybridParser

        parser = HybridParser()
        doc = parser.parse(response.text)

        # Extract book details
        title_elements = parser.css(doc, "div.product_main h1")
        title = parser.extract_text(title_elements[0]) if title_elements else ""

        price_elements = parser.css(doc, "p.price_color")
        price = parser.extract_text(price_elements[0]) if price_elements else ""

        stock_elements = parser.css(doc, "p.instock.availability")
        stock = parser.extract_text(stock_elements[0]) if stock_elements else ""

        # Create item
        item = Item()
        item["title"] = title
        item["price"] = price
        item["stock"] = stock
        item["url"] = response.url
        item["spider"] = self.name

        self._update_stats("items_extracted")

        yield item


__all__ = ["Spider", "BookSpider"]
