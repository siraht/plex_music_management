# app.py
from flask import Flask, render_template, request, jsonify, make_response
from collections import defaultdict
import os
import logging
from mutagen.flac import FLAC
from mutagen.aiff import AIFF
from mutagen.mp3 import MP3
from mutagen.wave import WAVE
import json
import re
from datetime import datetime

import config
from tag_manager import apply_tags_to_group
from cache_manager import FileCacheManager
from enhanced_tag_reader import EnhancedTagReader
from filename_validator import FilenameValidator
from duplicate_detector import AdvancedDuplicateDetector
import threading
import time

# Helper function to strip existing tags from filename
def strip_existing_tags_from_basename(basename):
    """
    Strip existing tag patterns from basename for consistent grouping.
    """
    import re
    # Remove patterns like --E125, --T7, -E125, etc.
    patterns = [
        r"\s+--[A-Z]\w+",  # Old format (--E125)
        r"\s+-[A-Z]\w+",   # New format (-E125)
        r"\s+--[A-Z][0-9]+", # Specific energy format (--E125)
        r"\s+-[A-Z][0-9]+"   # Specific energy format (-E125)
    ]
    clean_basename = basename
    for pattern in patterns:
        clean_basename = re.sub(pattern, "", clean_basename, flags=re.IGNORECASE)
    return clean_basename.strip()


# Configure Flask
app = Flask(__name__)

# Initialize cache, tag reader, and filename validator
cache_manager = FileCacheManager()
tag_reader = EnhancedTagReader()
filename_validator = FilenameValidator()
# Initialize duplicate detector
duplicate_detector = AdvancedDuplicateDetector(cache_manager)

# Global variables for duplicate scan progress
scan_progress = {"scanning": False, "progress": 0, "total": 0, "current_file": "", "results": None}

# --- Tag Management Functions ---
def load_tags():
    """Loads tags from the JSON file."""
    if not os.path.exists(config.TAGS_FILE):
        return []
    try:
        with open(config.TAGS_FILE, 'r') as f:
            return json.load(f)
    except (IOError, json.JSONDecodeError) as e:
        logging.error(f"Error loading tags file: {e}")
        return []

def save_tags(tags):
    """Saves tags to the JSON file."""
    try:
        with open(config.TAGS_FILE, 'w') as f:
            json.dump(tags, f, indent=4)
        # Refresh tag reader definitions when tags are updated
        tag_reader.refresh_tag_definitions()
    except IOError as e:
        logging.error(f"Error saving tags file: {e}")

# --- Enhanced Metadata and File Scanning with Cache ---
def get_audio_metadata(file_path):
    """Extract metadata from audio file using enhanced tag reader."""
    return tag_reader.get_audio_metadata(file_path)

def scan_files_and_group_with_cache(force_rescan=False):
    """Scans the base directory and groups files by basename, using cache for efficiency."""
    file_groups = {}
    all_audio_files = []
    filename_warnings = []
    
    # First, discover all audio files and check filename lengths
    for root, _, files in os.walk(config.BASE_DOWNLOAD_DIR):
        for file in files:
            if file.lower().endswith(('.flac', '.aiff', '.mp3', '.wav')):
                file_path = os.path.join(root, file)
                all_audio_files.append(file_path)
                
                # Check filename length
                validation = filename_validator.validate_filename_length(file_path)
                if not validation['is_valid']:
                    validation['suggested_name'] = filename_validator.suggest_filename_truncation(file_path)
                    filename_warnings.append(validation)
    
    # Log filename warnings
    if filename_warnings:
        logging.warning(f"Found {len(filename_warnings)} files with filenames over 255 characters:")
        for warning in filename_warnings[:5]:  # Log first 5
            logging.warning(f"  {warning['filename']} ({warning['length']} chars)")
        if len(filename_warnings) > 5:
            logging.warning(f"  ... and {len(filename_warnings) - 5} more files")
    
    # Clean up cache for deleted files
    cache_manager.remove_deleted_files(all_audio_files)
    
    # Process files using cache
    for file_path in all_audio_files:
        raw_basename = os.path.splitext(os.path.basename(file_path))[0]
        basename = strip_existing_tags_from_basename(raw_basename)
        group_key = os.path.join(os.path.dirname(file_path), basename)
        
        if group_key not in file_groups:
            file_groups[group_key] = {
                'files': [],
                'metadata': {},
                'current_tags': {},
                'filename_warnings': []
            }
        
        file_groups[group_key]['files'].append(file_path)
        
        # Add filename warnings to the group
        file_warning = next((w for w in filename_warnings if w['file_path'] == file_path), None)
        if file_warning:
            file_groups[group_key]['filename_warnings'].append(file_warning)
        
        # Check if we need to scan this file
        needs_scan = force_rescan or cache_manager.is_file_modified(file_path)
        
        if needs_scan:
            # Get comprehensive file data (metadata + current tags)
            file_data = tag_reader.get_comprehensive_file_data(file_path)
            
            # Update cache
            cache_manager.update_file_cache(
                file_path, 
                file_data['metadata'], 
                file_data['current_tags']
            )
            
            # Use fresh data for this group if not already set
            if not file_groups[group_key]['metadata']:
                file_groups[group_key]['metadata'] = file_data['metadata']
                file_groups[group_key]['current_tags'] = file_data['current_tags']
        else:
            # Use cached data
            cache_entry = cache_manager.get_file_cache_entry(file_path)
            if cache_entry and not file_groups[group_key]['metadata']:
                file_groups[group_key]['metadata'] = cache_entry['metadata']
                file_groups[group_key]['current_tags'] = cache_entry['current_tags']
    
    # Sort by key (path)
    return dict(sorted(file_groups.items()))

