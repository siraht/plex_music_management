import os
import re
import hashlib
from pathlib import Path
from collections import defaultdict
from fuzzywuzzy import fuzz, process
from enhanced_tag_reader import EnhancedTagReader
import logging

logger = logging.getLogger(__name__)

class AdvancedDuplicateDetector:
    def __init__(self, cache_manager, thresholds=None):
        self.cache_manager = cache_manager
        self.tag_reader = EnhancedTagReader()
        self.thresholds = thresholds or {
            'title': 85,
            'artist': 80,
            'album': 80,
            'filename': 75,
            'overall': 78
        }
        self.audio_extensions = {'.mp3', '.flac', '.wav', '.aiff', '.m4a', '.ogg'}
    
    def normalize_string(self, text):
        """Normalize string for comparison"""
        if not text:
            return ""
        # Remove special characters, convert to lowercase, strip whitespace
        normalized = re.sub(r'[^\w\s]', '', str(text).lower().strip())
        # Remove extra whitespace and common words that add noise
        normalized = re.sub(r'\s+', ' ', normalized)
        # Remove common words that might cause false matches
        common_words = ['the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by']
        words = normalized.split()
        words = [w for w in words if w not in common_words]
        return ' '.join(words)
    
    def extract_audio_features(self, file_path, metadata):
        """Extract comparable features from filename and metadata"""
        filename = Path(file_path).stem
        
        # Handle both string and list metadata formats
        def get_first_value(value):
            if isinstance(value, list) and value:
                return str(value[0])
            return str(value) if value else ""
        
        # Extract duration (handle different possible keys)
        duration = 0
        for key in ['duration', 'length', 'time']:
            if key in metadata:
                try:
                    duration = float(metadata[key])
                    break
                except (ValueError, TypeError):
                    continue
        
        return {
            'filename': self.normalize_string(filename),
            'title': self.normalize_string(get_first_value(metadata.get('title', ''))),
            'artist': self.normalize_string(get_first_value(metadata.get('artist', ''))),
            'albumartist': self.normalize_string(get_first_value(metadata.get('albumartist', ''))),
            'album': self.normalize_string(get_first_value(metadata.get('album', ''))),
            'duration': duration,
            'file_size': os.path.getsize(file_path) if os.path.exists(file_path) else 0,
            'bitrate': metadata.get('bitrate', [0])[0] if isinstance(metadata.get('bitrate'), list) else metadata.get('bitrate', 0),
            'track_number': get_first_value(metadata.get('tracknumber', '')),
            'year': get_first_value(metadata.get('date', metadata.get('year', ''))),
            'file_extension': Path(file_path).suffix.lower()
        }
    
    def create_audio_signature(self, features):
        """Create a signature for quick comparison grouping"""
        # Create buckets for initial grouping to optimize comparison
        duration_bucket = int(features['duration'] // 30) * 30 if features['duration'] else 0  # 30-second buckets
        size_bucket = int(features['file_size'] // (1024 * 1024)) if features['file_size'] else 0  # MB buckets
        
        # Create a rough signature for grouping
        signature_parts = [
            features['artist'][:10] if features['artist'] else '',
            features['title'][:10] if features['title'] else '',
            str(duration_bucket),
            str(size_bucket)
        ]
        
        return ''.join(signature_parts).replace(' ', '')
    
    def fuzzy_compare(self, features1, features2):
        """Compare two audio files using advanced fuzzy matching"""
        scores = {}
        
        # Fuzzy string matching with different algorithms
        scores['title_ratio'] = fuzz.ratio(features1['title'], features2['title'])
        scores['title_partial'] = fuzz.partial_ratio(features1['title'], features2['title'])
        scores['title_token_sort'] = fuzz.token_sort_ratio(features1['title'], features2['title'])
        scores['title'] = max(scores['title_ratio'], scores['title_partial'], scores['title_token_sort'])
        
        scores['artist_ratio'] = fuzz.ratio(features1['artist'], features2['artist'])
        scores['artist_partial'] = fuzz.partial_ratio(features1['artist'], features2['artist'])
        scores['artist'] = max(scores['artist_ratio'], scores['artist_partial'])
        
        # Check albumartist if artist doesn't match well
        if features1['albumartist'] and features2['albumartist']:
            albumartist_score = fuzz.ratio(features1['albumartist'], features2['albumartist'])
            scores['artist'] = max(scores['artist'], albumartist_score)
        
        scores['album'] = fuzz.ratio(features1['album'], features2['album'])
        scores['filename'] = fuzz.ratio(features1['filename'], features2['filename'])
        
        # Duration similarity (within 5 seconds tolerance)
        duration_diff = abs(features1['duration'] - features2['duration'])
        if duration_diff <= 3:
            duration_score = 100
        elif duration_diff <= 10:
            duration_score = 90 - (duration_diff - 3) * 5
        else:
            duration_score = max(0, 100 - (duration_diff * 2))
        
        # File size similarity
        if features1['file_size'] > 0 and features2['file_size'] > 0:
            size_diff_percent = abs(features1['file_size'] - features2['file_size']) / max(features1['file_size'], features2['file_size'])
            size_score = max(0, 100 - (size_diff_percent * 100))
        else:
            size_score = 0
        
        # Bitrate similarity
        if features1['bitrate'] > 0 and features2['bitrate'] > 0:
            bitrate_diff_percent = abs(features1['bitrate'] - features2['bitrate']) / max(features1['bitrate'], features2['bitrate'])
            bitrate_score = max(0, 100 - (bitrate_diff_percent * 100))
        else:
            bitrate_score = 50  # Neutral score if bitrate info missing
        
        # Combined score with weights (more emphasis on title and artist)
        overall_score = (
            scores['title'] * 0.35 +
            scores['artist'] * 0.30 +
            scores['album'] * 0.10 +
            scores['filename'] * 0.10 +
            duration_score * 0.10 +
            size_score * 0.03 +
            bitrate_score * 0.02
        )
        
        return {
            'overall': round(overall_score, 2),
            'title': scores['title'],
            'artist': scores['artist'],
            'album': scores['album'],
            'filename': scores['filename'],
            'duration': duration_score,
            'size': size_score,
            'bitrate': bitrate_score,
            'details': {
                'duration_diff': duration_diff,
                'size_diff_mb': abs(features1['file_size'] - features2['file_size']) / (1024 * 1024),
                'bitrate_diff': abs(features1['bitrate'] - features2['bitrate'])
            }
        }
    
    def scan_for_duplicates(self, directory_path, progress_callback=None):
        """Scan directory for potential duplicate audio files"""
        logger.info(f"Starting duplicate scan in: {directory_path}")
        
        audio_files = []
        total_files = 0
        processed_files = 0
        
        # First pass: count total files
        for root, dirs, files in os.walk(directory_path):
            for file in files:
                if Path(file).suffix.lower() in self.audio_extensions:
                    total_files += 1
        
        # Second pass: process files
        for root, dirs, files in os.walk(directory_path):
            for file in files:
                if Path(file).suffix.lower() in self.audio_extensions:
                    file_path = os.path.join(root, file)
                    processed_files += 1
                    
                    if progress_callback:
                        progress_callback(processed_files, total_files, file_path)
                    
                    try:
                        # Try to get from cache first
                        cached_data = self.cache_manager.get_file_data(file_path)
                        if cached_data and 'metadata' in cached_data:
                            metadata = cached_data['metadata']
                        else:
                            metadata = self.tag_reader.read_tags(file_path)
                            if metadata:
                                self.cache_manager.cache_file_data(file_path, {'metadata': metadata})
                        
                        if metadata:
                            audio_files.append((file_path, metadata))
                    except Exception as e:
                        logger.warning(f"Error processing {file_path}: {e}")
                        continue
        
        logger.info(f"Processed {len(audio_files)} audio files for duplicate detection")
        return self.find_duplicates(audio_files)
    
    def find_duplicates(self, audio_files_metadata):
        """Find duplicates using advanced fuzzy matching"""
        logger.info(f"Analyzing {len(audio_files_metadata)} files for duplicates")
        
        duplicates = []
        processed = set()
        
        # Create signature groups for optimization
        signature_groups = defaultdict(list)
        for file_path, metadata in audio_files_metadata:
            features = self.extract_audio_features(file_path, metadata)
            signature = self.create_audio_signature(features)
            signature_groups[signature].append((file_path, features))
        
        logger.info(f"Created {len(signature_groups)} signature groups")
        
        # Compare within signature groups
        for group_files in signature_groups.values():
            if len(group_files) < 2:
                continue
                
            for i, (file1, features1) in enumerate(group_files):
                if file1 in processed:
                    continue
                
                similar_files = [(file1, features1, 100.0)]  # (file, features, similarity_score)
                
                for file2, features2 in group_files[i+1:]:
                    if file2 in processed:
                        continue
                    
                    comparison = self.fuzzy_compare(features1, features2)
                    
                    if comparison['overall'] >= self.thresholds['overall']:
                        similar_files.append((file2, features2, comparison['overall']))
                        processed.add(file2)
                
                if len(similar_files) > 1:
                    # Sort by similarity score (descending)
                    similar_files.sort(key=lambda x: x[2], reverse=True)
                    
                    # Create detailed duplicate group info
                    duplicate_group = {
                        'files': [],
                        'best_match': similar_files[0][0],  # File with highest score (first one)
                        'group_id': hashlib.md5(f"{similar_files[0][0]}{len(similar_files)}".encode()).hexdigest()[:8]
                    }
                    
                    for file_path, features, score in similar_files:
                        file_info = {
                            'path': file_path,
                            'filename': os.path.basename(file_path),
                            'size': features['file_size'],
                            'duration': features['duration'],
                            'bitrate': features['bitrate'],
                            'title': features['title'] if features['title'] else 'Unknown',
                            'artist': features['artist'] if features['artist'] else 'Unknown',
                            'album': features['album'] if features['album'] else 'Unknown',
                            'similarity_score': score,
                            'file_extension': features['file_extension']
                        }
                        duplicate_group['files'].append(file_info)
                    
                    duplicates.append(duplicate_group)
                    processed.add(file1)
        
        logger.info(f"Found {len(duplicates)} duplicate groups")
        return duplicates
    
    def get_duplicate_statistics(self, duplicates):
        """Generate statistics about found duplicates"""
        total_duplicates = len(duplicates)
        total_files = sum(len(group['files']) for group in duplicates)
        potential_savings = 0
        
        for group in duplicates:
            # Calculate potential space savings (keep largest file, remove others)
            files = group['files']
            if len(files) > 1:
                files_sorted = sorted(files, key=lambda x: x['size'], reverse=True)
                potential_savings += sum(f['size'] for f in files_sorted[1:])
        
        return {
            'total_duplicate_groups': total_duplicates,
            'total_duplicate_files': total_files,
            'potential_space_savings_mb': round(potential_savings / (1024 * 1024), 2),
            'average_files_per_group': round(total_files / total_duplicates, 1) if total_duplicates > 0 else 0
        }
