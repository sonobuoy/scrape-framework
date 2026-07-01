#!/usr/bin/env python3
"""
Main CLI entry point for the scraping framework.

This module provides the command-line interface for running scrapers,
managing configuration, and viewing statistics.
"""

import argparse
import asyncio
import sys
from typing import Any

import structlog

from src.core.config import get_settings, load_yaml_config
from src.core.pipeline import ScraperEngine
from src.infrastructure.http_client import (
    HttpxDownloader,
    UserAgentRotatorMiddleware,
)
from src.infrastructure.logger import setup_logging
from src.infrastructure.parser import HybridParser
from src.infrastructure.storage import create_storage
from src.scrapers.base_spider import BookSpider, Spider


def get_spider_by_name(name: str) -> Spider | None:
    """
    Get spider instance by name.

    Args:
        name: Name of the spider class.

    Returns:
        Spider instance or None if not found.
    """
    # Registry of available spiders
    spiders: dict[str, type[Spider]] = {
        "book": BookSpider,
    }

    spider_class = spiders.get(name.lower())
    if spider_class:
        return spider_class()

    return None


def list_spiders() -> None:
    """List all available spiders."""
    print("\nAvailable spiders:")
    print("-" * 40)

    spiders = {
        "book": "Example spider for books.toscrape.com",
    }

    for name, description in spiders.items():
        print(f"  {name:15} - {description}")

    print()


async def run_spider(
    spider_name: str,
    config_file: str | None = None,
    log_level: str = "INFO",
    storage_type: str | None = None,
    concurrency: int | None = None,
) -> dict[str, Any]:
    """
    Run a spider with the given configuration.

    Args:
        spider_name: Name of the spider to run.
        config_file: Path to YAML configuration file.
        log_level: Logging level.
        storage_type: Override storage type.
        concurrency: Override concurrency setting.

    Returns:
        Statistics dictionary.

    Raises:
        ValueError: If spider not found.
    """
    # Setup logging
    settings = get_settings(config_file)

    # Override settings if provided
    if log_level:
        settings.logging.level = log_level
    if concurrency:
        settings.concurrency = concurrency
    if storage_type:
        settings.storage.type = storage_type

    # Initialize logging
    setup_logging(
        log_level=settings.logging.level,
        log_format=settings.logging.format_type,
        log_file=settings.logging.log_file,
        rotate_max_bytes=settings.logging.rotate_max_bytes,
        rotate_backup_count=settings.logging.rotate_backup_count,
    )

    logger = structlog.get_logger(__name__)
    logger.info("Starting scraper framework", spider=spider_name)

    # Get spider instance
    spider = get_spider_by_name(spider_name)
    if not spider:
        raise ValueError(f"Spider '{spider_name}' not found. Use 'list' to see available spiders.")

    # Initialize components
    downloader = HttpxDownloader(settings=settings)
    parser = HybridParser()
    storage = create_storage(storage_type=settings.storage.type, settings=settings)

    # Initialize middlewares
    downloader_middlewares = [
        UserAgentRotatorMiddleware(settings=settings),
    ]

    # Create engine
    engine = ScraperEngine(
        downloader=downloader,
        parser=parser,
        storage=storage,
        settings=settings,
        downloader_middlewares=downloader_middlewares,
    )

    try:
        # Run spider
        stats = await engine.run(spider)
        return stats

    except KeyboardInterrupt:
        logger.info("Scraper interrupted by user")
        engine.stop()
        return {"interrupted": True}

    except Exception as e:
        logger.exception("Scraper failed", error=str(e))
        raise


def main() -> int:
    """
    Main CLI entry point.

    Returns:
        Exit code (0 for success, non-zero for errors).
    """
    parser = argparse.ArgumentParser(
        prog="scrape-cli",
        description="Web Scraping Framework CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  scrape-cli run book                 Run the book spider
  scrape-cli run book --concurrency 5 Run with 5 concurrent requests
  scrape-cli run book --storage csv   Save results to CSV
  scrape-cli list                     List available spiders
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Run command
    run_parser = subparsers.add_parser("run", help="Run a spider")
    run_parser.add_argument(
        "spider",
        type=str,
        help="Name of the spider to run",
    )
    run_parser.add_argument(
        "--config", "-c",
        type=str,
        default=None,
        help="Path to YAML configuration file",
    )
    run_parser.add_argument(
        "--log-level", "-l",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level",
    )
    run_parser.add_argument(
        "--storage", "-s",
        type=str,
        choices=["json", "csv", "sqlite"],
        default=None,
        help="Storage backend type",
    )
    run_parser.add_argument(
        "--concurrency", "-j",
        type=int,
        default=None,
        help="Number of concurrent requests",
    )

    # List command
    subparsers.add_parser("list", help="List available spiders")

    args = parser.parse_args()

    if args.command == "list":
        list_spiders()
        return 0

    elif args.command == "run":
        try:
            stats = asyncio.run(
                run_spider(
                    spider_name=args.spider,
                    config_file=args.config,
                    log_level=args.log_level,
                    storage_type=args.storage,
                    concurrency=args.concurrency,
                )
            )

            # Print summary
            print("\n" + "=" * 50)
            print("SCRAPING COMPLETE")
            print("=" * 50)
            print(f"Pages scraped:     {stats.get('pages_scraped', 0)}")
            print(f"Items extracted:   {stats.get('items_scraped', 0)}")
            print(f"Requests failed:   {stats.get('requests_failed', 0)}")
            print(f"Duration:          {stats.get('duration_seconds', 0):.2f}s")
            print("=" * 50 + "\n")

            return 0

        except ValueError as e:
            print(f"\nError: {e}\n", file=sys.stderr)
            return 1

        except Exception as e:
            print(f"\nFatal error: {e}\n", file=sys.stderr)
            return 1

    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