def create_tree_data(file_groups):
    """Converts the flat file group into a structure for AG Grid with folder information, current tags, and filename warnings."""
    tree_data = []

    base_path_parts = config.BASE_DOWNLOAD_DIR.rstrip(os.sep).split(os.sep)
    base_len = len(base_path_parts)

    for group_key, data in file_groups.items():
        # Create path parts relative to the base download directory
        full_path_parts = group_key.split(os.sep)
        relative_path_parts = full_path_parts[base_len:]
        
        # Create a path for grouping
        path = '/'.join(relative_path_parts[:-1])  # Exclude filename from path
        filename = os.path.splitext(relative_path_parts[-1])[0]

        # Check if any files in this group have filename warnings
        has_filename_warning = bool(data.get('filename_warnings', []))
        max_filename_length = 0
        if data.get('files'):
            max_filename_length = max(len(os.path.basename(f)) for f in data['files'])

        # Create the file entry with current tags and filename validation info
        file_entry = {
            'filepath': path,  # This will be used for grouping
            'filename': filename,
            'artist': data['metadata'].get('artist', ''),
            'album': data['metadata'].get('album', ''),
            'title': data['metadata'].get('title', '') or filename,
            'formats': [os.path.splitext(f)[1][1:].upper() for f in data['files']],
            'group_key': group_key,
            'filename_length': max_filename_length,
            'has_filename_warning': has_filename_warning,
            'filename_warnings': data.get('filename_warnings', [])
        }
        
        # Add current tag values from cache
        current_tags = data.get('current_tags', {})
        for tag_name, tag_value in current_tags.items():
            file_entry[tag_name] = tag_value

        tree_data.append(file_entry)

    return tree_data

# --- API Endpoints ---
@app.route('/')
def index():
    """Main page - renders the container for the grid."""
    return render_template('index.html')

@app.route('/api/files')
def get_files_for_grid():
    """API endpoint to provide file data for the AG Grid."""
    force_rescan = request.args.get('force_rescan', 'false').lower() == 'true'
    grouped_files = scan_files_and_group_with_cache(force_rescan=force_rescan)
    tree_data = create_tree_data(grouped_files)
    return jsonify(tree_data)

@app.route('/api/files/refresh')
def refresh_files():
    """API endpoint to force refresh all files."""
    grouped_files = scan_files_and_group_with_cache(force_rescan=True)
    tree_data = create_tree_data(grouped_files)
    return jsonify(tree_data)

@app.route('/api/files/filename-warnings')
def get_filename_warnings():
    """API endpoint to get files with filename length warnings."""
    grouped_files = scan_files_and_group_with_cache()
    warnings = filename_validator.get_filename_warnings(grouped_files)
    
    # Get summary stats
    stats = filename_validator.get_summary_stats([
        filename_validator.validate_filename_length(f) 
        for group in grouped_files.values() 
        for f in group.get('files', [])
    ])
    
    return jsonify({
        'warnings': warnings,
        'stats': stats
    })

@app.route('/api/tags', methods=['GET'])
def get_tags():
    """API endpoint to get the list of available tags."""
    tags = load_tags()
    return jsonify(tags)

