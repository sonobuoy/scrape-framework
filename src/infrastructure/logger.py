# Infrastructure Logger Configuration
"""
Logging configuration using structlog.

This module sets up structured logging for the scraping framework with
support for console and file output, rotating logs, and JSON formatting.
"""

import logging
import sys
from pathlib import Path
from typing import Any

import structlog
from structlog.types import Processor


def setup_logging(
    log_level: str = "INFO",
    log_format: str = "console",
    log_file: Path | None = None,
    rotate_max_bytes: int = 10_485_760,
    rotate_backup_count: int = 5,
) -> None:
    """
    Configure structured logging for the application.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_format: Output format ('console', 'json', 'structured').
        log_file: Optional path to log file.
        rotate_max_bytes: Maximum size of log file before rotation.
        rotate_backup_count: Number of backup log files to keep.
    """
    # Parse log level
    level = getattr(logging, log_level.upper(), logging.INFO)

    # Configure handlers
    handlers: list[logging.Handler] = []

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    handlers.append(console_handler)

    # File handler (if specified)
    if log_file:
        from logging.handlers import RotatingFileHandler

        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=rotate_max_bytes,
            backupCount=rotate_backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        handlers.append(file_handler)

    # Configure logging format
    if log_format == "json":
        # JSON format for production
        formatter = logging.Formatter(
            "%(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        processors: list[Processor] = [
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ]
    elif log_format == "structured":
        # Structured format for development
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        processors = [
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.dev.ConsoleRenderer(colors=True),
        ]
    else:
        # Console format (default)
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        processors = [
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    # Apply formatter to handlers
    for handler in handlers:
        handler.setFormatter(formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    for handler in handlers:
        root_logger.addHandler(handler)

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.BoundLogger:
    """
    Get a structured logger instance.

    Args:
        name: Optional logger name (usually __name__).

    Returns:
        Configured structlog BoundLogger.
    """
    return structlog.get_logger(name)


class LogContext:
    """Context manager for adding temporary context to logs."""

    def __init__(self, **kwargs: Any) -> None:
        self.context = kwargs
        self.logger: structlog.BoundLogger | None = None

    def __enter__(self) -> structlog.BoundLogger:
        self.logger = structlog.get_logger()
        for key, value in self.context.items():
            self.logger = self.logger.bind(**{key: value})
        return self.logger  # type: ignore[return-value]

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        # Context is automatically cleaned up
        pass


__all__ = ["setup_logging", "get_logger", "LogContext"]
