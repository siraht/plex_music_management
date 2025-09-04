# cache_manager.py

import sqlite3
import os
import logging
import json
import hashlib
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import config

class FileCacheManager:
    """Manages SQLite cache for file metadata and tags to enable incremental scanning."""
    
    def __init__(self, db_path: str = None, use_content_hash: bool = True):
        if db_path is None:
            db_path = os.path.join(os.path.dirname(__file__), 'file_cache.db')
        self.db_path = db_path
        self.use_content_hash = use_content_hash
        self._init_database()
        self._migrate_database()  # Add migration for existing databases
    
    def _init_database(self):
        """Initialize the SQLite database with required tables."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Create table for file cache with content_hash field
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS file_cache (
                        file_path TEXT PRIMARY KEY,
                        last_modified REAL NOT NULL,
                        file_size INTEGER NOT NULL,
                        last_scanned REAL NOT NULL,
                        metadata_json TEXT,
                        current_tags_json TEXT,
                        checksum TEXT,
                        content_hash TEXT
                    )
                ''')
                
                # Create index for performance
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_last_modified 
                    ON file_cache(last_modified)
                ''')
                
                conn.commit()
                logging.info(f"Database initialized at {self.db_path}")
                
        except sqlite3.Error as e:
            logging.error(f"Error initializing database: {e}")
            raise
    
    def _migrate_database(self):
        """Add content_hash column to existing databases."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Check if content_hash column exists
                cursor.execute("PRAGMA table_info(file_cache)")
                columns = [column[1] for column in cursor.fetchall()]
                
                if 'content_hash' not in columns:
                    logging.info("Migrating database: adding content_hash column...")
                    cursor.execute('ALTER TABLE file_cache ADD COLUMN content_hash TEXT')
                    conn.commit()
                    logging.info("Database migration completed")
                    
        except sqlite3.Error as e:
            logging.warning(f"Migration check/update: {e}")
    
    def _compute_file_hash(self, file_path: str, quick: bool = True) -> str:
        """
        Compute a hash of the file content.
        
        Args:
            file_path: Path to the file
            quick: If True, only hash first and last chunks for speed
        
        Returns:
            Hex string of the hash
        """
        try:
            hasher = hashlib.md5()
            
            with open(file_path, 'rb') as f:
                if quick:
                    # Quick hash: first 64KB + last 64KB + file size
                    chunk_size = 65536  # 64KB
                    
                    # Add file size to hash (helps detect truncation)
                    file_size = os.path.getsize(file_path)
                    hasher.update(str(file_size).encode())
                    
                    # Hash first chunk
                    first_chunk = f.read(chunk_size)
                    if first_chunk:
                        hasher.update(first_chunk)
                    
                    # Hash last chunk if file is large enough
                    if file_size > chunk_size * 2:
                        f.seek(-chunk_size, os.SEEK_END)
                        last_chunk = f.read(chunk_size)
                        if last_chunk:
                            hasher.update(last_chunk)
                else:
                    # Full hash: read entire file
                    while chunk := f.read(8192):
                        hasher.update(chunk)
            
            return hasher.hexdigest()
            
        except Exception as e:
            logging.warning(f"Error computing hash for {file_path}: {e}")
            return ""
    
    def get_file_cache_entry(self, file_path: str) -> Optional[Dict]:
        """Get cached data for a specific file."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute(
                    'SELECT * FROM file_cache WHERE file_path = ?',
                    (file_path,)
                )
                
                row = cursor.fetchone()
                if row:
                    result = dict(row)
                    # Parse JSON fields
                    if result['metadata_json']:
                        result['metadata'] = json.loads(result['metadata_json'])
                    else:
                        result['metadata'] = {}
                    
                    if result['current_tags_json']:
                        result['current_tags'] = json.loads(result['current_tags_json'])
                    else:
                        result['current_tags'] = {}
                    
                    return result
                
                return None
                
        except sqlite3.Error as e:
            logging.error(f"Error getting cache entry for {file_path}: {e}")
            return None
    
    def is_file_modified(self, file_path: str, deep_check: bool = False) -> bool:
        """
        Check if a file has been modified since last scan.
        
        Args:
            file_path: Path to the file to check
            deep_check: If True, always use content hash checking
        
        Returns:
            True if file has been modified, False otherwise
        """
        if not os.path.exists(file_path):
            return True  # File doesn't exist, consider it modified
        
        try:
            stat = os.stat(file_path)
            current_mtime = stat.st_mtime
            current_size = stat.st_size
            
            cache_entry = self.get_file_cache_entry(file_path)
            
            if not cache_entry:
                return True  # File not in cache, needs scanning
            
            # First check: modification time or size changed
            if (cache_entry['last_modified'] != current_mtime or 
                cache_entry['file_size'] != current_size):
                return True
            
            # Second check: content hash (if enabled and available)
            if self.use_content_hash or deep_check:
                cached_hash = cache_entry.get('content_hash')
                if cached_hash:
                    # Compute current hash and compare
                    current_hash = self._compute_file_hash(file_path, quick=True)
                    if current_hash and current_hash != cached_hash:
                        logging.debug(f"Content hash mismatch for {file_path}")
                        return True
                else:
                    # No cached hash, consider file modified to compute one
                    return True
            
            return False
            
        except OSError as e:
            logging.warning(f"Error checking file modification for {file_path}: {e}")
            return True
    
    def update_file_cache(self, file_path: str, metadata: Dict, current_tags: Dict, checksum: str = None):
        """Update cache entry for a file with new metadata and tags."""
        try:
            stat = os.stat(file_path)
            current_time = datetime.now().timestamp()
            
            # Compute content hash if enabled
            content_hash = None
            if self.use_content_hash:
                content_hash = self._compute_file_hash(file_path, quick=True)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT OR REPLACE INTO file_cache 
                    (file_path, last_modified, file_size, last_scanned, metadata_json, 
                     current_tags_json, checksum, content_hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    file_path,
                    stat.st_mtime,
                    stat.st_size,
                    current_time,
                    json.dumps(metadata),
                    json.dumps(current_tags),
                    checksum,
                    content_hash
                ))
                
                conn.commit()
                
        except (sqlite3.Error, OSError) as e:
            logging.error(f"Error updating cache for {file_path}: {e}")
            raise
    
    def force_rehash_all(self):
        """Force recomputation of content hashes for all cached files."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get all file paths
                cursor.execute('SELECT file_path FROM file_cache')
                file_paths = [row[0] for row in cursor.fetchall()]
                
                updated_count = 0
                for file_path in file_paths:
                    if os.path.exists(file_path):
                        content_hash = self._compute_file_hash(file_path, quick=True)
                        if content_hash:
                            cursor.execute(
                                'UPDATE file_cache SET content_hash = ? WHERE file_path = ?',
                                (content_hash, file_path)
                            )
                            updated_count += 1
                
                conn.commit()
                logging.info(f"Updated content hashes for {updated_count} files")
                
        except sqlite3.Error as e:
            logging.error(f"Error updating content hashes: {e}")
    
    def get_files_modified_since(self, timestamp: float) -> List[Dict]:
        """Get all files that were modified after the given timestamp."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute(
                    'SELECT * FROM file_cache WHERE last_modified > ?',
                    (timestamp,)
                )
                
                rows = cursor.fetchall()
                results = []
                
                for row in rows:
                    result = dict(row)
                    if result['metadata_json']:
                        result['metadata'] = json.loads(result['metadata_json'])
                    else:
                        result['metadata'] = {}
                    
                    if result['current_tags_json']:
                        result['current_tags'] = json.loads(result['current_tags_json'])
                    else:
                        result['current_tags'] = {}
                    
                    results.append(result)
                
                return results
                
        except sqlite3.Error as e:
            logging.error(f"Error getting modified files: {e}")
            return []
    
    def remove_deleted_files(self, existing_files: List[str]):
        """Remove cache entries for files that no longer exist."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get all cached file paths
                cursor.execute('SELECT file_path FROM file_cache')
                cached_files = [row[0] for row in cursor.fetchall()]
                
                # Find files to remove
                files_to_remove = [f for f in cached_files if f not in existing_files]
                
                if files_to_remove:
                    placeholders = ','.join(['?'] * len(files_to_remove))
                    cursor.execute(
                        f'DELETE FROM file_cache WHERE file_path IN ({placeholders})',
                        files_to_remove
                    )
                    
                    conn.commit()
                    logging.info(f"Removed {len(files_to_remove)} deleted files from cache")
                
        except sqlite3.Error as e:
            logging.error(f"Error removing deleted files from cache: {e}")
    
    def get_all_cached_files(self) -> Dict[str, Dict]:
        """Get all files from cache as a dictionary keyed by file path."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute('SELECT * FROM file_cache')
                rows = cursor.fetchall()
                
                result = {}
                for row in rows:
                    file_data = dict(row)
                    if file_data['metadata_json']:
                        file_data['metadata'] = json.loads(file_data['metadata_json'])
                    else:
                        file_data['metadata'] = {}
                    
                    if file_data['current_tags_json']:
                        file_data['current_tags'] = json.loads(file_data['current_tags_json'])
                    else:
                        file_data['current_tags'] = {}
                    
                    result[file_data['file_path']] = file_data
                
                return result
                
        except sqlite3.Error as e:
            logging.error(f"Error getting all cached files: {e}")
            return {}
    
    def remove_file_from_cache(self, file_path): 
        """Remove a specific file from the cache.""" 
        try: 
            with sqlite3.connect(self.db_path) as conn: 
                cursor = conn.cursor() 
                cursor.execute("DELETE FROM file_cache WHERE file_path = ?", (file_path,)) 
                conn.commit() 
                logging.info(f"Removed {file_path} from cache") 
                 
        except sqlite3.Error as e: 
            logging.error(f"Error removing file from cache: {e}") 
    

    def clear_cache(self):
        """Clear all cache entries."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM file_cache')
                conn.commit()
                logging.info("Cache cleared successfully")
                
        except sqlite3.Error as e:
            logging.error(f"Error clearing cache: {e}")
            raise
    
    def verify_cache_integrity(self, sample_size: int = 10) -> Dict:
        """
        Verify cache integrity by checking a sample of files.
        
        Args:
            sample_size: Number of files to check (0 = all files)
        
        Returns:
            Dictionary with verification results
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                if sample_size > 0:
                    cursor.execute(
                        'SELECT file_path, content_hash FROM file_cache ORDER BY RANDOM() LIMIT ?',
                        (sample_size,)
                    )
                else:
                    cursor.execute('SELECT file_path, content_hash FROM file_cache')
                
                rows = cursor.fetchall()
                
                results = {
                    'total_checked': len(rows),
                    'hash_mismatches': [],
                    'missing_files': [],
                    'missing_hashes': []
                }
                
                for file_path, cached_hash in rows:
                    if not os.path.exists(file_path):
                        results['missing_files'].append(file_path)
                    elif not cached_hash:
                        results['missing_hashes'].append(file_path)
                    else:
                        current_hash = self._compute_file_hash(file_path, quick=True)
                        if current_hash != cached_hash:
                            results['hash_mismatches'].append(file_path)
                
                return results
                
        except sqlite3.Error as e:
            logging.error(f"Error verifying cache integrity: {e}")
            return {}
