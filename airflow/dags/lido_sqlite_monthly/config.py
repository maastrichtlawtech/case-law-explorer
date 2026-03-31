"""
Configuration for lido_sqlite_monthly DAG.

This module centralizes all configuration values for the SQLite metadata database
built from LIDO exports. Values can be overridden via Airflow Variables.
"""

import os
from pathlib import Path

# ============================================================================
# Directory and File Paths
# ============================================================================

# Root directories
DIR_ROOT = Path(__file__).parent.parent.parent  # airflow/ directory
DIR_DATA = DIR_ROOT / "data"
DIR_DATA_LIDO = DIR_DATA / "lido"

# Ensure directories exist
DIR_DATA.mkdir(exist_ok=True, parents=True)
DIR_DATA_LIDO.mkdir(exist_ok=True, parents=True)

# File paths
FILE_LIDO_TTL_GZ = DIR_DATA_LIDO / "lido-export.ttl.gz"
FILE_SQLITE_DB = DIR_DATA_LIDO / "lido_metadata.db"

# ============================================================================
# URLs and Download Configuration
# ============================================================================

# LIDO export source
URL_LIDO_TTL_GZ = "https://linkeddata.overheid.nl/export/lido-export.ttl.gz"

# Download configuration
DOWNLOAD_CHUNK_SIZE = 1024 * 1024 * 5  # 5MB chunks
DOWNLOAD_TIMEOUT = 300  # seconds
MIN_FILE_SIZE = 1_000_000  # 1MB minimum (sanity check)

# ============================================================================
# SQLite Database Configuration
# ============================================================================

# Table name for metadata
TABLE_NAME = "metadata"

# SQLite PRAGMA settings for fast bulk inserts
PRAGMA_SETTINGS = {
    "synchronous": "OFF",
    "journal_mode": "MEMORY",
    "cache_size": "-64000",  # 64MB cache
    "temp_store": "MEMORY",
    "busy_timeout": "5000",  # 5 second lock timeout
}

# Database indexes for query performance
INDEXES = [
    (TABLE_NAME, ["date_publication"]),
    (TABLE_NAME, ["instance"]),
    (TABLE_NAME, ["date_decision"]),
    (TABLE_NAME, ["source"]),
]

# ============================================================================
# Data Processing Configuration
# ============================================================================

# Batch size for committing inserts (number of records)
BATCH_SIZE = 50000

# Logging interval (log progress every N lines)
LOG_INTERVAL = 100000

# ============================================================================
# LIDO RDF Predicates Mapping
# Mapping from full predicate URIs to field names
# ============================================================================

PREDICATE_FIELD_MAP = {
    # Case identifier
    "http://purl.org/dc/terms/identifier": "ecli",
    
    # Court/instance info
    "http://purl.org/dc/terms/creator": "instance",
    
    # Dates
    "http://purl.org/dc/terms/date": "date_decision",
    "http://purl.org/dc/terms/issued": "date_publication",
    
    # Text fields
    "http://purl.org/dc/terms/title": "title",
    "http://purl.org/dc/terms/description": "info",
    
    # Language and location
    "http://purl.org/dc/terms/language": "language",
    "http://purl.org/dc/terms/spatial": "spatial",
    
    # Case specifics
    "http://psi.rechtspraak.nl/zaaknummer": "case_number",
    "http://purl.org/dc/terms/type": "document_type",
    "http://purl.org/dc/terms/subject": "domains",
    "http://psi.rechtspraak.nl/procedure": "procedure_type",
    
    # Summary (case law content)
    # Note: "inhoudsindicatie" appears without full URI wrapping in some triples
    
    # Relationships
    "http://purl.org/dc/terms/hasVersion": "alternative_publications",
    "http://linkeddata.overheid.nl/terms/refereertAan": "legislations_cited",
    "http://linkeddata.overheid.nl/terms/linkt": "citing",
    "http://purl.org/dc/terms/references": "referenced_legislation_titles",
    "http://purl.org/dc/terms/relation": "predecessor_successor_cases",
}

# Predicates to filter on (used in BASH pipeline for scrdi output)
# These are the predicates we care about from the LIDO export
LIDO_RELEVANT_PREDICATES = list(PREDICATE_FIELD_MAP.keys()) + [
    "http://linkeddata.overheid.nl/terms/heeftZaaknummer",
    "inhoudsindicatio",  # Summary - special case (no full URI)
]

# LIDO filter for case law only (not legislation)
LIDO_CASE_LAW_FILTER = "http://linkeddata.overheid.nl/terms/jurisprudentie/id/"

# ============================================================================
# Task Configuration
# ============================================================================

# Task defaults
TASK_OWNER = "airflow"
TASK_RETRIES = 1
TASK_RETRY_DELAY_MINUTES = 5
TASK_EXECUTION_TIMEOUT_HOURS = 8  # Large downloads + processing

# ============================================================================
# Logging Configuration
# ============================================================================

LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_LEVEL = "INFO"
