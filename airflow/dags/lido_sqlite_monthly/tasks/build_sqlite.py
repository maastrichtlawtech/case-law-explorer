"""
Task to build SQLite database from LIDO TTL export using pyoxigraph.

This task:
1. Streams N-Triple data from gzipped TTL file
2. Parses triples using pyoxigraph
3. Maps predicates to database fields
4. Extracts meaningful entities from URIs
5. Inserts records into metadata table with batch commits

Issue resolution:
- Issue 3.1: Uses pyoxigraph instead of shell subprocess (security, performance, testability)
- Issue 3.2: Reuses lido.utils.stream for efficient triple streaming
- Issue 3.3: Uses predicate mapping dictionary for O(1) lookups
"""

import logging
from pathlib import Path
from collections import defaultdict

from lido.utils.stream import stream_triples

from lido_sqlite_monthly.config import (
    FILE_LIDO_TTL_GZ,
    FILE_SQLITE_DB,
    TABLE_NAME,
    BATCH_SIZE,
    LOG_INTERVAL,
    PREDICATE_FIELD_MAP,
    LIDO_CASE_LAW_FILTER,
)
from lido_sqlite_monthly.utils.sqlite import get_conn_metadata

logger = logging.getLogger(__name__)


def extract_ecli_from_subject(subject: str) -> str:
    """
    Extract ECLI from subject URI.
    
    Example: http://linkeddata.overheid.nl/terms/jurisprudentie/id/ECLI:NL:PHR:2024:123
    Returns: ECLI:NL:PHR:2024:123
    
    Args:
        subject: Full subject URI
        
    Returns:
        ECLI identifier or empty string if not found
    """
    if not subject:
        return ""
    
    # ECLI is typically the last component after /id/
    parts = subject.split("/")
    for i, part in enumerate(parts):
        if part == "id" and i + 1 < len(parts):
            return parts[i + 1]
    
    return ""


def extract_bwb_ids(legislations_list) -> str:
    """
    Extract BWB IDs from legislation URIs.
    
    Args:
        legislations_list: List of legislation URIs or single URI string
        
    Returns:
        Newline-delimited string of BWB IDs
    """
    if not legislations_list:
        return ""
    
    items = legislations_list if isinstance(legislations_list, list) else [legislations_list]
    bwb_ids = []
    
    for item in items:
        if not isinstance(item, str):
            continue
        
        item = item.strip()
        
        # Match URNs or LIDO URIs
        if "urn:nld:act:" in item or "bwb" in item.lower():
            bwb_ids.append(item)
    
    return "\n".join(bwb_ids) if bwb_ids else ""


def map_predicate_to_field(predicate_uri: str) -> str:
    """
    Map RDF predicate URI to database field name (Issue 3.3).
    
    Uses O(1) dictionary lookup instead of O(n) string checks.
    
    Args:
        predicate_uri: Full predicate URI
        
    Returns:
        Field name or None if predicate not mapped
    """
    # Direct lookup first
    if predicate_uri in PREDICATE_FIELD_MAP:
        return PREDICATE_FIELD_MAP[predicate_uri]
    
    # Special case: inhoudsindicatie (appears without full wrapping sometimes)
    if "inhoudsindicatie" in predicate_uri.lower():
        return "summary"
    
    return None


