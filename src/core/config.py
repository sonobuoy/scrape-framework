# Core Configuration Management
"""
Configuration management using Pydantic Settings.

This module handles loading and validating configuration from multiple sources:
1. Default values in code
2. YAML configuration files
3. Environment variables
4. Command-line arguments (handled in main.py)
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class RetrySettings(BaseSettings):
    """Retry configuration settings."""

    max_retries: int = Field(default=3, ge=0, le=10)
    backoff_factor: float = Field(default=2.0, ge=1.0)
    retry_status_codes: list[int] = Field(
        default_factory=lambda: [429, 500, 502, 503, 504]
    )
    retry_timeout: float = Field(default=30.0, ge=0.1)


class TimeoutSettings(BaseSettings):
    """Timeout configuration settings."""

    connect_timeout: float = Field(default=10.0, ge=0.1)
    read_timeout: float = Field(default=30.0, ge=0.1)
    write_timeout: float = Field(default=10.0, ge=0.1)
    pool_timeout: float = Field(default=5.0, ge=0.1)


class RateLimitSettings(BaseSettings):
    """Rate limiting configuration settings."""

    requests_per_second: float = Field(default=1.0, gt=0.0)
    random_delay_range: tuple[float, float] = Field(default=(0.1, 0.5))
    per_domain_limit: bool = Field(default=True)


class StorageSettings(BaseSettings):
    """Storage backend configuration settings."""

    type: str = Field(default="json", pattern="^(json|csv|sqlite|postgres)$")
    output_dir: Path = Field(default=Path("./output"))
    database_url: str | None = None
    batch_size: int = Field(default=100, ge=1)

    @field_validator("output_dir")
    @classmethod
    def validate_output_dir(cls, v: Path) -> Path:
        """Ensure output directory exists."""
        v.mkdir(parents=True, exist_ok=True)
        return v


class LoggingSettings(BaseSettings):
    """Logging configuration settings."""

    level: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    format_type: str = Field(default="console", pattern="^(console|json|structured)$")
    log_file: Path | None = None
    rotate_max_bytes: int = Field(default=10_485_760, ge=1_048_576)  # 10MB
    rotate_backup_count: int = Field(default=5, ge=1)


class ScraperSettings(BaseSettings):
    """Main scraper configuration settings."""

    model_config = SettingsConfigDict(
        env_prefix="SCRAPER_",
        env_nested_delimiter="__",
        extra="ignore",
        case_sensitive=False,
    )

    # General settings
    concurrency: int = Field(default=10, ge=1, le=100)
    user_agent_pool: list[str] = Field(
        default_factory=lambda: [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        ]
    )
    respect_robots_txt: bool = Field(default=False)
    follow_redirects: bool = Field(default=True)
    max_redirects: int = Field(default=10, ge=0)

    # Sub-settings
    retry: RetrySettings = Field(default_factory=RetrySettings)
    timeout: TimeoutSettings = Field(default_factory=TimeoutSettings)
    rate_limit: RateLimitSettings = Field(default_factory=RateLimitSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)

    # Proxy settings
    proxy_url: str | None = Field(default=None)
    proxy_rotation: bool = Field(default=False)
    proxy_list: list[str] = Field(default_factory=list)

    @field_validator("user_agent_pool")
    @classmethod
    def validate_user_agents(cls, v: list[str]) -> list[str]:
        """Ensure at least one user agent is present."""
        if not v:
            raise ValueError("User agent pool cannot be empty")
        return v


def load_yaml_config(config_path: Path | str | None = None) -> dict[str, Any]:
    """
    Load configuration from a YAML file.

    Args:
        config_path: Path to the YAML configuration file.

    Returns:
        Dictionary containing configuration values.
    """
    if config_path is None:
        # Try default locations
        default_paths = [
            Path("./config/default.yaml"),
            Path("./scrape_framework/config/default.yaml"),
            Path(os.getenv("SCRAPER_CONFIG", "")) if os.getenv("SCRAPER_CONFIG") else None,
        ]
        for path in default_paths:
            if path and path.exists():
                config_path = path
                break

    if config_path is None or not Path(config_path).exists():
        return {}

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    return config or {}


@lru_cache()
def get_settings(config_path: str | None = None) -> ScraperSettings:
    """
    Get cached scraper settings instance.

    This function loads configuration from multiple sources with the following
    priority (highest to lowest):
    1. Environment variables (SCRAPER_* prefix)
    2. YAML configuration file
    3. Default values in code

    Args:
        config_path: Optional path to YAML configuration file.

    Returns:
        Validated ScraperSettings instance.
    """
    # Clear any existing SCRAPER_USER_AGENT_POOL env var that might be malformed
    if os.environ.get("SCRAPER_USER_AGENT_POOL"):
        del os.environ["SCRAPER_USER_AGENT_POOL"]

    # Load YAML config if provided
    yaml_config = load_yaml_config(config_path)

    # Flatten nested config for environment variable override
    # Pydantic Settings will handle the rest
    if yaml_config:
        # Set environment variables from YAML for values not overridden by env
        for key, value in _flatten_dict(yaml_config).items():
            env_key = f"SCRAPER_{key.upper()}"
            if env_key not in os.environ:
                os.environ[env_key] = str(value)

    return ScraperSettings()


def _flatten_dict(d: dict[str, Any], parent_key: str = "", sep: str = "__") -> dict[str, Any]:
    """
    Flatten a nested dictionary for environment variable mapping.

    Args:
        d: Dictionary to flatten.
        parent_key: Parent key prefix.
        sep: Separator between keys.

    Returns:
        Flattened dictionary.
    """
    items: list[tuple[str, Any]] = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(_flatten_dict(v, new_key, sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


__all__ = [
    "ScraperSettings",
    "RetrySettings",
    "TimeoutSettings",
    "RateLimitSettings",
    "StorageSettings",
    "LoggingSettings",
    "get_settings",
    "load_yaml_config",
]
