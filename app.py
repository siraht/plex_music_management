# app.py
from flask import Flask, render_template, request, jsonify
from collections import defaultdict
import os
import logging
from mutagen.flac import FLAC
from mutagen.aiff import AIFF
from mutagen.mp3 import MP3
from mutagen.wave import WAVE

import config
from tag_manager import apply_tags_to_group

# Configure Flask
app = Flask(__name__)

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

@app.route('/')
def index():
    """Main page - displays all grouped audio files."""
    grouped_files = scan_files_and_group()
    return render_template('index.html', grouped_files=grouped_files)

@app.route('/api/tag', methods=['POST'])
def tag_file():
    """API endpoint to receive tagging requests from the frontend."""
    data = request.json
    group_key = data.get('group_key')
    energy_level = data.get('energy')

    if not group_key or not energy_level:
        return jsonify({'status': 'error', 'message': 'Missing data'}), 400

    all_files = scan_files_and_group()
    file_group = all_files.get(group_key)
    
    if not file_group:
        return jsonify({'status': 'error', 'message': 'File group not found'}), 404

    # Apply tags to all files in the group
    apply_tags_to_group(file_group['files'], {'energy': energy_level})
    return jsonify({'status': 'success', 'message': f'Tagged {os.path.basename(group_key)}'})

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    app.run(host='0.0.0.0', port=5000, debug=True)