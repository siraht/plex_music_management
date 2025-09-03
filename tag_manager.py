# tag_manager.py
import os
import re
import logging
import mutagen
from mutagen.flac import FLAC
import json
from mutagen.aiff import AIFF
from mutagen.id3 import TXXX
import config

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

def update_title_metadata_with_tags(original_title, tags, tag_config=None):
    """
    Updates a title metadata field with tags, removing any existing tags of the same type.
    
    Args:
        original_title (str): The original title
        tags (dict): Dictionary of tags to apply
        tag_config (dict): Configuration for tags including prefixes
        
    Returns:
        str: Updated title with tags
    """
    tag_config = tag_config or {}
    
    # Remove any existing tags from title
    title = original_title
    for tag_name in tags.keys():
        prefix = (tag_config.get(tag_name, {}).get('prefix', '') or tag_name[0]).upper()
        # Remove both old format (--T) and new format (-PREFIX)
        patterns = [
            r'\s+-{}\w+'.format(re.escape(prefix)),  # New format with prefix (-PREFIXvalue)
            r'\s+--{}\w+'.format(re.escape(tag_name[0].upper()))  # Old format (--Tvalue)
        ]
        for pattern in patterns:
            title = re.sub(pattern, '', title, flags=re.IGNORECASE)
    
    # Add new tags to title
    suffix = ""
    for field, value in sorted(tags.items()):
        if value:
            prefix = (tag_config.get(field, {}).get('prefix', '') or field[0]).upper()
            if prefix:
                suffix += f" -{prefix}{value}"
    
    return f"{title.strip()}{suffix}"

def apply_tags_to_group(file_group, tags):
    """
    Applies custom tags to a group of files in the group (e.g., .flac, .mp3, .wav).

    Returns a list of mappings {"old_path": str, "new_path": str} for each file,
    so callers can update caches after potential renames.

    Behavior:
    - Filename tagging does not depend on metadata being writable.
    - If no files were updated (neither metadata saved nor rename), raises an error
      so the API can surface a failure instead of silently succeeding.
    """
    if not file_group:
        return []

    # Get current settings to determine tag placement
    settings = config.load_settings()
    tag_placement = settings.get('tag_placement', 'filename')

    # Since all files in the group should have the same base name, we can use the first one.
    first_file_path = file_group[0]
    directory = os.path.dirname(first_file_path)

    if not any(tags.values()):
        logging.warning("No valid tag values provided to apply.")
        return

    # Load tag configuration for prefixes
    tag_definitions = []
    try:
        if os.path.exists(config.TAGS_FILE):
            with open(config.TAGS_FILE, 'r') as f:
                tag_definitions = json.load(f)
    except Exception as e:
        logging.error(f"Error loading tag definitions: {e}")

    # Create tag config mapping
    tag_config = {}
    for tag_def in tag_definitions:
        if 'name' in tag_def and 'prefix' in tag_def:
            tag_config[tag_def['name'].lower()] = {'prefix': tag_def['prefix']}

    any_success = False
    results = []

    for old_path in file_group:
        new_path = old_path  # default
        file_success = False

        # 1) If filename tagging is enabled, compute the target filename up-front
        if tag_placement in ['filename', 'both']:
            try:
                current_filename = os.path.basename(old_path)
                new_filename = update_filename_with_tags(current_filename, tags, tag_config)
                new_path = os.path.join(directory, new_filename)
            except Exception as e:
                logging.error("Failed to compute new filename for '%s': %s", os.path.basename(old_path), e)

        # 2) Try metadata tagging (best-effort)
        try:
            audio = mutagen.File(old_path, easy=True)
            if audio is not None:
                # Determine original title safely
                original_title = ""
                if hasattr(audio, 'get'):
                    original_title = audio.get('title', [''])[0]
                elif hasattr(audio, 'tags') and hasattr(audio.tags, 'get'):
                    title_tag = audio.tags.get('TIT2')
                    original_title = title_tag.text[0] if title_tag else ""
                if not original_title:
                    original_title = os.path.splitext(os.path.basename(old_path))[0]

                if tag_placement in ['title', 'both']:
                    updated_title = update_title_metadata_with_tags(original_title, tags, tag_config)
                    try:
                        audio['TITLE'] = updated_title
                    except Exception:
                        # Some containers might not support TITLE this way; ignore
                        pass
                    logging.info("Updated title metadata: '%s' -> '%s'", original_title, updated_title)

                # Also write raw tag values to metadata for reference where possible
                for tag_name, tag_value in tags.items():
                    if tag_value:
                        try:
                            audio[tag_name.upper()] = str(tag_value)
                        except Exception:
                            pass

                try:
                    audio.save()
                    file_success = True
                    logging.info("Saved metadata to '%s'", os.path.basename(old_path))
                except Exception as e:
                    logging.warning("Could not save metadata for '%s': %s", os.path.basename(old_path), e)
        except Exception as e:
            logging.warning("Failed to open file for metadata '%s': %s", os.path.basename(old_path), e)

        # 3) Perform filename rename if enabled, regardless of metadata success
        if tag_placement in ['filename', 'both'] and old_path != new_path:
            try:
                os.rename(old_path, new_path)
                file_success = True
                logging.info("Renamed '%s' to '%s'", os.path.basename(old_path), os.path.basename(new_path))
            except Exception as e:
                logging.error("Failed to rename '%s' -> '%s': %s", os.path.basename(old_path), os.path.basename(new_path), e)

        any_success = any_success or file_success
        results.append({"old_path": old_path, "new_path": new_path})

    if not any_success:
        # Ensure the caller can surface a meaningful error instead of silent success
        raise RuntimeError("Failed to apply tags to all files in group: metadata not writable and filename rename failed")

    return results
