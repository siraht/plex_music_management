#!/usr/bin/env python3
"""Force update metadata for all files in the cache"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cache_manager
import enhanced_tag_reader
from logger_config import setup_logging
import logging

def force_update_all_metadata():
    """Force re-read metadata for all files"""
    
    setup_logging()
    
    print("\n" + "="*70)
    print("FORCING METADATA UPDATE FOR ALL FILES")
    print("="*70)
    
    cache = cache_manager.FileCacheManager()
    reader = enhanced_tag_reader.EnhancedTagReader()
    
    # Get all cached files
    cached_files = cache.get_all_cached_files()
    total = len(cached_files)
    
    print(f"\nFound {total} files in cache to update")
    
    updated = 0
    errors = 0
    
    for i, (file_path, cache_data) in enumerate(cached_files.items(), 1):
        if i % 100 == 0:
            print(f"Progress: {i}/{total} files processed...")
        
        if not os.path.exists(file_path):
            continue
            
        try:
            # Get comprehensive file data (metadata + current tags)
            file_data = reader.get_comprehensive_file_data(file_path)
            
            # Update cache with fresh data
            cache.update_file_cache(
                file_path,
                file_data['metadata'],
                file_data['current_tags']
            )
            updated += 1
            
        except Exception as e:
            logging.error(f"Error updating {file_path}: {e}")
            errors += 1
    
    print(f"\n✅ Update complete!")
    print(f"   Files updated: {updated}")
    print(f"   Errors: {errors}")
    
    # Sample check of what was stored
    print("\n📋 Sample of updated metadata:")
    sample_files = list(cached_files.keys())[:5]
    for file_path in sample_files:
        entry = cache.get_file_cache_entry(file_path)
        if entry:
            print(f"\n  {os.path.basename(file_path)}:")
            print(f"    Artist: {entry['metadata'].get('artist', 'N/A')}")
            print(f"    Album: {entry['metadata'].get('album', 'N/A')}")
            print(f"    Title: {entry['metadata'].get('title', 'N/A')}")

if __name__ == "__main__":
    force_update_all_metadata()
