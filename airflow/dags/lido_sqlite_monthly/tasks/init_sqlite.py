"""
Task to initialize SQLite database schema for metadata storage.
"""

import logging
from pathlib import Path

from lido_sqlite_monthly.config import (
    FILE_SQLITE_DB,
    TABLE_NAME,
    PRAGMA_SETTINGS,
    INDEXES,
)
from lido_sqlite_monthly.utils.sqlite import (
    get_conn_metadata,
    apply_pragmas,
    create_indexes,
)

logger = logging.getLogger(__name__)


def task_init_sqlite_database() -> str:
    """
    Initialize SQLite database with metadata table schema.
    
    Creates:
    - metadata table with ECLI as primary key
    - optimized PRAGMA settings
    - query performance indexes
    
    Returns:
        Path to database file
        
    Raises:
        Exception: If table creation or PRAGMA setup fails
    """
    
    db_path = str(FILE_SQLITE_DB)
    logger.info(f"Initializing SQLite database at {db_path}")
    
    try:
        # Connect to database (creates it if not exists)
        conn = get_conn_metadata(db_path)
        cursor = conn.cursor()
        
        # Apply optimization pragmas
        logger.info("Applying PRAGMA settings for fast bulk inserts...")
        apply_pragmas(conn, PRAGMA_SETTINGS)
        
        # Create metadata table with comprehensive schema
        logger.info(f"Creating {TABLE_NAME} table...")
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                -- Primary key
                ecli TEXT PRIMARY KEY,
                
                -- Publication info
                date_publication TEXT,
                language TEXT,
                
                -- Court/instance info
                instance TEXT,
                jurisdiction_city TEXT,
                
                -- Decision info
                date_decision TEXT,
                case_number TEXT,
                document_type TEXT,
                procedure_type TEXT,
                
                -- Content categories
                domains TEXT,
                referenced_legislation_titles TEXT,
                alternative_publications TEXT,
                
                -- Case content
                title TEXT,
                full_text TEXT,
                summary TEXT,
                
                -- Relationships
                citing TEXT,
                cited_by TEXT,
                legislations_cited TEXT,
                predecessor_successor_cases TEXT,
                
                -- Metadata
                url_publications TEXT,
                info TEXT,
                source TEXT,
                spatial TEXT,
                bwb_id TEXT
            )
        """)
        
        conn.commit()
        logger.info(f"✓ Table {TABLE_NAME} created/verified")
        
        # Create indexes for query performance (Issue 4.1)
        logger.info("Creating query performance indexes...")
        create_indexes(conn, INDEXES)
        logger.info("✓ Indexes created")
        
        cursor.close()
        conn.close()
        
        logger.info(f"✓ Database initialization complete: {db_path}")
        return db_path
        
    except Exception as e:
        logger.error(f"✗ Database initialization failed: {e}")
        raise