def insert_row(conn, row_data: dict) -> bool:
    """
    Insert a single row into the metadata table.
    
    Args:
        conn: Database connection
        row_data: Dictionary with field values
        
    Returns:
        True if insert succeeded, False if skipped (no ECLI)
    """
    if "ecli" not in row_data or not row_data["ecli"]:
        return False
    
    # Prepare field values
    ecli_val = row_data.get("ecli", "")
    
    # Join list-based fields with newlines
    case_number = "\n".join(row_data.get("case_number", [])) \
        if isinstance(row_data.get("case_number"), list) else row_data.get("case_number", "")
    domains = "\n".join(row_data.get("domains", [])) \
        if isinstance(row_data.get("domains"), list) else row_data.get("domains", "")
    legislations_cited = "\n".join(row_data.get("legislations_cited", [])) \
        if isinstance(row_data.get("legislations_cited"), list) else row_data.get("legislations_cited", "")
    references_titles = "\n".join(row_data.get("references_titles", [])) \
        if isinstance(row_data.get("references_titles"), list) else row_data.get("references_titles", "")
    citing = "\n".join(row_data.get("citing", [])) \
        if isinstance(row_data.get("citing"), list) else row_data.get("citing", "")
    predecessor_successor = "\n".join(row_data.get("predecessor_successor_cases", [])) \
        if isinstance(row_data.get("predecessor_successor_cases"), list) else row_data.get("predecessor_successor_cases", "")
    
    # Extract BWB IDs from legislations_cited
    bwb_id_str = extract_bwb_ids(row_data.get("legislations_cited", []))
    
    cursor = conn.cursor()
    
    cursor.execute(f"""
        INSERT OR REPLACE INTO {TABLE_NAME} (
            ecli, date_publication, language, instance, jurisdiction_city, 
            date_decision, case_number, document_type, procedure_type, 
            domains, referenced_legislation_titles, alternative_publications, 
            title, full_text, summary, citing, cited_by, legislations_cited, 
            predecessor_successor_cases, url_publications, info, source,
            spatial, bwb_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        ecli_val,
        row_data.get("date_publication", ""),
        row_data.get("language", "nl"),  # Default language
        row_data.get("instance", ""),
        "",  # jurisdiction_city: not robustly parsable from URI
        row_data.get("date_decision", ""),
        case_number,
        row_data.get("document_type", ""),
        row_data.get("procedure_type", ""),
        domains,
        references_titles,
        row_data.get("alternative_publications", ""),
        row_data.get("title", ""),
        "",  # full_text: not in LIDO metadata
        row_data.get("summary", ""),
        citing,
        row_data.get("cited_by", ""),
        legislations_cited,
        predecessor_successor,
        f"https://uitspraken.rechtspraak.nl/inziendocument?id={ecli_val}",
        row_data.get("info", ""),
        "Rechtspraak",  # source
        row_data.get("spatial", ""),
        bwb_id_str,
    ))
    
    return True


def task_build_sqlite_database() -> int:
    """
    Build SQLite database from LIDO TTL export.
    
    Uses lido.utils.stream.stream_triples() with pyoxigraph for efficient
    gzip streaming and RDF parsing. Replaces shell subprocess with native
    Python processing. (Issue 3.1, 3.2)
    
    Returns:
        Number of records inserted
        
    Raises:
        Exception: If database operations fail
    """
    
    logger.info("=" * 70)
    logger.info("🚀 Starting LIDO metadata database build")
    logger.info(f"   Source: {FILE_LIDO_TTL_GZ}")
    logger.info(f"   Target: {FILE_SQLITE_DB}")
    logger.info("=" * 70)
    
    if not Path(FILE_LIDO_TTL_GZ).exists():
        raise FileNotFoundError(f"TTL file not found: {FILE_LIDO_TTL_GZ}")
    
    try:
        conn = get_conn_metadata(str(FILE_SQLITE_DB))
        
        # Clear existing data
        cursor = conn.cursor()
        cursor.execute(f"DELETE FROM {TABLE_NAME}")
        conn.commit()
        logger.info(f"✓ Cleared existing {TABLE_NAME} table")
        
        # Stream and process triples
        count = 0
        line_count = 0
        
        logger.info("Starting triple stream processing...")
        
        # Stream triples from gzipped TTL file using pyoxigraph (Issue 3.2)
        for subject, properties in stream_triples(str(FILE_LIDO_TTL_GZ), gzip=True):
            line_count += 1
            
            # Log progress
            if line_count % LOG_INTERVAL == 0:
                logger.info(
                    f"[Progress] Processed {line_count} subjects, "
                    f"inserted {count} records"
                )
            
            # Filter to case law only
            if not subject.startswith(LIDO_CASE_LAW_FILTER):
                continue
            
            # Initialize row data for this subject (case)
            row_data = {}
            
            # Extract ECLI from subject URI
            row_data["ecli"] = extract_ecli_from_subject(subject)
            
            # Map properties to field values (Issue 3.3: O(1) predicate lookup)
            for predicate_uri, objects in properties.items():
                field_name = map_predicate_to_field(predicate_uri)
                
                if not field_name:
                    continue  # Skip unmapped predicates
                
                # Handle multi-valued fields
                if field_name in ["case_number", "domains", "legislations_cited", 
                                   "references_titles", "citing", "predecessor_successor_cases"]:
                    row_data[field_name] = objects  # Keep as list
                else:
                    # Single-valued fields: take first value
                    row_data[field_name] = objects[0] if objects else ""
            
            # Insert row
            if insert_row(conn, row_data):
                count += 1
                
                # Batch commits for performance
                if count % BATCH_SIZE == 0:
                    conn.commit()
                    logger.info(
                        f"✓ Committed {count} records "
                        f"(processed {line_count} subjects)"
                    )
        
        # Final commit
        conn.commit()
        
        logger.info("=" * 70)
        logger.info(f"✓ Database build COMPLETE")
        logger.info(f"  Total subjects processed: {line_count}")
        logger.info(f"  Records inserted: {count}")
        logger.info(f"  Database: {FILE_SQLITE_DB}")
        logger.info("=" * 70)
        
        conn.close()
        
        return count
        
    except Exception as e:
        logger.error(f"✗ Database build failed: {e}", exc_info=True)
        raise
