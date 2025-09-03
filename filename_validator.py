# filename_validator.py

import os
import re
import logging
from typing import Dict, List, Optional, Tuple

class FilenameValidator:
    """Validates and manages filename lengths for CDJ compatibility."""
    
    # CDJ filename limit (255 characters)
    MAX_FILENAME_LENGTH = 255
    
    def __init__(self):
        self.warning_files = []
    
    def validate_filename_length(self, file_path: str) -> Dict[str, any]:
        """
        Validate if a filename is within CDJ limits.
        
        Returns:
            Dict with validation results
        """
        filename = os.path.basename(file_path)
        filename_length = len(filename)
        
        return {
            'file_path': file_path,
            'filename': filename,
            'length': filename_length,
            'is_valid': filename_length <= self.MAX_FILENAME_LENGTH,
            'excess_chars': max(0, filename_length - self.MAX_FILENAME_LENGTH),
            'warning_level': self._get_warning_level(filename_length)
        }
    
    def _get_warning_level(self, length: int) -> str:
        """Get warning level based on filename length."""
        if length <= self.MAX_FILENAME_LENGTH:
            return 'none'
        elif length <= self.MAX_FILENAME_LENGTH + 10:
            return 'warning'
        else:
            return 'critical'
    
    def check_proposed_filename(self, current_path: str, tags: Dict[str, str], tag_config: Dict = None) -> Dict[str, any]:
        """
        Check if applying tags would create a filename that's too long.
        
        Args:
            current_path: Current file path
            tags: Tags to be applied
            tag_config: Tag configuration with prefixes
            
        Returns:
            Dict with validation results for the proposed filename
        """
        from tag_manager import update_filename_with_tags
        
        current_filename = os.path.basename(current_path)
        directory = os.path.dirname(current_path)
        
        # Calculate what the new filename would be
        try:
            new_filename = update_filename_with_tags(current_filename, tags, tag_config)
            new_path = os.path.join(directory, new_filename)
            
            return self.validate_filename_length(new_path)
        except Exception as e:
            logging.error(f"Error calculating proposed filename: {e}")
            return {
                'file_path': current_path,
                'filename': current_filename,
                'length': len(current_filename),
                'is_valid': False,
                'excess_chars': 0,
                'warning_level': 'error',
                'error': str(e)
            }
    
    def suggest_filename_truncation(self, file_path: str, target_length: int = None) -> str:
        """
        Suggest a truncated filename that fits within limits.
        
        Args:
            file_path: Original file path
            target_length: Target length (defaults to MAX_FILENAME_LENGTH)
            
        Returns:
            Suggested truncated filename
        """
        if target_length is None:
            target_length = self.MAX_FILENAME_LENGTH
        
        filename = os.path.basename(file_path)
        name, ext = os.path.splitext(filename)
        
        if len(filename) <= target_length:
            return filename
        
        # Calculate how much we need to truncate
        available_length = target_length - len(ext)
        
        if available_length < 10:  # Ensure minimum reasonable length
            return filename  # Can't truncate meaningfully
        
        # Try to preserve important parts
        # 1. Preserve any existing tags at the end
        tag_pattern = r'(\s+-[A-Z]\w*|\s+--[A-Z]\w*)+'
        tag_match = re.search(tag_pattern + r'$', name)
        
        if tag_match:
            tags_part = tag_match.group(0)
            base_part = name[:tag_match.start()]
            
            # Calculate available space for base name
            available_for_base = available_length - len(tags_part)
            
            if available_for_base > 20:  # Ensure reasonable base name length
                truncated_base = base_part[:available_for_base].rstrip(' -')
                return f"{truncated_base}{tags_part}{ext}"
        
        # If no tags or can't preserve them, just truncate
        truncated_name = name[:available_length].rstrip(' -')
        return f"{truncated_name}{ext}"
    
    def get_filename_warnings(self, file_groups: Dict) -> List[Dict]:
        """
        Get all files with filename length warnings from scanned groups.
        
        Args:
            file_groups: File groups from scanning
            
        Returns:
            List of files with warnings
        """
        warnings = []
        
        for group_key, group_data in file_groups.items():
            for file_path in group_data.get('files', []):
                validation = self.validate_filename_length(file_path)
                
                if not validation['is_valid']:
                    validation['suggested_name'] = self.suggest_filename_truncation(file_path)
                    warnings.append(validation)
        
        return warnings
    
    def validate_tags_for_filename_length(self, file_path: str, tags: Dict[str, str], tag_config: Dict = None) -> Tuple[bool, str, Optional[str]]:
        """
        Validate if applying tags would create a valid filename length.
        
        Returns:
            Tuple of (is_valid, message, suggested_alternative)
        """
        validation = self.check_proposed_filename(file_path, tags, tag_config)
        
        if validation['is_valid']:
            return True, "Filename length OK", None
        
        excess = validation['excess_chars']
        suggested = self.suggest_filename_truncation(file_path, self.MAX_FILENAME_LENGTH - 20)  # Leave room for tags
        
        message = f"Warning: Proposed filename would be {excess} characters too long ({validation['length']} chars)"
        
        return False, message, suggested
    
    def scan_directory_for_long_filenames(self, directory: str) -> Dict[str, List[Dict]]:
        """
        Scan a directory for files with problematic filenames.
        
        Returns:
            Dict with 'warnings' and 'critical' lists
        """
        results = {'warnings': [], 'critical': []}
        
        for root, _, files in os.walk(directory):
            for file in files:
                if file.lower().endswith(('.flac', '.aiff', '.mp3', '.wav')):
                    file_path = os.path.join(root, file)
                    validation = self.validate_filename_length(file_path)
                    
                    if not validation['is_valid']:
                        validation['suggested_name'] = self.suggest_filename_truncation(file_path)
                        
                        if validation['warning_level'] == 'critical':
                            results['critical'].append(validation)
                        else:
                            results['warnings'].append(validation)
        
        return results
    
    def get_summary_stats(self, validations: List[Dict]) -> Dict[str, int]:
        """Get summary statistics for filename validations."""
        stats = {
            'total_files': len(validations),
            'valid_files': sum(1 for v in validations if v['is_valid']),
            'warning_files': sum(1 for v in validations if v['warning_level'] == 'warning'),
            'critical_files': sum(1 for v in validations if v['warning_level'] == 'critical'),
        }
        stats['invalid_files'] = stats['total_files'] - stats['valid_files']
        return stats
