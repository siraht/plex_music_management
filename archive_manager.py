# archive_manager.py
import logging
from config import BASE_DOWNLOAD_DIR
import os

ARCHIVE_FILE = os.path.join(BASE_DOWNLOAD_DIR, ".download_archive.txt")

def load_download_archive():
    """Loads all downloaded track ratingKeys into a set for fast lookups."""
    if not os.path.exists(ARCHIVE_FILE):
        return set()
    try:
        with open(ARCHIVE_FILE, 'r') as f:
            return {line.strip() for line in f if line.strip()}
    except IOError as e:
        logging.error("Could not read archive file: %s", e)
        return set()

def add_track_to_archive(track):
    """Appends a track's ratingKey to the archive file."""
    try:
        with open(ARCHIVE_FILE, 'a') as f:
            f.write(f"{track.ratingKey}\n")
        logging.info("Added track '%s' (key: %s) to download archive.", track.title, track.ratingKey)
    except IOError as e:
        logging.error("Could not write to archive file: %s", e)