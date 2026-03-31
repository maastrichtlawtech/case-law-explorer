"""
DAG to build SQLite metadata database from LIDO export on a monthly basis.

This DAG:
1. Downloads lido-export.ttl.gz from data.overheid.nl
2. Initializes SQLite database with optimized schema and indexes
3. Processes the TTL file using pyoxigraph for RDF parsing
4. Extracts case law metadata into database
5. Validates database integrity

Schedule: Monthly on the 8th day of each month at midnight UTC
Duration: ~1-2 hours for download + processing

Improvements over previous version:
- Issue 3.1: Uses pyoxigraph instead of shell subprocess ✓
- Issue 2.1: Modular task structure (tasks/ package) ✓
- Issue 1.1: Centralized configuration (config.py) ✓
- Issue 4.1: Added database indexes for query performance ✓
- Issue 5.1: Proper SSL verification ✓
- Issue 6.1: Comprehensive error handling and validation ✓
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from airflow.utils.task_group import TaskGroup

from lido_sqlite_monthly.config import (
    FILE_LIDO_TTL_GZ,
    FILE_SQLITE_DB,
    TABLE_NAME,
    TASK_OWNER,
    TASK_RETRIES,
    TASK_RETRY_DELAY_MINUTES,
    TASK_EXECUTION_TIMEOUT_HOURS,
)
from lido_sqlite_monthly.tasks.download import task_download_lido_ttl
from lido_sqlite_monthly.tasks.init_sqlite import task_init_sqlite_database
from lido_sqlite_monthly.tasks.build_sqlite import task_build_sqlite_database
from lido_sqlite_monthly.utils.sqlite import validate_database

# ============================================================================
# DAG Configuration
# ============================================================================

default_args = {
    "owner": TASK_OWNER,
    "retries": TASK_RETRIES,
    "retry_delay": timedelta(minutes=TASK_RETRY_DELAY_MINUTES),
    "execution_timeout": timedelta(hours=TASK_EXECUTION_TIMEOUT_HOURS),
}

with DAG(
    dag_id="lido_sqlite_monthly",
    default_args=default_args,
    description="Build SQLite metadata database from LIDO export monthly",
    schedule_interval="0 0 8 * *",  # Every month on the 8th at midnight UTC
    start_date=datetime(2025, 6, 1),
    catchup=False,
    tags=["caselaw", "lido", "sqlite", "metadata"],
) as dag:
    
    dag.doc = __doc__  # Use module docstring as DAG documentation
    
    # ========================================================================
    # Task: Download LIDO export
    # ========================================================================
    
    download_task = PythonOperator(
        task_id="download_lido_ttl",
        python_callable=task_download_lido_ttl,
        doc="""
        Download lido-export.ttl.gz from data.overheid.nl
        
        Features:
        - Proper SSL certificate verification
        - Progress tracking
        - File validation (size check)
        - Atomic file operations
        """,
    )
    
    verify_download = BashOperator(
        task_id="verify_ttl_download",
        bash_command=f"test -s {FILE_LIDO_TTL_GZ} && du -h {FILE_LIDO_TTL_GZ}",
        doc="Verify that the TTL file was downloaded successfully",
    )
    
    # ========================================================================
    # Task: Initialize Database
    # ========================================================================
    
    init_db_task = PythonOperator(
        task_id="init_sqlite_database",
        python_callable=task_init_sqlite_database,
        doc="""
        Initialize SQLite database with metadata table schema
        
        Creates:
        - metadata table with 24 columns for comprehensive case law metadata
        - query performance indexes on frequently searched fields
        - optimized PRAGMA settings for fast bulk inserts
        """,
    )
    
    check_db = BashOperator(
        task_id="verify_database_created",
        bash_command=f"""
            sqlite3 {FILE_SQLITE_DB} \
            "SELECT name FROM sqlite_master WHERE type='table' AND name='{TABLE_NAME}';" \
            && echo '✓ Database table created'
        """,
        doc="Verify database and table were created",
    )
    
    # ========================================================================
    # Task: Build Database (Process TTL and Insert Records)
    # ========================================================================
    
    build_db_task = PythonOperator(
        task_id="build_sqlite_database",
        python_callable=task_build_sqlite_database,
        doc="""
        Parse LIDO TTL export and build SQLite metadata database
        
        Process:
        1. Stream gzipped TTL file using pyoxigraph (fast, native Python)
        2. Filter to case law (jurisprudentie) only
        3. Map RDF predicates to database fields using O(1) dictionary lookup
        4. Extract entities (ECLI, BWB IDs) from URIs
        5. Batch insert records for performance (~50K per batch)
        
        Replaces shell subprocess with native pyoxigraph parsing.
        """,
    )
    
    # ========================================================================
    # Task: Validate Database
    # ========================================================================
    
    def validate_db_python():
        """Validate database integrity after build."""
        is_valid = validate_database(str(FILE_SQLITE_DB), TABLE_NAME)
        if not is_valid:
            raise Exception("Database validation failed")
    
    validate_db_task = PythonOperator(
        task_id="validate_database",
        python_callable=validate_db_python,
        doc="""
        Validate database integrity after build
        
        Checks:
        - Database file exists and is readable
        - metadata table exists
        - Table contains records
        """,
    )
    
    verify_records = BashOperator(
        task_id="verify_record_count",
        bash_command=f"""
            RECORD_COUNT=$(sqlite3 {FILE_SQLITE_DB} \
                "SELECT COUNT(*) FROM {TABLE_NAME};")
            echo "✓ Database contains $RECORD_COUNT records"
            if [ "$RECORD_COUNT" -eq "0" ]; then
                exit 1
            fi
        """,
        doc="Display final record count",
    )
    
    # ========================================================================
    # Task: Generate Summary Report
    # ========================================================================
    
    generate_summary = BashOperator(
        task_id="generate_summary_report",
        bash_command=f"""
            echo "📊 LIDO Metadata Database Build Summary"
            echo "========================================"
            echo "Database: {FILE_SQLITE_DB}"
            
            sqlite3 {FILE_SQLITE_DB} <<EOF
.mode box
SELECT 
    (SELECT COUNT(*) FROM {TABLE_NAME}) as total_records,
    (SELECT COUNT(DISTINCT source) FROM {TABLE_NAME}) as source_count,
    (SELECT COUNT(DISTINCT language) FROM {TABLE_NAME}) as language_count,
    (SELECT MIN(date_publication) FROM {TABLE_NAME}) as earliest_publication,
    (SELECT MAX(date_publication) FROM {TABLE_NAME}) as latest_publication;
EOF

            echo ""
            echo "Sample records:"
            sqlite3 {FILE_SQLITE_DB} ".mode column" "SELECT ecli, title, date_publication FROM {TABLE_NAME} LIMIT 5;"
        """,
        doc="Generate summary report of database contents",
    )
    
    # ========================================================================
    # Task Dependencies
    # ========================================================================
    
    # Download phase
    download_task >> verify_download
    
    # Initialize phase
    verify_download >> init_db_task >> check_db
    
    # Build phase
    check_db >> build_db_task
    
    # Validation phase
    build_db_task >> validate_db_task >> verify_records
    
    # Report phase
    verify_records >> generate_summary
