# Infrastructure Storage Backends
"""
Storage backend implementations for scraped data.

This module provides concrete implementations of the IStorage interface
for various storage backends: JSON files, CSV files, and SQLite databases.
"""

import csv
import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import structlog
from sqlalchemy import Column, Integer, String, Text, create_engine, text
from sqlalchemy.orm import Session, declarative_base

from src.core.config import ScraperSettings, get_settings
from src.core.exceptions import StorageError
from src.core.interfaces import IStorage, Item

logger = structlog.get_logger(__name__)

Base = declarative_base()


class DynamicItemModel(Base):
    """Dynamic SQLAlchemy model for storing items."""

    __tablename__ = "scraped_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    item_type = Column(String(100), nullable=False)
    data = Column(Text, nullable=False)  # JSON string

    def __repr__(self) -> str:
        return f"<DynamicItemModel(id={self.id}, type={self.item_type})>"


class BaseStorage(ABC):
    """Abstract base class for storage implementations."""

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize storage resources."""
        pass

    @abstractmethod
    async def save(self, item: Item) -> None:
        """Save a single item."""
        pass

    @abstractmethod
    async def save_many(self, items: list[Item]) -> None:
        """Save multiple items."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close storage resources."""
        pass


class JsonStorage(BaseStorage):
    """
    Storage backend that saves items to JSON files.

    Features:
    - One file per spider
    - Append mode for incremental saving
    - Pretty-printed output
    """

    def __init__(
        self,
        settings: ScraperSettings | None = None,
        filename: str | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.filename = filename or "scraped_data.json"
        self.file_path = self.settings.storage.output_dir / self.filename
        self._initialized = False
        self._items: list[dict[str, Any]] = []

    async def initialize(self) -> None:
        """Ensure output directory exists."""
        self.settings.storage.output_dir.mkdir(parents=True, exist_ok=True)
        self._initialized = True
        logger.info("JSON storage initialized", path=str(self.file_path))

    async def save(self, item: Item) -> None:
        """Save item to in-memory list."""
        if not self._initialized:
            raise StorageError("Storage not initialized")

        self._items.append(item.to_dict())
        logger.debug("Item queued for JSON storage", item=item.to_dict())

    async def save_many(self, items: list[Item]) -> None:
        """Save multiple items."""
        for item in items:
            await self.save(item)

    async def close(self) -> None:
        """Write all items to JSON file."""
        if self._items:
            try:
                # Load existing data if file exists
                existing_data: list[dict[str, Any]] = []
                if self.file_path.exists():
                    with open(self.file_path, "r", encoding="utf-8") as f:
                        existing_data = json.load(f)

                # Append new items
                existing_data.extend(self._items)

                # Write back
                with open(self.file_path, "w", encoding="utf-8") as f:
                    json.dump(existing_data, f, indent=2, ensure_ascii=False)

                logger.info(
                    "JSON storage closed",
                    path=str(self.file_path),
                    items_written=len(self._items),
                )
            except Exception as e:
                logger.exception("Failed to write JSON file", error=str(e))
                raise StorageError(f"Failed to write JSON: {str(e)}") from e

        self._items.clear()


class CsvStorage(BaseStorage):
    """
    Storage backend that saves items to CSV files.

    Features:
    - Automatic header detection
    - Append mode support
    - UTF-8 encoding
    """

    def __init__(
        self,
        settings: ScraperSettings | None = None,
        filename: str | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.filename = filename or "scraped_data.csv"
        self.file_path = self.settings.storage.output_dir / self.filename
        self._initialized = False
        self._items: list[dict[str, Any]] = []
        self._fieldnames: list[str] | None = None

    async def initialize(self) -> None:
        """Ensure output directory exists."""
        self.settings.storage.output_dir.mkdir(parents=True, exist_ok=True)
        self._initialized = True
        logger.info("CSV storage initialized", path=str(self.file_path))

    async def save(self, item: Item) -> None:
        """Save item to in-memory list."""
        if not self._initialized:
            raise StorageError("Storage not initialized")

        item_dict = item.to_dict()
        self._items.append(item_dict)

        # Update fieldnames
        if self._fieldnames is None:
            self._fieldnames = list(item_dict.keys())
        else:
            # Add new keys if found
            for key in item_dict.keys():
                if key not in self._fieldnames:
                    self._fieldnames.append(key)

        logger.debug("Item queued for CSV storage", item=item_dict)

    async def save_many(self, items: list[Item]) -> None:
        """Save multiple items."""
        for item in items:
            await self.save(item)

    async def close(self) -> None:
        """Write all items to CSV file."""
        if self._items and self._fieldnames:
            try:
                file_exists = self.file_path.exists()

                with open(
                    self.file_path, "a", newline="", encoding="utf-8"
                ) as f:
                    writer = csv.DictWriter(f, fieldnames=self._fieldnames)

                    # Write header if new file
                    if not file_exists:
                        writer.writeheader()

                    writer.writerows(self._items)

                logger.info(
                    "CSV storage closed",
                    path=str(self.file_path),
                    items_written=len(self._items),
                )
            except Exception as e:
                logger.exception("Failed to write CSV file", error=str(e))
                raise StorageError(f"Failed to write CSV: {str(e)}") from e

        self._items.clear()


class SqliteStorage(BaseStorage):
    """
    Storage backend that saves items to SQLite database.

    Features:
    - Persistent storage
    - Query capability
    - Transaction support
    """

    def __init__(
        self,
        settings: ScraperSettings | None = None,
        database_url: str | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.database_url = database_url or f"sqlite:///{self.settings.storage.output_dir}/scraped_data.db"
        self._engine = None
        self._session: Session | None = None

    async def initialize(self) -> None:
        """Create database engine and tables."""
        try:
            self._engine = create_engine(self.database_url, echo=False)
            Base.metadata.create_all(self._engine)
            logger.info("SQLite storage initialized", database=self.database_url)
        except Exception as e:
            logger.exception("Failed to initialize SQLite", error=str(e))
            raise StorageError(f"Failed to initialize SQLite: {str(e)}") from e

    async def save(self, item: Item) -> None:
        """Save single item to database."""
        if self._engine is None:
            raise StorageError("Storage not initialized")

        try:
            with Session(self._engine) as session:
                item_dict = item.to_dict()
                model = DynamicItemModel(
                    item_type=item.__class__.__name__,
                    data=json.dumps(item_dict, ensure_ascii=False),
                )
                session.add(model)
                session.commit()
                logger.debug("Item saved to SQLite", item_type=item.__class__.__name__)
        except Exception as e:
            logger.exception("Failed to save item to SQLite", error=str(e))
            raise StorageError(f"Failed to save to SQLite: {str(e)}") from e

    async def save_many(self, items: list[Item]) -> None:
        """Save multiple items in batch."""
        if self._engine is None:
            raise StorageError("Storage not initialized")

        try:
            with Session(self._engine) as session:
                for item in items:
                    item_dict = item.to_dict()
                    model = DynamicItemModel(
                        item_type=item.__class__.__name__,
                        data=json.dumps(item_dict, ensure_ascii=False),
                    )
                    session.add(model)
                session.commit()
                logger.info("Batch saved to SQLite", count=len(items))
        except Exception as e:
            logger.exception("Failed to save batch to SQLite", error=str(e))
            raise StorageError(f"Failed to save batch to SQLite: {str(e)}") from e

    async def close(self) -> None:
        """Dispose database engine."""
        if self._engine is not None:
            self._engine.dispose()
            logger.info("SQLite storage closed")


def create_storage(
    storage_type: str | None = None,
    settings: ScraperSettings | None = None,
    **kwargs: Any,
) -> IStorage:
    """
    Factory function to create appropriate storage backend.

    Args:
        storage_type: Type of storage ('json', 'csv', 'sqlite').
        settings: Scraper settings.
        **kwargs: Additional arguments for specific storage backends.

    Returns:
        Configured storage instance.

    Raises:
        ValueError: If storage_type is not recognized.
    """
    settings = settings or get_settings()
    storage_type = storage_type or settings.storage.type

    if storage_type == "json":
        return JsonStorage(settings=settings, **kwargs)
    elif storage_type == "csv":
        return CsvStorage(settings=settings, **kwargs)
    elif storage_type == "sqlite":
        return SqliteStorage(settings=settings, **kwargs)
    else:
        raise ValueError(f"Unknown storage type: {storage_type}")


__all__ = [
    "BaseStorage",
    "JsonStorage",
    "CsvStorage",
    "SqliteStorage",
    "create_storage",
]
