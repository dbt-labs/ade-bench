"""Manages shared database files for ADE-Bench tasks."""

import shutil
import logging
import yaml
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum


class DatabaseType(Enum):
    DUCKDB = "duckdb"
    SQLITE = "sqlite"
    POSTGRES = "postgres"

    @classmethod
    def from_extension(cls, filepath: Path) -> "DatabaseType":
        """Determine database type from file extension."""
        ext = filepath.suffix.lower()
        if ext == ".duckdb":
            return cls.DUCKDB
        elif ext in [".db", ".sqlite", ".sqlite3"]:
            return cls.SQLITE
        elif ext == ".sql":
            return cls.POSTGRES
        else:
            raise ValueError(f"Unknown database extension: {ext}")


@dataclass
class DatabaseInfo:
    """Information about a shared database."""

    name: str
    type: DatabaseType
    path: Path
    size: int
    description: Optional[str] = None
    tables: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


class DatabasePoolManager:
    """Manages shared database files and provides copy-on-write functionality."""

    def __init__(
        self, shared_db_dir: Optional[Path] = None, logger: Optional[logging.Logger] = None
    ):
        self.logger = logger or logging.getLogger(__name__)
        self.shared_db_dir = (
            shared_db_dir or Path(__file__).parent.parent.parent / "shared" / "databases"
        )
        self.catalog_path = self.shared_db_dir / "catalog.yaml"
        self._catalog: Optional[Dict[str, Any]] = None

    @property
    def catalog(self) -> Dict[str, Any]:
        """Load catalog on demand."""
        if self._catalog is None:
            self._load_catalog()
        return self._catalog

    def _load_catalog(self) -> None:
        """Load the database catalog from disk."""
        if self.catalog_path.exists():
            with open(self.catalog_path, "r") as f:
                self._catalog = yaml.safe_load(f) or {"databases": {}}
        else:
            self._catalog = {"databases": {}}

    def _save_catalog(self) -> None:
        """Save the database catalog to disk."""
        self.catalog_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.catalog_path, "w") as f:
            yaml.dump(self._catalog, f, default_flow_style=False, sort_keys=False)

    def get_database(self, name: str, db_type: DatabaseType, target_dir: Path) -> Path:
        """
        Get a copy of a database file for use outside of containers.

        Note: For container use, it's more efficient to use find_database_file()
        and copy directly to the container.

        Args:
            name: Database name (without extension)
            db_type: Type of database
            target_dir: Directory to place the database copy

        Returns:
            Path to the database copy
        """
        # Find the database file
        db_path = self.find_database_file(name, db_type)
        if not db_path:
            raise FileNotFoundError(f"Database '{name}' of type {db_type.value} not found")

        target_dir.mkdir(parents=True, exist_ok=True)

        # Always create a copy in the target directory
        target_path = target_dir / db_path.name
        self.logger.info(f"Copying database {db_path} to {target_path}")

        # Use regular copy to ensure complete isolation
        shutil.copy2(db_path, target_path)

        return target_path

    def find_database_file(self, name: str, db_type: DatabaseType) -> Optional[Path]:
        """Find a database file by name and type."""
        type_dir = self.shared_db_dir / db_type.value
        if not type_dir.exists():
            return None

        # Try common extensions for the database type
        extensions = {
            DatabaseType.DUCKDB: [".duckdb"],
            DatabaseType.SQLITE: [".db", ".sqlite", ".sqlite3"],
            DatabaseType.POSTGRES: [".sql"],
        }

        for ext in extensions.get(db_type, []):
            db_path = type_dir / f"{name}{ext}"
            if db_path.exists():
                return db_path

        # Try to find by prefix match
        for db_file in type_dir.iterdir():
            if db_file.stem == name or db_file.stem.startswith(f"{name}_"):
                return db_file

        return None

    def register_database(
        self,
        db_path: Path,
        description: Optional[str] = None,
        tables: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DatabaseInfo:
        """
        Register a new database in the shared pool.

        Args:
            db_path: Path to the database file
            description: Description of the database
            tables: List of table names in the database
            tags: Tags for categorization
            metadata: Additional metadata

        Returns:
            DatabaseInfo object
        """
        if not db_path.exists():
            raise FileNotFoundError(f"Database file not found: {db_path}")

        # Determine database type
        db_type = DatabaseType.from_extension(db_path)

        # Copy to appropriate directory
        target_dir = self.shared_db_dir / db_type.value
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / db_path.name

        if target_path.exists():
            raise ValueError(f"Database already exists: {target_path}")

        shutil.copy2(db_path, target_path)

        # Create database info
        db_info = DatabaseInfo(
            name=db_path.stem,
            type=db_type,
            path=target_path,
            size=target_path.stat().st_size,
            description=description,
            tables=tables,
            tags=tags,
            metadata=metadata,
        )

        # Update catalog
        self.catalog["databases"][db_info.name] = {
            "type": db_type.value,
            "filename": target_path.name,
            "size": db_info.size,
            "description": description,
            "tables": tables,
            "tags": tags,
            "metadata": metadata,
        }
        self._save_catalog()

        self.logger.info(f"Registered database: {db_info.name}")
        return db_info

    def list_databases(self) -> List[DatabaseInfo]:
        """List all available shared databases."""
        databases = []

        # Scan all type directories
        for db_type in DatabaseType:
            type_dir = self.shared_db_dir / db_type.value
            if not type_dir.exists():
                continue

            for db_file in type_dir.iterdir():
                if db_file.is_file() and not db_file.name.startswith("."):
                    # Get info from catalog if available
                    catalog_info = self.catalog.get("databases", {}).get(db_file.stem, {})

                    db_info = DatabaseInfo(
                        name=db_file.stem,
                        type=db_type,
                        path=db_file,
                        size=db_file.stat().st_size,
                        description=catalog_info.get("description"),
                        tables=catalog_info.get("tables"),
                        tags=catalog_info.get("tags"),
                        metadata=catalog_info.get("metadata"),
                    )
                    databases.append(db_info)

        return sorted(databases, key=lambda x: (x.type.value, x.name))

    def remove_database(self, name: str, db_type: Optional[DatabaseType] = None) -> bool:
        """Remove a database from the shared pool."""
        # Find the database
        if db_type:
            db_path = self.find_database_file(name, db_type)
            if db_path and db_path.exists():
                db_path.unlink()
                self.logger.info(f"Removed database: {db_path}")

                # Update catalog
                if name in self.catalog.get("databases", {}):
                    del self.catalog["databases"][name]
                    self._save_catalog()

                return True
        else:
            # Try all types
            removed = False
            for dtype in DatabaseType:
                if self.remove_database(name, dtype):
                    removed = True
            return removed

        return False

    def get_database_info(
        self, name: str, db_type: Optional[DatabaseType] = None
    ) -> Optional[DatabaseInfo]:
        """Get information about a specific database."""
        if db_type:
            db_path = self.find_database_file(name, db_type)
            if db_path:
                catalog_info = self.catalog.get("databases", {}).get(name, {})
                return DatabaseInfo(
                    name=name,
                    type=db_type,
                    path=db_path,
                    size=db_path.stat().st_size,
                    description=catalog_info.get("description"),
                    tables=catalog_info.get("tables"),
                    tags=catalog_info.get("tags"),
                    metadata=catalog_info.get("metadata"),
                )
        else:
            # Try all types
            for dtype in DatabaseType:
                info = self.get_database_info(name, dtype)
                if info:
                    return info

        return None