@app.route('/api/tags', methods=['POST'])
def save_all_tags():
    """API endpoint to save all tags, replacing the existing ones."""
    tags_data = request.json
    if not isinstance(tags_data, list):
        return jsonify({'status': 'error', 'message': 'Invalid data format, expected a list of tags'}), 400
    
    save_tags(tags_data)
    return jsonify({'status': 'success', 'message': 'Tags saved successfully.'})

@app.route('/api/settings', methods=['GET'])
def get_settings():
    """API endpoint to get the current settings."""
    settings = config.load_settings()
    return jsonify(settings)

@app.route('/api/settings', methods=['POST'])
def save_app_settings():
    """API endpoint to save application settings."""
    settings_data = request.json
    if not isinstance(settings_data, dict):
        return jsonify({'status': 'error', 'message': 'Invalid data format, expected a settings object'}), 400
    
    try:
        config.save_settings(settings_data)
        return jsonify({'status': 'success', 'message': 'Settings saved successfully.'})
    except Exception as e:
        logging.error(f"Error saving settings: {e}")
        return jsonify({'status': 'error', 'message': f'Failed to save settings: {str(e)}'}), 500

@app.route('/api/tag', methods=['POST'])
def tag_file():
    """API endpoint to receive tagging requests from the frontend."""
    data = request.json
    group_key = data.get('group_key')
    tags_to_apply = data.get('tags')

    if not group_key or not tags_to_apply:
        return jsonify({'status': 'error', 'message': 'Missing group_key or tags'}), 400

    all_files = scan_files_and_group_with_cache()
    file_group = all_files.get(group_key)
    
    if not file_group:
        return jsonify({'status': 'error', 'message': 'File group not found'}), 404

    # Validate filename lengths before applying tags
    tag_definitions = load_tags()
    tag_config = {tag['name'].lower(): {'prefix': tag.get('prefix', tag['name'][0])} for tag in tag_definitions}
    
    filename_validation_errors = []
    for file_path in file_group['files']:
        settings = config.load_settings()
        tag_placement = settings.get('tag_placement', 'filename')
        
        # Only validate filename length if tags will be applied to filename
        if tag_placement in ['filename', 'both']:
            is_valid, message, suggested = filename_validator.validate_tags_for_filename_length(
                file_path, tags_to_apply, tag_config
            )
            
            if not is_valid:
                filename_validation_errors.append({
                    'file': os.path.basename(file_path),
                    'message': message,
                    'suggested': suggested
                })
    
    # If there are filename validation errors, return them
    if filename_validation_errors:
        return jsonify({
            'status': 'error', 
            'message': 'Filename length validation failed',
            'validation_errors': filename_validation_errors
        }), 400

    try:
        # Apply tags to all files in the group and get path mappings
        path_results = apply_tags_to_group(file_group['files'], tags_to_apply)

        # Refresh cache to reflect any renames and updated tags
        # Prefer precise updates using returned mappings
        for item in path_results:
            old_path = item.get('old_path')
            new_path = item.get('new_path') or old_path
            # If renamed, remove old cache entry first
            if new_path != old_path:
                try:
                    cache_manager.remove_file_from_cache(old_path)
                except Exception:
                    pass
            # Update cache with fresh metadata/tags for the new/current path
            try:
                file_data = tag_reader.get_comprehensive_file_data(new_path)
                cache_manager.update_file_cache(
                    new_path,
                    file_data['metadata'],
                    file_data['current_tags']
                )
            except Exception as e:
                logging.warning(f"Cache update failed for {new_path}: {e}")

        # Optionally trigger a rescan of groups so UI immediately reflects changes
        # (kept lightweight since cache is already updated)
        # grouped_files = scan_files_and_group_with_cache(force_rescan=False)

        return jsonify({'status': 'success', 'message': f'Tagged {os.path.basename(group_key)}'})
    except Exception as e:
        logging.error(f"Error applying tags: {e}")
        return jsonify({'status': 'error', 'message': f'Error applying tags: {str(e)}'}), 500

@app.route('/api/validate-filename', methods=['POST'])
def validate_filename():
    """API endpoint to validate proposed filename changes."""
    data = request.json
    file_path = data.get('file_path')
    tags = data.get('tags', {})
    
    if not file_path:
        return jsonify({'status': 'error', 'message': 'Missing file_path'}), 400
    
    # Get tag configuration
    tag_definitions = load_tags()
    tag_config = {tag['name'].lower(): {'prefix': tag.get('prefix', tag['name'][0])} for tag in tag_definitions}
    
    # Validate the proposed filename
    is_valid, message, suggested = filename_validator.validate_tags_for_filename_length(
        file_path, tags, tag_config
    )
    
    return jsonify({
        'is_valid': is_valid,
        'message': message,
        'suggested_filename': suggested,
        'current_length': len(os.path.basename(file_path))
    })

