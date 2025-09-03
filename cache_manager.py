# cache_manager.py

import sqlite3
import os
import logging
import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import config

class FileCacheManager:
    """Manages SQLite cache for file metadata and tags to enable incremental scanning."""
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = os.path.join(os.path.dirname(__file__), 'file_cache.db')
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Initialize the SQLite database with required tables."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Create table for file cache
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS file_cache (
                        file_path TEXT PRIMARY KEY,
                        last_modified REAL NOT NULL,
                        file_size INTEGER NOT NULL,
                        last_scanned REAL NOT NULL,
                        metadata_json TEXT,
                        current_tags_json TEXT,
                        checksum TEXT
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
    
    def is_file_modified(self, file_path: str) -> bool:
        """Check if a file has been modified since last scan."""
        if not os.path.exists(file_path):
            return True  # File doesn't exist, consider it modified
        
        try:
            stat = os.stat(file_path)
            current_mtime = stat.st_mtime
            current_size = stat.st_size
            
            cache_entry = self.get_file_cache_entry(file_path)
            
            if not cache_entry:
                return True  # File not in cache, needs scanning
            
            # Check if modification time or size changed
            return (cache_entry['last_modified'] != current_mtime or 
                   cache_entry['file_size'] != current_size)
            
        except OSError as e:
            logging.warning(f"Error checking file modification for {file_path}: {e}")
            return True
    
    def update_file_cache(self, file_path: str, metadata: Dict, current_tags: Dict, checksum: str = None):
        """Update cache entry for a file with new metadata and tags."""
        try:
            stat = os.stat(file_path)
            current_time = datetime.now().timestamp()
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT OR REPLACE INTO file_cache 
                    (file_path, last_modified, file_size, last_scanned, metadata_json, current_tags_json, checksum)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    file_path,
                    stat.st_mtime,
                    stat.st_size,
                    current_time,
                    json.dumps(metadata),
                    json.dumps(current_tags),
                    checksum
                ))
                
                conn.commit()
                
        except (sqlite3.Error, OSError) as e:
            logging.error(f"Error updating cache for {file_path}: {e}")
            raise
    
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
