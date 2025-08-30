# app.py
from flask import Flask, render_template, request, jsonify
from collections import defaultdict
import os
import logging
from mutagen.flac import FLAC
from mutagen.aiff import AIFF
from mutagen.mp3 import MP3
from mutagen.wave import WAVE
import json

import config
from tag_manager import apply_tags_to_group

# Configure Flask
app = Flask(__name__)

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
    except IOError as e:
        logging.error(f"Error saving tags file: {e}")

# --- Metadata and File Scanning ---
def get_audio_metadata(file_path):
    """Extract metadata from audio file."""
    try:
        audio = None
        if file_path.lower().endswith('.flac'):
            audio = FLAC(file_path)
        elif file_path.lower().endswith('.aiff'):
            audio = AIFF(file_path)
        elif file_path.lower().endswith('.mp3'):
            audio = MP3(file_path)
        elif file_path.lower().endswith('.wav'):
            audio = WAVE(file_path)
        
        if not audio:
            return {}
            
        tags = {}
        if hasattr(audio, 'tags'):
            if hasattr(audio, 'get'):  # FLAC
                tags = {
                    'artist': audio.get('artist', [''])[0],
                    'album': audio.get('album', [''])[0],
                    'title': audio.get('title', [''])[0]
                }
            elif hasattr(audio.tags, 'getall'):  # ID3 (MP3, AIFF)
                tags = {
                    'artist': audio.tags.get('TPE1', ['']).text[0] if audio.tags.get('TPE1') else '',
                    'album': audio.tags.get('TALB', ['']).text[0] if audio.tags.get('TALB') else '',
                    'title': audio.tags.get('TIT2', ['']).text[0] if audio.tags.get('TIT2') else ''
                }
                
        # If title is empty, use filename without extension
        if not tags.get('title'):
            tags['title'] = os.path.splitext(os.path.basename(file_path))[0]
            
        return tags
    except Exception as e:
        logging.warning(f"Error reading metadata from {file_path}: {str(e)}")
        return {}

def scan_files_and_group():
    """Scans the base directory and groups files by basename."""
    file_groups = {}
    for root, _, files in os.walk(config.BASE_DOWNLOAD_DIR):
        for file in files:
            if file.lower().endswith(('.flac', '.aiff', '.mp3', '.wav')):
                file_path = os.path.join(root, file)
                basename = os.path.splitext(file)[0]
                group_key = os.path.join(root, basename)
                
                if group_key not in file_groups:
                    file_groups[group_key] = {
                        'files': [],
                        'metadata': {}
                    }
                
                # Add file to group
                file_groups[group_key]['files'].append(file_path)
                
                # Get metadata if not already set for this group
                if not file_groups[group_key]['metadata']:
                    metadata = get_audio_metadata(file_path)
                    if metadata:
                        file_groups[group_key]['metadata'] = metadata
    
    # Sort by key (path)
    return dict(sorted(file_groups.items()))

def create_tree_data(file_groups):
    """Converts the flat file group into a structure for AG Grid with folder information."""
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

        # Add the file entry
        file_entry = {
            'filepath': path,  # This will be used for grouping
            'filename': filename,
            'artist': data['metadata'].get('artist', ''),
            'album': data['metadata'].get('album', ''),
            'title': data['metadata'].get('title', '') or filename,
            'formats': [os.path.splitext(f)[1][1:].upper() for f in data['files']],
            'group_key': group_key
        }
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
    grouped_files = scan_files_and_group()
    tree_data = create_tree_data(grouped_files)
    return jsonify(tree_data)

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

@app.route('/api/tag', methods=['POST'])
def tag_file():
    """API endpoint to receive tagging requests from the frontend."""
    data = request.json
    group_key = data.get('group_key')
    tags_to_apply = data.get('tags')

    if not group_key or not tags_to_apply:
        return jsonify({'status': 'error', 'message': 'Missing group_key or tags'}), 400

    all_files = scan_files_and_group()
    file_group = all_files.get(group_key)
    
    if not file_group:
        return jsonify({'status': 'error', 'message': 'File group not found'}), 404

    # Apply tags to all files in the group
    apply_tags_to_group(file_group['files'], tags_to_apply)
    return jsonify({'status': 'success', 'message': f'Tagged {os.path.basename(group_key)}'})

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    app.run(host='0.0.0.0', port=5000, debug=True)