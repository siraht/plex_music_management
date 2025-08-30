# tag_manager.py
import os
import logging
import mutagen
from mutagen.flac import FLAC
from mutagen.aiff import AIFF
from mutagen.id3 import TXXX

def apply_tags_to_group(file_group, tags):
    """
    Applies custom tags to a group of files (e.g., .flac and .aiff).
    Renames the files and writes custom metadata.
    """
    if not file_group:
        return

    base_path = os.path.splitext(file_group[0])[0]
    
    # Construct the new filename suffix from tags
    suffix = ""
    for field, value in tags.items():
        if field.lower() == 'energy':
            suffix += f" --E{value}"
        # Add more custom fields here, e.g., --InsSax
        # elif field.lower() == 'instrument':
        #     suffix += f" --Ins{value}"

    if not suffix:
        logging.warning("No valid tags provided to apply.")
        return

    for old_path in file_group:
        extension = os.path.splitext(old_path)[1]
        new_path = f"{base_path}{suffix}{extension}"

        try:
            # 1. Write metadata
            audio = mutagen.File(old_path)
            if audio is None:
                raise TypeError("Could not load file with mutagen.")
            
            # For FLAC (Vorbis Comments)
            if isinstance(audio, FLAC):
                audio['ENERGY'] = str(tags.get('energy', ''))
            
            # For AIFF/MP3 (ID3 Tags)
            elif isinstance(audio, AIFF):
                # TXXX is a custom text frame: TXXX:description=value
                audio.tags.add(TXXX(encoding=3, desc='Energy', text=str(tags.get('energy', ''))))

            audio.save()
            logging.info("Saved metadata to '%s'", os.path.basename(old_path))

            # 2. Rename the file
            os.rename(old_path, new_path)
            logging.info("Renamed '%s' to '%s'", os.path.basename(old_path), os.path.basename(new_path))

        except Exception as e:
            logging.error("Failed to process file '%s': %s", os.path.basename(old_path), e)