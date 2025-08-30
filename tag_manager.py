# tag_manager.py
import os
import re
import logging
import mutagen
from mutagen.flac import FLAC
from mutagen.aiff import AIFF
from mutagen.id3 import TXXX

def update_filename_with_tags(filename, tags, tag_config=None):
    """
    Updates a filename with the given tags, removing any existing tags of the same type.
    
    Args:
        filename (str): The original filename (without path)
        tags (dict): Dictionary of tags to apply (e.g., {'energy': '7', 'mood': 'dark'})
        tag_config (dict): Configuration for tags including prefixes (e.g., {'energy': {'prefix': 'E'}})
        
    Returns:
        str: Updated filename with tags
    """
    base_name, ext = os.path.splitext(filename)
    tag_config = tag_config or {}
    
    # Remove any existing tags by finding patterns like --TAGVALUE or -PREFIXVALUE
    for tag_name in tags.keys():
        # Get the prefix from config or use first letter of tag name as default
        prefix = (tag_config.get(tag_name, {}).get('prefix', '') or tag_name[0]).upper()
        # Remove both old format (--T) and new format (-PREFIX)
        patterns = [
            r'\s+-{}\w+'.format(re.escape(prefix)),  # New format with prefix (-PREFIXvalue)
            r'\s+--{}\w+'.format(re.escape(tag_name[0].upper()))  # Old format (--Tvalue)
        ]
        for pattern in patterns:
            base_name = re.sub(pattern, '', base_name, flags=re.IGNORECASE)
    
    # Add new tags with configured prefixes
    suffix = ""
    for field, value in sorted(tags.items()):
        if value:
            # Get prefix from config or use first letter of field name
            prefix = (tag_config.get(field, {}).get('prefix', '') or field[0]).upper()
            if prefix:
                suffix += f" -{prefix}{value}"
    
    return f"{base_name}{suffix}{ext}"

def apply_tags_to_group(file_group, tags):
    """
    Applies custom tags to a group of files (e.g., .flac and .aiff).
    Renames the files and writes custom metadata.
    """
    if not file_group:
        return

    # Since all files in the group should have the same base name, we can use the first one.
    first_file_path = file_group[0]
    directory = os.path.dirname(first_file_path)
    original_basename = os.path.basename(os.path.splitext(first_file_path)[0])

    # Clean the base name from any existing tags before adding new ones
    # This assumes that the original basename in the group does not have tags applied.
    # A more robust implementation would strip known tags from the original_basename.

    new_basename_with_tags = update_filename_with_tags(original_basename, tags)

    if not any(tags.values()):
        logging.warning("No valid tag values provided to apply.")
        return

    for old_path in file_group:
        try:
            ext = os.path.splitext(old_path)[1]
            new_path = os.path.join(directory, new_basename_with_tags + ext)

            # 1. Write metadata
            audio = mutagen.File(old_path, easy=True)
            if audio is None:
                raise TypeError("Could not load file with mutagen.")

            for tag_name, tag_value in tags.items():
                if tag_value:
                    # For FLAC, AIFF, MP3 using easy=True (Vorbis Comments or ID3)
                    audio[tag_name.upper()] = str(tag_value)

            audio.save()
            logging.info("Saved metadata to '%s'", os.path.basename(old_path))

            # 2. Rename the file
            if old_path != new_path:
                os.rename(old_path, new_path)
                logging.info("Renamed '%s' to '%s'", os.path.basename(old_path), os.path.basename(new_path))

        except Exception as e:
            logging.error("Failed to process file '%s': %s", os.path.basename(old_path), e)