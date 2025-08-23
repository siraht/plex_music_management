# file_converter.py

import os
import subprocess
import logging
from concurrent.futures import ThreadPoolExecutor

# UPDATED FUNCTION
def _convert_flac_to_aiff(flac_file):
    """Converts a single .flac file to .aiff, preserving all metadata."""
    # Change the extension from .wav to .aiff
    aiff_file = os.path.splitext(flac_file)[0] + '.aiff'
    
    if os.path.exists(aiff_file):
        logging.info("AIFF file already exists for '%s'.", os.path.basename(flac_file))
        return

    try:
        logging.info("Converting '%s' to AIFF...", os.path.basename(flac_file))
        # Updated FFmpeg command for AIFF with metadata preservation
        result = subprocess.run(
            [
                "ffmpeg", "-y", "-i", flac_file,
                "-map_metadata", "0",          # Map all metadata streams
                "-write_id3v2", "1",           # Ensure ID3v2 tags are written
                aiff_file
            ],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            logging.info("Successfully converted '%s'.", os.path.basename(flac_file))
        else:
            logging.error("Error converting '%s': %s", os.path.basename(flac_file), result.stderr)
    except Exception as e:
        logging.error("Exception during conversion of '%s': %s", os.path.basename(flac_file), e)

# UPDATED FUNCTION
def convert_all_flac(base_dir):
    """Finds all .flac files and converts them to .aiff using a thread pool."""
    flac_files = [
        os.path.join(root, file)
        for root, _, files in os.walk(base_dir)
        for file in files if file.endswith(".flac")
    ]
    
    if not flac_files:
        logging.info("No FLAC files found to convert.")
        return

    logging.info("Found %d FLAC files to process for AIFF conversion.", len(flac_files))
    max_workers = os.cpu_count() or 4
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Call the new aiff function
        executor.map(_convert_flac_to_aiff, flac_files)
    logging.info("FLAC to AIFF conversion process finished.")