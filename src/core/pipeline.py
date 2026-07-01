# Core Pipeline Engine
"""
Main pipeline orchestration engine for the scraping framework.

This module implements the core scraping pipeline that coordinates:
1. Request scheduling and queue management
2. Downloader middleware chain
3. Response parsing
4. Item pipeline processing
5. Error handling and retry logic
"""

import asyncio
import random
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable

import structlog

from src.core.config import ScraperSettings, get_settings
from src.core.exceptions import (
    CircuitBreakerError,
    DownloadError,
    RetryError,
    ScrapingError,
)
from src.core.interfaces import (
    IDownloader,
    IItemPipeline,
    IMiddleware,
    IParser,
    IStorage,
    ISpider,
    Item,
    Request,
    Response,
)

logger = structlog.get_logger(__name__)


@dataclass
class CircuitBreaker:
    """Circuit breaker implementation for failure handling."""

    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    half_open_requests: int = 3

    failures: int = 0
    last_failure_time: float | None = None
    state: str = "closed"  # closed, open, half-open
    success_count: int = 0

    def record_failure(self) -> None:
        """Record a failure and potentially open the circuit."""
        self.failures += 1
        self.last_failure_time = time.time()
        if self.failures >= self.failure_threshold:
            self.state = "open"
            logger.warning("Circuit breaker opened", failures=self.failures)

    def record_success(self) -> None:
        """Record a success and potentially close the circuit."""
        if self.state == "half-open":
            self.success_count += 1
            if self.success_count >= self.half_open_requests:
                self.state = "closed"
                self.failures = 0
                self.success_count = 0
                logger.info("Circuit breaker closed")
        elif self.state == "closed":
            self.failures = max(0, self.failures - 1)

    def can_execute(self) -> bool:
        """Check if request can be executed based on circuit state."""
        if self.state == "closed":
            return True

        if self.state == "open":
            if (
                self.last_failure_time
                and (time.time() - self.last_failure_time) > self.recovery_timeout
            ):
                self.state = "half-open"
                self.success_count = 0
                logger.info("Circuit breaker half-open, testing...")
                return True
            return False

        return True  # half-open allows limited requests


@dataclass
class RequestQueue:
    """Priority queue for managing requests."""

    _queue: deque[Request] = field(default_factory=deque)
    _seen_urls: set[str] = field(default_factory=set)
    _pending: set[str] = field(default_factory=set)

    def add_request(self, request: Request) -> bool:
        """Add request to queue if not duplicate."""
        if request.url in self._seen_urls or request.url in self._pending:
            return False

        self._seen_urls.add(request.url)
        self._pending.add(request.url)

        if request.priority > 0:
            self._queue.appendleft(request)
        else:
            self._queue.append(request)

        return True

    def get_request(self) -> Request | None:
        """Get next request from queue."""
        if not self._queue:
            return None

        request = self._queue.popleft()
        self._pending.discard(request.url)
        return request

    def is_empty(self) -> bool:
        """Check if queue is empty."""
        return len(self._queue) == 0

    def size(self) -> int:
        """Get queue size."""
        return len(self._queue)


