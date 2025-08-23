# file_converter.py

import os
import subprocess
import logging
from concurrent.futures import ThreadPoolExecutor

def _convert_flac_to_wav(flac_file):
    """Converts a single .flac file to .wav if it doesn't already exist."""
    wav_file = os.path.splitext(flac_file)[0] + '.wav'
    if os.path.exists(wav_file):
        logging.info("WAV file already exists for '%s'.", os.path.basename(flac_file))
        return

    try:
        logging.info("Converting '%s' to WAV...", os.path.basename(flac_file))
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", flac_file, wav_file],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            logging.info("Successfully converted '%s'.", os.path.basename(flac_file))
        else:
            logging.error("Error converting '%s': %s", os.path.basename(flac_file), result.stderr)
    except Exception as e:
        logging.error("Exception during conversion of '%s': %s", os.path.basename(flac_file), e)

def convert_all_flac(base_dir):
    """Finds all .flac files and converts them to .wav using a thread pool."""
    flac_files = [
        os.path.join(root, file)
        for root, _, files in os.walk(base_dir)
        for file in files if file.endswith(".flac")
    ]
    
    if not flac_files:
        logging.info("No FLAC files found to convert.")
        return

    logging.info("Found %d FLAC files to process.", len(flac_files))
    max_workers = os.cpu_count() or 4
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        executor.map(_convert_flac_to_wav, flac_files)
    logging.info("FLAC to WAV conversion process finished.")