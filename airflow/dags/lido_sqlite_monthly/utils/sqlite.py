"""
SQLite utilities for lido_sqlite_monthly DAG.

NOTE: This module wraps/extends lido.utils.sqlite.
The base get_conn() function is imported from lido's utilities to avoid duplication.
"""

import sqlite3
import logging
from typing import Optional

# Import base function from lido to avoid duplication (Issue 2.2)
from lido.utils.sqlite import get_conn

logger = logging.getLogger(__name__)


def get_conn_metadata(db: str) -> sqlite3.Connection:
    """
    Get SQLite connection for metadata database.
    
    This is a wrapper around lido.utils.sqlite.get_conn() for consistency.
    
    Args:
        db: Path to database file
        
    Returns:
        sqlite3.Connection object
    """
    return get_conn(db)


def cursor_is_sqlite(cursor) -> bool:
    """Check if cursor is SQLite."""
    return isinstance(cursor, sqlite3.Cursor)


def apply_pragmas(conn: sqlite3.Connection, pragmas: dict) -> None:
    """
    Apply SQLite PRAGMA settings for optimization.
    
    Args:
        conn: Database connection
        pragmas: Dictionary of {setting: value}
    """
    cursor = conn.cursor()
    for setting, value in pragmas.items():
        try:
            cursor.execute(f"PRAGMA {setting} = {value}")
            logger.debug(f"✓ PRAGMA {setting} = {value}")
        except Exception as e:
            logger.warning(f"Could not set PRAGMA {setting}: {e}")
    
    conn.commit()
    cursor.close()


def create_indexes(conn: sqlite3.Connection, indexes: list) -> None:
    """
    Create indexes on table columns.
    
    Args:
        conn: Database connection
        indexes: List of (table_name, [column, ...]) tuples
    """
    cursor = conn.cursor()
    
    for table_name, columns in indexes:
        columns_str = ", ".join(columns)
        index_name = f"idx_{table_name}_{'_'.join(columns)}"
        
        try:
            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS {index_name} 
                ON {table_name} ({columns_str})
            """)
            logger.debug(f"✓ Created index {index_name}")
        except Exception as e:
            logger.warning(f"Could not create index {index_name}: {e}")
    
    conn.commit()
    cursor.close()


def validate_database(db_path: str, table_name: str) -> bool:
    """
    Validate database integrity after build.
    
    Checks:
    - File exists and is readable
    - Database can be connected
    - Table exists
    - Table has records
    
    Args:
        db_path: Path to database file
        table_name: Name of table to validate
        
    Returns:
        True if valid, False otherwise
    """
    try:
        conn = get_conn_metadata(db_path)
        cursor = conn.cursor()
        
        # Check table exists
        cursor.execute(f"""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='{table_name}'
        """)
        if not cursor.fetchone():
            logger.error(f"✗ Table {table_name} does not exist")
            conn.close()
            return False
        
        # Check record count
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        
        if count == 0:
            logger.error(f"✗ Table {table_name} has no records")
            conn.close()
            return False
        
        logger.info(f"✓ Database valid: {count} records in {table_name}")
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"✗ Database validation failed: {e}")
        return False
