# file_converter.py

import os
import subprocess
import logging
from concurrent.futures import ThreadPoolExecutor

# UPDATED FUNCTION
def _convert_flac_to_mp3(flac_file):
    """Converts a single .flac file to 320kbps MP3, preserving all metadata."""
    # Change the extension to .mp3
    mp3_file = os.path.splitext(flac_file)[0] + '.mp3'
    
    if os.path.exists(mp3_file):
        logging.info("MP3 file already exists for '%s'.", os.path.basename(flac_file))
        return

    try:
        logging.info("Converting '%s' to 320kbps MP3...", os.path.basename(flac_file))
        # FFmpeg command for MP3 conversion with high quality settings
        result = subprocess.run(
            [
                "ffmpeg", "-y", "-i", flac_file,
                "-codec:a", "libmp3lame",  # Use LAME MP3 encoder
                "-b:a", "320k",            # Set bitrate to 320kbps
                "-map_metadata", "0",      # Map all metadata
                "-id3v2_version", "3",     # Use ID3v2.3 tags
                "-write_id3v1", "1",       # Also write ID3v1 tags for compatibility
                mp3_file
            ],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            logging.info("Successfully converted '%s' to MP3.", os.path.basename(flac_file))
        else:
            logging.error("Error converting '%s': %s", os.path.basename(flac_file), result.stderr)
    except Exception as e:
        logging.error("Exception during conversion of '%s': %s", os.path.basename(flac_file), e)

# UPDATED FUNCTION
def convert_all_flac(base_dir):
    """Finds all .flac files and converts them to 320kbps MP3 using a thread pool."""
    flac_files = [
        os.path.join(root, file)
        for root, _, files in os.walk(base_dir)
        for file in files if file.endswith(".flac")
    ]
    
    if not flac_files:
        logging.info("No FLAC files found to convert.")
        return

    logging.info("Found %d FLAC files to process for MP3 conversion.", len(flac_files))
    max_workers = os.cpu_count() or 4
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        executor.map(_convert_flac_to_mp3, flac_files)
    logging.info("FLAC to MP3 conversion process finished.")