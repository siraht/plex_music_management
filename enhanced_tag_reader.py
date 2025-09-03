# enhanced_tag_reader.py

import os
import re
import logging
import json
from typing import Dict, List, Optional, Tuple
from mutagen.flac import FLAC
from mutagen.aiff import AIFF
from mutagen.mp3 import MP3
from mutagen.wave import WAVE
import mutagen
import config

class EnhancedTagReader:
    """Enhanced tag reader that can extract tags from both metadata and filenames."""
    
    def __init__(self):
        self.tag_definitions = self._load_tag_definitions()
    
    def _load_tag_definitions(self) -> List[Dict]:
        """Load tag definitions from the tags.json file."""
        try:
            if os.path.exists(config.TAGS_FILE):
                with open(config.TAGS_FILE, 'r') as f:
                    return json.load(f)
            return []
        except Exception as e:
            logging.error(f"Error loading tag definitions: {e}")
            return []
    
    def get_audio_metadata(self, file_path: str) -> Dict[str, str]:
        """Extract basic metadata (artist, album, title) from audio file."""
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
            if hasattr(audio, 'tags') and audio.tags:
                if hasattr(audio, 'get'):  # FLAC
                    tags = {
                        'artist': audio.get('artist', [''])[0] if audio.get('artist') else '',
                        'album': audio.get('album', [''])[0] if audio.get('album') else '',
                        'title': audio.get('title', [''])[0] if audio.get('title') else ''
                    }
                elif hasattr(audio.tags, 'get'):  # ID3 (MP3, AIFF, WAV)
                    tags = {
                        'artist': self._get_id3_text(audio.tags.get('TPE1')),
                        'album': self._get_id3_text(audio.tags.get('TALB')),
                        'title': self._get_id3_text(audio.tags.get('TIT2'))
                    }
                    
            # If title is empty, use filename without extension
            if not tags.get('title'):
                tags['title'] = os.path.splitext(os.path.basename(file_path))[0]
                
            return tags
        except Exception as e:
            logging.warning(f"Error reading metadata from {file_path}: {str(e)}")
            return {'title': os.path.splitext(os.path.basename(file_path))[0]}
    
    def _get_id3_text(self, tag) -> str:
        """Extract text from ID3 tag object."""
        if tag and hasattr(tag, 'text') and tag.text:
            return tag.text[0]
        return ''
    
    def extract_current_tags_from_metadata(self, file_path: str) -> Dict[str, str]:
        """Extract current custom tags from file metadata."""
        current_tags = {}
        
        try:
            audio = mutagen.File(file_path, easy=True)
            if not audio:
                return {}
            
            # Look for custom tag fields in metadata
            for tag_def in self.tag_definitions:
                tag_name = tag_def['name'].lower()
                
                # Try to find the tag in metadata using various possible field names
                possible_fields = [
                    tag_name.upper(),
                    tag_name.lower(),
                    tag_name.capitalize(),
                    tag_def.get('metadata_field', tag_name.upper())
                ]
                
                for field in possible_fields:
                    if field in audio and audio[field]:
                        value = audio[field]
                        if isinstance(value, list) and value:
                            current_tags[tag_name] = str(value[0])
                        else:
                            current_tags[tag_name] = str(value)
                        break
            
            return current_tags
            
        except Exception as e:
            logging.warning(f"Error extracting tags from metadata for {file_path}: {e}")
            return {}
    
    def extract_current_tags_from_filename(self, file_path: str) -> Dict[str, str]:
        """Extract current custom tags from filename."""
        current_tags = {}
        filename = os.path.basename(file_path)
        basename = os.path.splitext(filename)[0]
        
        try:
            # Look for tag patterns in filename
            for tag_def in self.tag_definitions:
                tag_name = tag_def['name'].lower()
                prefix = tag_def.get('prefix', tag_name[0]).upper()
                
                # Create patterns to match tags in filename
                patterns = [
                    rf'-{re.escape(prefix)}([^\\s-]+)',  # New format: -PREFIX{value}
                    rf'--{re.escape(tag_name[0].upper())}([^\\s-]+)'  # Old format: --T{value}
                ]
                
                for pattern in patterns:
                    matches = re.findall(pattern, basename, re.IGNORECASE)
                    if matches:
                        current_tags[tag_name] = matches[0]
                        break
            
            return current_tags
            
        except Exception as e:
            logging.warning(f"Error extracting tags from filename for {file_path}: {e}")
            return {}
    
    def extract_current_tags_from_title_metadata(self, file_path: str) -> Dict[str, str]:
        """Extract current custom tags from title metadata field."""
        current_tags = {}
        
        try:
            audio = mutagen.File(file_path, easy=True)
            if not audio or 'TITLE' not in audio:
                return {}
            
            title = audio['TITLE']
            if isinstance(title, list) and title:
                title = title[0]
            elif not isinstance(title, str):
                return {}
            
            # Look for tag patterns in title
            for tag_def in self.tag_definitions:
                tag_name = tag_def['name'].lower()
                prefix = tag_def.get('prefix', tag_name[0]).upper()
                
                # Create patterns to match tags in title
                patterns = [
                    rf'-{re.escape(prefix)}([^\\s-]+)',  # New format: -PREFIX{value}
                    rf'--{re.escape(tag_name[0].upper())}([^\\s-]+)'  # Old format: --T{value}
                ]
                
                for pattern in patterns:
                    matches = re.findall(pattern, title, re.IGNORECASE)
                    if matches:
                        current_tags[tag_name] = matches[0]
                        break
            
            return current_tags
            
        except Exception as e:
            logging.warning(f"Error extracting tags from title metadata for {file_path}: {e}")
            return {}
    
    def get_comprehensive_file_data(self, file_path: str) -> Dict:
        """Get comprehensive file data including metadata and current tags based on settings."""
        # Get basic metadata
        metadata = self.get_audio_metadata(file_path)
        
        # Get current tag placement setting
        settings = config.load_settings()
        tag_placement = settings.get('tag_placement', 'filename')
        
        # Extract current tags based on settings
        current_tags = {}
        
        if tag_placement == 'filename':
            current_tags = self.extract_current_tags_from_filename(file_path)
        elif tag_placement == 'title':
            current_tags = self.extract_current_tags_from_title_metadata(file_path)
        elif tag_placement == 'both':
            # Try both, filename takes precedence if both exist
            filename_tags = self.extract_current_tags_from_filename(file_path)
            title_tags = self.extract_current_tags_from_title_metadata(file_path)
            metadata_tags = self.extract_current_tags_from_metadata(file_path)
            
            # Merge tags, with filename > title > metadata priority
            current_tags = {**metadata_tags, **title_tags, **filename_tags}
        
        # Also check for custom tag fields in metadata as fallback
        metadata_tags = self.extract_current_tags_from_metadata(file_path)
        for tag_name, value in metadata_tags.items():
            if tag_name not in current_tags and value:
                current_tags[tag_name] = value
        
        return {
            'metadata': metadata,
            'current_tags': current_tags,
            'file_path': file_path,
            'tag_placement': tag_placement
        }
    
    def refresh_tag_definitions(self):
        """Reload tag definitions from the tags.json file."""
        self.tag_definitions = self._load_tag_definitions()