@app.route('/api/cache/clear', methods=['POST'])
def clear_cache():
    """API endpoint to clear the file cache."""
    try:
        cache_manager.clear_cache()
        return jsonify({'status': 'success', 'message': 'Cache cleared successfully'})
    except Exception as e:
        logging.error(f"Error clearing cache: {e}")
        return jsonify({'status': 'error', 'message': f'Error clearing cache: {str(e)}'}), 500

@app.route('/api/cache/stats')
def get_cache_stats():
    """API endpoint to get cache statistics."""
    try:
        cached_files = cache_manager.get_all_cached_files()
        
        # Get filename length statistics
        all_validations = []
        for cache_data in cached_files.values():
            validation = filename_validator.validate_filename_length(cache_data['file_path'])
            all_validations.append(validation)
        
        filename_stats = filename_validator.get_summary_stats(all_validations)
        
        stats = {
            'total_cached_files': len(cached_files),
            'cache_db_path': cache_manager.db_path,
            'last_updated': max([f['last_scanned'] for f in cached_files.values()]) if cached_files else None,
            'filename_stats': filename_stats
        }
        return jsonify(stats)
    except Exception as e:
        logging.error(f"Error getting cache stats: {e}")
        return jsonify({'status': 'error', 'message': f'Error getting cache stats: {str(e)}'}), 500


# ===== DUPLICATE DETECTION ROUTES ===== 

@app.route("/duplicates") 
def duplicates_page(): 
    """Render the duplicates detection page""" 
    return render_template("duplicates.html") 

@app.route("/scan-duplicates", methods=["POST"]) 
def start_duplicate_scan(): 
    """Start scanning for duplicates in a separate thread""" 
    global scan_progress 
    
    if scan_progress["scanning"]: 
        return jsonify({"status": "error", "message": "Scan already in progress"}), 400 
    
    try: 
        data = request.get_json() 
        directory_path = data.get("directory", config.MUSIC_DIRECTORY) 
        
        if not os.path.exists(directory_path): 
            return jsonify({"status": "error", "message": "Directory does not exist"}), 400 
        
        # Reset progress 
        scan_progress = {"scanning": True, "progress": 0, "total": 0, "current_file": "", "results": None} 
        
        # Start scan in background thread 
        scan_thread = threading.Thread(target=perform_duplicate_scan, args=(directory_path,)) 
        scan_thread.daemon = True 
        scan_thread.start() 
        
        return jsonify({"status": "started", "message": "Duplicate scan started"}) 
    except Exception as e: 
        logging.error(f"Error starting duplicate scan: {e}") 
        scan_progress["scanning"] = False 
        return jsonify({"status": "error", "message": str(e)}), 500 

@app.route("/scan-duplicates/progress") 
def get_scan_progress(): 
    """Get current scan progress""" 
    global scan_progress 
    return jsonify(scan_progress) 

@app.route("/scan-duplicates/results") 
def get_scan_results(): 
    """Get scan results""" 
    global scan_progress 
    
    if scan_progress["results"] is None: 
        return jsonify({"status": "no_results", "message": "No scan results available"}) 
    
    try: 
        duplicates = scan_progress["results"] 
        stats = duplicate_detector.get_duplicate_statistics(duplicates) 
        
        return jsonify({ 
            "status": "completed", 
            "duplicates": duplicates, 
            "statistics": stats 
        }) 
    except Exception as e: 
        logging.error(f"Error getting scan results: {e}") 
        return jsonify({"status": "error", "message": str(e)}), 500 

@app.route("/delete-duplicate", methods=["POST"]) 
def delete_duplicate_file(): 
    """Delete a duplicate file""" 
    try: 
        data = request.get_json() 
        file_path = data.get("file_path") 
        
        if not file_path or not os.path.exists(file_path): 
            return jsonify({"status": "error", "message": "File does not exist"}), 400 
        
        # Remove from cache first 
        cache_manager.remove_file_from_cache(file_path) 
        
        # Delete the file 
        os.remove(file_path) 
        
        logging.info(f"Deleted duplicate file: {file_path}") 
        return jsonify({"status": "success", "message": "File deleted successfully"}) 
    except Exception as e: 
        logging.error(f"Error deleting file: {e}") 
        return jsonify({"status": "error", "message": str(e)}), 500 

