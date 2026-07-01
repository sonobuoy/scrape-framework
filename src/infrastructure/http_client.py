# Infrastructure HTTP Client
"""
HTTP client implementation using httpx.

This module provides a concrete implementation of the IDownloader interface
using the httpx library for high-performance async HTTP requests.
"""

import time
from typing import Any

import httpx
import structlog

from src.core.config import ScraperSettings, get_settings
from src.core.exceptions import (
    ConnectionError,
    DownloadError,
    DownloadTimeout,
    HTTPError,
)
from src.core.interfaces import IDownloader, Request, Response

logger = structlog.get_logger(__name__)


class HttpxDownloader:
    """
    Async HTTP downloader implementation using httpx.

    Features:
    - Connection pooling for efficiency
    - HTTP/2 support
    - Automatic retry handling (at middleware level)
    - Timeout management
    - Proxy support
    - Custom headers and cookies
    """

    def __init__(
        self,
        settings: ScraperSettings | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._client = client
        self._owns_client = client is None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create httpx async client with configured settings."""
        if self._client is not None:
            return self._client

        # Configure timeout
        timeout = httpx.Timeout(
            connect=self.settings.timeout.connect_timeout,
            read=self.settings.timeout.read_timeout,
            write=self.settings.timeout.write_timeout,
            pool=self.settings.timeout.pool_timeout,
        )

        # Configure limits
        limits = httpx.Limits(
            max_connections=self.settings.concurrency * 2,
            max_keepalive_connections=self.settings.concurrency,
        )

        # Build client
        self._client = httpx.AsyncClient(
            timeout=timeout,
            limits=limits,
            follow_redirects=self.settings.follow_redirects,
            max_redirects=self.settings.max_redirects,
            http2=True,  # Enable HTTP/2
            headers={
                "User-Agent": self.settings.user_agent_pool[0],
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            },
        )

        return self._client

    async def fetch(self, request: Request) -> Response:
        """
        Execute HTTP request and return response.

        Args:
            request: Request object with URL, method, headers, etc.

        Returns:
            Response object with status, headers, and body.

        Raises:
            DownloadTimeout: If request times out.
            ConnectionError: If connection cannot be established.
            HTTPError: If server returns error status code.
            DownloadError: For other download failures.
        """
        client = await self._get_client()

        # Prepare request kwargs
        headers = {**(request.headers or {})}
        
        # Set user agent from pool if not specified
        if "User-Agent" not in headers:
            headers["User-Agent"] = request.meta.get(
                "user_agent", self.settings.user_agent_pool[0]
            )

        try:
            start_time = time.time()

            response = await client.request(
                method=request.method,
                url=request.url,
                headers=headers,
                params=request.params,
                content=request.body if isinstance(request.body, bytes) else None,
                data=request.body if isinstance(request.body, str) else None,
                cookies=request.cookies,
            )

            elapsed_ms = (time.time() - start_time) * 1000

            logger.debug(
                "HTTP request completed",
                url=request.url,
                method=request.method,
                status=response.status_code,
                elapsed_ms=elapsed_ms,
            )

            # Check for HTTP errors
            if response.status_code >= 400:
                raise HTTPError(
                    status_code=response.status_code,
                    message=f"HTTP {response.status_code}: {response.reason_phrase}",
                    url=request.url,
                    context={"method": request.method, "headers": dict(response.headers)},
                )

            # Build response object
            return Response(
                url=str(response.url),
                status_code=response.status_code,
                headers=dict(response.headers),
                body=response.content,
                cookies=dict(response.cookies),
                elapsed_ms=elapsed_ms,
                encoding=response.encoding or "utf-8",
            )

        except httpx.TimeoutException as e:
            logger.warning("Request timed out", url=request.url, error=str(e))
            raise DownloadTimeout(
                f"Request to {request.url} timed out",
                context={"url": request.url, "timeout": self.settings.timeout.read_timeout},
            ) from e

        except httpx.ConnectError as e:
            logger.warning("Connection failed", url=request.url, error=str(e))
            raise ConnectionError(
                f"Failed to connect to {request.url}",
                context={"url": request.url},
            ) from e

        except httpx.RequestError as e:
            logger.error("Request failed", url=request.url, error=str(e))
            raise DownloadError(
                f"Request to {request.url} failed: {str(e)}",
                context={"url": request.url, "error_type": type(e).__name__},
            ) from e

        except Exception as e:
            logger.exception("Unexpected error during request", url=request.url)
            raise DownloadError(
                f"Unexpected error fetching {request.url}: {str(e)}",
                context={"url": request.url},
            ) from e

    async def close(self) -> None:
        """Close the HTTP client and release resources."""
        if self._client is not None and self._owns_client:
            await self._client.aclose()
            logger.info("HTTP client closed")


class DownloaderMiddleware:
    """Base class for downloader middlewares."""

    async def process_request(self, request: Request) -> Request | None:
        """Process outgoing request."""
        return request

    async def process_response(
        self, request: Request, response: Response
    ) -> Response | None:
        """Process incoming response."""
        return response


class UserAgentRotatorMiddleware(DownloaderMiddleware):
    """Middleware for rotating user agents."""

    def __init__(self, settings: ScraperSettings | None = None) -> None:
        self.settings = settings or get_settings()
        self._index = 0

    async def process_request(self, request: Request) -> Request | None:
        """Rotate user agent for each request."""
        if not request.headers or "User-Agent" not in request.headers:
            # Select next user agent from pool
            user_agent = self.settings.user_agent_pool[self._index % len(self.settings.user_agent_pool)]
            self._index += 1
            
            if request.headers is None:
                request.headers = {}
            request.headers["User-Agent"] = user_agent
            
            logger.debug("User agent rotated", user_agent=user_agent)

        return request


class ProxyRotatorMiddleware(DownloaderMiddleware):
    """Middleware for rotating proxies."""

    def __init__(
        self,
        settings: ScraperSettings | None = None,
        proxies: list[str] | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.proxies = proxies or self.settings.proxy_list
        self._index = 0

    async def process_request(self, request: Request) -> Request | None:
        """Set proxy for request if proxy rotation is enabled."""
        if not self.settings.proxy_rotation or not self.proxies:
            return request

        # Select next proxy
        proxy = self.proxies[self._index % len(self.proxies)]
        self._index += 1

        request.meta["proxy"] = proxy
        logger.debug("Proxy assigned", proxy=proxy)

        return request


class RetryMiddleware(DownloaderMiddleware):
    """Middleware for handling retries with exponential backoff."""

    def __init__(self, settings: ScraperSettings | None = None) -> None:
        self.settings = settings or get_settings()

    async def process_response(
        self, request: Request, response: Response
    ) -> Response | None:
        """Check if response should trigger a retry."""
        if response.status_code in self.settings.retry.retry_status_codes:
            if not request.dont_retry:
                current_retries = request.meta.get("_retry_count", 0)
                max_retries = request.max_retries or self.settings.retry.max_retries

                if current_retries < max_retries:
                    logger.warning(
                        "Response status triggers retry",
                        url=request.url,
                        status=response.status_code,
                        retries=current_retries,
                    )
                    # Raise error to trigger retry logic in engine
                    raise HTTPError(
                        status_code=response.status_code,
                        message=f"Retryable status code: {response.status_code}",
                        url=request.url,
                    )

        return response


__all__ = [
    "HttpxDownloader",
    "DownloaderMiddleware",
    "UserAgentRotatorMiddleware",
    "ProxyRotatorMiddleware",
    "RetryMiddleware",
]