class ScraperEngine:
    """
    Main scraping engine that orchestrates the entire pipeline.

    This class manages the lifecycle of a scraping job, including:
    - Initializing components (downloader, parser, storage)
    - Processing request queue with concurrency control
    - Applying middleware chains
    - Handling errors and retries
    - Managing circuit breaker state
    """

    def __init__(
        self,
        downloader: IDownloader,
        parser: IParser,
        storage: IStorage,
        settings: ScraperSettings | None = None,
        downloader_middlewares: list[IMiddleware] | None = None,
        item_pipelines: list[IItemPipeline] | None = None,
    ) -> None:
        self.downloader = downloader
        self.parser = parser
        self.storage = storage
        self.settings = settings or get_settings()
        self.downloader_middlewares = downloader_middlewares or []
        self.item_pipelines = item_pipelines or []

        self.queue = RequestQueue()
        self.circuit_breaker = CircuitBreaker()
        self._running = False
        self._stats: dict[str, Any] = {
            "requests_sent": 0,
            "requests_failed": 0,
            "items_scraped": 0,
            "pages_scraped": 0,
            "start_time": None,
            "end_time": None,
        }

    async def run(self, spider: ISpider) -> dict[str, Any]:
        """
        Run the scraping engine with the given spider.

        Args:
            spider: Spider instance defining scraping logic.

        Returns:
            Statistics dictionary with scraping results.
        """
        logger.info("Starting scraper", spider_name=spider.name)
        self._running = True
        self._stats["start_time"] = time.time()

        try:
            # Initialize storage
            await self.storage.initialize()

            # Add initial requests from spider
            for request in spider.start_requests():
                self.queue.add_request(request)

            # Process queue with concurrency control
            await self._process_queue(spider)

        except Exception as e:
            logger.exception("Scraper failed", error=str(e))
            raise
        finally:
            await self.storage.close()
            self._running = False
            self._stats["end_time"] = time.time()
            self._stats["duration_seconds"] = (
                self._stats["end_time"] - self._stats["start_time"]
            )

            logger.info("Scraper finished", stats=self._stats)

        return self._stats

    async def _process_queue(self, spider: ISpider) -> None:
        """Process request queue with concurrency control."""
        semaphore = asyncio.Semaphore(self.settings.concurrency)
        tasks: list[asyncio.Task[None]] = []

        while self._running and (not self.queue.is_empty() or tasks):
            # Start new tasks up to concurrency limit
            while not self.queue.is_empty() and len(tasks) < self.settings.concurrency:
                request = self.queue.get_request()
                if request:
                    task = asyncio.create_task(
                        self._process_request_with_semaphore(request, spider, semaphore)
                    )
                    tasks.append(task)

            # Wait for at least one task to complete
            if tasks:
                done, pending = await asyncio.wait(
                    tasks, return_when=asyncio.FIRST_COMPLETED
                )
                tasks = list(pending)

                # Check for exceptions in completed tasks
                for task in done:
                    if task.exception():
                        logger.error("Task failed", error=str(task.exception()))

        # Wait for remaining tasks
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _process_request_with_semaphore(
        self, request: Request, spider: ISpider, semaphore: asyncio.Semaphore
    ) -> None:
        """Process single request with semaphore for concurrency control."""
        async with semaphore:
            await self._process_request(request, spider)

    async def _process_request(self, request: Request, spider: ISpider) -> None:
        """Process single request through the full pipeline."""
        # Check circuit breaker
        if not self.circuit_breaker.can_execute():
            logger.warning(
                "Request skipped due to open circuit breaker", url=request.url
            )
            return

        # Apply rate limiting
        delay = random.uniform(*self.settings.rate_limit.random_delay_range)
        await asyncio.sleep(delay)

        try:
            # Process through downloader middlewares
            processed_request = await self._run_downloader_middlewares(request)
            if processed_request is None:
                logger.debug("Request dropped by middleware", url=request.url)
                return

            # Fetch response
            self._stats["requests_sent"] += 1
            start_time = time.time()
            response = await self.downloader.fetch(processed_request)
            elapsed_ms = (time.time() - start_time) * 1000
            response.elapsed_ms = elapsed_ms
            response.request = processed_request

            self.circuit_breaker.record_success()
            self._stats["pages_scraped"] += 1

            logger.debug(
                "Response received",
                url=response.url,
                status=response.status_code,
                elapsed_ms=elapsed_ms,
            )

            # Parse response
            items = await self._parse_response(response, spider)

            # Process items through pipeline
            for item in items:
                await self._process_item(item, spider)

        except DownloadError as e:
            self.circuit_breaker.record_failure()
            self._stats["requests_failed"] += 1

            # Handle retry logic
            if not request.dont_retry and self._should_retry(request, e):
                await self._retry_request(request, spider, e)
            else:
                logger.error("Request failed permanently", url=request.url, error=str(e))

        except Exception as e:
            self.circuit_breaker.record_failure()
            logger.exception("Unexpected error processing request", url=request.url)
            raise

    async def _run_downloader_middlewares(
        self, request: Request
    ) -> Request | None:
        """Run request through downloader middleware chain."""
        current_request = request

        for middleware in self.downloader_middlewares:
            result = await middleware.process_request(current_request)
            if result is None:
                return None
            current_request = result

        return current_request

    async def _parse_response(self, response: Response, spider: ISpider) -> list[Item]:
        """Parse response and extract items/requests."""
        items: list[Item] = []

        if not response.is_success:
            logger.warning("Non-success response", url=response.url, status=response.status_code)
            return items

        # Get callback method from spider
        callback_name = response.request.callback if response.request else "parse"
        callback_method = getattr(spider, callback_name, None)
        if not callback_method:
            logger.error("Callback method not found", callback=callback_name)
            return items

        # Parse HTML
        doc = self.parser.parse(response.text)

        # Call spider's callback method (support sync, async, and async generator)
        try:
            import inspect
            if inspect.isasyncgenfunction(callback_method):
                # Handle async generator (most common for spiders)
                async for result in callback_method(response):
                    if isinstance(result, Item):
                        items.append(result)
                    elif isinstance(result, Request):
                        self.queue.add_request(result)
            elif inspect.iscoroutinefunction(callback_method):
                # Handle async function that returns a list/generator
                results = await callback_method(response)
                if results:
                    for result in results:
                        if isinstance(result, Item):
                            items.append(result)
                        elif isinstance(result, Request):
                            self.queue.add_request(result)
            else:
                # Handle sync generator or function
                results = callback_method(response)
                if results:
                    for result in results:
                        if isinstance(result, Item):
                            items.append(result)
                        elif isinstance(result, Request):
                            self.queue.add_request(result)
        except Exception as e:
            logger.exception("Error in spider callback", error=str(e))
            raise

        return items

    async def _process_item(self, item: Item, spider: ISpider) -> None:
        """Process item through item pipeline and save to storage."""
        current_item = item

        # Run through item pipelines
        for pipeline in self.item_pipelines:
            result = await pipeline.process_item(current_item, spider)
            if result is None:
                logger.debug("Item dropped by pipeline", item=current_item.to_dict())
                return
            current_item = result

        # Save to storage
        await self.storage.save(current_item)
        self._stats["items_scraped"] += 1

        logger.debug("Item saved", item=current_item.to_dict())

    def _should_retry(self, request: Request, error: Exception) -> bool:
        """Determine if request should be retried."""
        if isinstance(error, DownloadError):
            # Check status code if available
            if hasattr(error, "status_code"):
                return error.status_code in self.settings.retry.retry_status_codes
            return True
        return False

    async def _retry_request(
        self, request: Request, spider: ISpider, error: Exception
    ) -> None:
        """Retry a failed request with exponential backoff."""
        max_retries = request.max_retries or self.settings.retry.max_retries
        current_attempts = request.meta.get("_retry_count", 0)

        if current_attempts >= max_retries:
            raise RetryError(
                f"Max retries exceeded for {request.url}",
                attempts=current_attempts,
                last_exception=error,
            )

        # Calculate backoff delay
        backoff_factor = self.settings.retry.backoff_factor
        delay = (backoff_factor ** current_attempts) + random.uniform(0, 1)
        delay = min(delay, self.settings.retry.retry_timeout)

        logger.info(
            "Retrying request",
            url=request.url,
            attempt=current_attempts + 1,
            max_retries=max_retries,
            delay=delay,
        )

        # Update request metadata
        request.meta["_retry_count"] = current_attempts + 1

        # Wait and re-add to queue
        await asyncio.sleep(delay)
        self.queue.add_request(request)

    def stop(self) -> None:
        """Stop the scraping engine gracefully."""
        logger.info("Stopping scraper...")
        self._running = False


__all__ = ["ScraperEngine", "CircuitBreaker", "RequestQueue"]
