# tag_manager.py
import os
import re
import logging
import mutagen
from mutagen.flac import FLAC
from mutagen.aiff import AIFF
from mutagen.id3 import TXXX

def update_filename_with_tags(filename, tags):
    """
    Updates a filename with the given tags, removing any existing tags of the same type.
    
    Args:
        filename (str): The original filename (without path)
        tags (dict): Dictionary of tags to apply (e.g., {'energy': '7'})
        
    Returns:
        str: Updated filename with tags
    """
    # Remove file extension
    base_name, ext = os.path.splitext(filename)
    
    # Remove any existing tags
    for tag_name in tags.keys():
        if tag_name.lower() == 'energy':
            base_name = re.sub(r'\s+--E\d+', '', base_name)
    
    # Add new tags
    suffix = ""
    for field, value in tags.items():
        if field.lower() == 'energy' and value:
            suffix += f" --E{value}"
    
    return f"{base_name}{suffix}{ext}"

def apply_tags_to_group(file_group, tags):
    """
    Applies custom tags to a group of files (e.g., .flac and .aiff).
    Renames the files and writes custom metadata.
    """
    if not file_group:
        return

    base_path = os.path.splitext(file_group[0])[0]
    
    # Get the current filename to check for existing tags
    current_filename = os.path.basename(file_group[0])
    
    # Generate new filename with updated tags
    new_filename = update_filename_with_tags(current_filename, tags)
    new_path = os.path.join(os.path.dirname(file_group[0]), new_filename)
    
    if not any(tags.values()):
        logging.warning("No valid tag values provided to apply.")
        return

    for old_path in file_group:
        try:
            # 1. Write metadata
            audio = mutagen.File(old_path)
            if audio is None:
                raise TypeError("Could not load file with mutagen.")
            
            # For FLAC (Vorbis Comments)
            if isinstance(audio, FLAC):
                if 'energy' in tags and tags['energy']:
                    audio['ENERGY'] = str(tags['energy'])
            
            # For AIFF/MP3 (ID3 Tags)
            elif isinstance(audio, AIFF):
                if 'energy' in tags and tags['energy']:
                    audio.tags.add(TXXX(encoding=3, desc='Energy', text=str(tags['energy'])))

            audio.save()
            logging.info("Saved metadata to '%s'", os.path.basename(old_path))

            # 2. Rename the file
            os.rename(old_path, new_path)
            logging.info("Renamed '%s' to '%s'", os.path.basename(old_path), os.path.basename(new_path))

        except Exception as e:
            logging.error("Failed to process file '%s': %s", os.path.basename(old_path), e)