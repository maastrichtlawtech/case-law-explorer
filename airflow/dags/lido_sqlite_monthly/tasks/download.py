"""
Task to download LIDO export file.

NOTE: This is a separate implementation from lido/dag.py which uses curl.
We use urllib with proper SSL and progress tracking.
Future: Consider creating shared lido/tasks/download_lido_ttl.py
"""

import logging
import os
import ssl
from urllib import request
from pathlib import Path

from lido_sqlite_monthly.config import (
    FILE_LIDO_TTL_GZ,
    URL_LIDO_TTL_GZ,
    DOWNLOAD_CHUNK_SIZE,
    DOWNLOAD_TIMEOUT,
    MIN_FILE_SIZE,
    DIR_DATA_LIDO,
)

logger = logging.getLogger(__name__)


def task_download_lido_ttl() -> str:
    """
    Download LIDO export TTL file from data.overheid.nl.
    
    Features:
    - Downloads to temp file first, then renames
    - Includes progress tracking
    - Validates file size
    - Proper SSL certificate verification
    
    Returns:
        Path to downloaded file
        
    Raises:
        Exception: If download fails or file validation fails
    """
    
    # Ensure directory exists
    DIR_DATA_LIDO.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Starting download from {URL_LIDO_TTL_GZ}")
    
    # Download to temporary file first
    temp_file = Path(str(FILE_LIDO_TTL_GZ) + ".tmp")
    
    try:
        # Set up request with proper headers
        req = request.Request(
            URL_LIDO_TTL_GZ,
            headers={'User-Agent': 'Mozilla/5.0 (case-law-explorer)'}
        )
        
        # Use proper SSL verification (no certificate bypassing)
        context = ssl.create_default_context()
        
        with request.urlopen(req, context=context, timeout=DOWNLOAD_TIMEOUT) as response:
            total_size = int(response.headers.get('Content-Length', 0))
            downloaded = 0
            
            if total_size:
                logger.info(f"Total size: {total_size / (1024**2):.1f} MB")
            
            with open(temp_file, 'wb') as out_file:
                while True:
                    chunk = response.read(DOWNLOAD_CHUNK_SIZE)
                    if not chunk:
                        break
                    
                    downloaded += len(chunk)
                    out_file.write(chunk)
                    
                    # Log progress every 50MB
                    if total_size and downloaded % (DOWNLOAD_CHUNK_SIZE * 10) < DOWNLOAD_CHUNK_SIZE:
                        progress = (downloaded / total_size) * 100
                        logger.info(f"Download progress: {progress:.1f}% ({downloaded / (1024**2):.1f} MB)")
        
        # Validate downloaded file
        if not temp_file.exists():
            raise FileNotFoundError(f"Download resulted in missing file: {temp_file}")
        
        file_size = temp_file.stat().st_size
        logger.info(f"✓ Download complete. File size: {file_size / (1024**2):.1f} MB")
        
        if file_size < MIN_FILE_SIZE:
            raise ValueError(
                f"Downloaded file too small: {file_size} bytes (minimum: {MIN_FILE_SIZE})"
            )
        
        # Atomic move to final location
        # Remove old file if exists
        if FILE_LIDO_TTL_GZ.exists():
            FILE_LIDO_TTL_GZ.unlink()
            logger.debug(f"Removed old file: {FILE_LIDO_TTL_GZ}")
        
        temp_file.rename(FILE_LIDO_TTL_GZ)
        logger.info(f"✓ File moved to: {FILE_LIDO_TTL_GZ}")
        
        return str(FILE_LIDO_TTL_GZ)
        
    except Exception as e:
        logger.error(f"✗ Download failed: {e}")
        
        # Cleanup temp file on error
        if temp_file.exists():
            temp_file.unlink()
            logger.debug(f"Cleaned up temp file: {temp_file}")
        
        raise