def perform_duplicate_scan(directory_path): 
    """Perform duplicate scan in background thread""" 
    global scan_progress 
    
    def progress_callback(current, total, current_file): 
        scan_progress["progress"] = current 
        scan_progress["total"] = total 
        scan_progress["current_file"] = os.path.basename(current_file) 
    
    try: 
        duplicates = duplicate_detector.scan_for_duplicates(directory_path, progress_callback) 
        scan_progress["results"] = duplicates 
        scan_progress["scanning"] = False 
        logging.info(f"Duplicate scan completed. Found {len(duplicates)} duplicate groups.") 
    except Exception as e: 
        logging.error(f"Error during duplicate scan: {e}") 
        scan_progress["scanning"] = False 
        scan_progress["results"] = [] 


# Error file management endpoints
@app.route('/api/error-files')
def api_get_error_files():
    """Get all files that had errors during processing"""
    try:
        from enhanced_tag_reader import get_error_files
        error_files = get_error_files()
        
        # Add additional file info
        for error_file in error_files:
            file_path = error_file['file_path']
            error_file['filename'] = os.path.basename(file_path)
            error_file['directory'] = os.path.dirname(file_path)
            error_file['exists'] = os.path.exists(file_path)
            if error_file['exists']:
                try:
                    stat = os.stat(file_path)
                    error_file['file_size'] = stat.st_size
                    error_file['modified_time'] = stat.st_mtime
                except:
                    pass
        
        return jsonify({
            'status': 'success',
            'error_files': error_files,
            'total_count': len(error_files)
        })
    except Exception as e:
        logging.error(f"Error getting error files: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/error-files/download')
def download_error_files_list():
    """Download a text file with list of error files"""
    try:
        from enhanced_tag_reader import get_error_files
        error_files = get_error_files()
        
        # Create text content
        lines = []
        lines.append("# Files with Processing Errors")
        lines.append(f"# Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"# Total files: {len(error_files)}")
        lines.append("")
        
        for error_file in error_files:
            lines.append(f"File: {error_file['file_path']}")
            lines.append(f"Error: {error_file['error_message']}")
            lines.append(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(error_file['timestamp']))}")
            lines.append("")
        
        content = "\n".join(lines)
        
        # Create response with file download
        response = make_response(content)
        response.headers['Content-Type'] = 'text/plain'
        response.headers['Content-Disposition'] = f'attachment; filename=error_files_{int(time.time())}.txt'
        
        return response
    except Exception as e:
        logging.error(f"Error downloading error files list: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/error-files/delete', methods=['POST'])
def delete_error_files():
    """Delete error files from filesystem and database"""
    try:
        data = request.json
        file_paths = data.get('file_paths', [])
        delete_from_filesystem = data.get('delete_from_filesystem', False)
        
        if not file_paths:
            return jsonify({'status': 'error', 'message': 'No file paths provided'}), 400
        
        from enhanced_tag_reader import remove_error_file
        
        results = {
            'deleted_from_db': [],
            'deleted_from_filesystem': [],
            'errors': []
        }
        
        for file_path in file_paths:
            try:
                # Remove from database/cache
                cache_manager.remove_file_from_cache(file_path)
                remove_error_file(file_path)
                results['deleted_from_db'].append(file_path)
                
                # Delete from filesystem if requested
                if delete_from_filesystem and os.path.exists(file_path):
                    os.remove(file_path)
                    results['deleted_from_filesystem'].append(file_path)
                    logging.info(f"Deleted error file from filesystem: {file_path}")
                
            except Exception as e:
                error_msg = f"Error processing {file_path}: {str(e)}"
                results['errors'].append(error_msg)
                logging.error(error_msg)
        
        return jsonify({
            'status': 'success',
            'results': results,
            'message': f"Processed {len(file_paths)} files"
        })
        
    except Exception as e:
        logging.error(f"Error deleting error files: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/error-files/clear', methods=['POST'])
def api_clear_error_files():
    """Clear all error files from tracking"""
    try:
        from enhanced_tag_reader import clear_error_files
        clear_error_files()
        return jsonify({'status': 'success', 'message': 'Error files cleared'})
    except Exception as e:
        logging.error(f"Error clearing error files: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    app.run(host='0.0.0.0', port=5000, debug=True)

