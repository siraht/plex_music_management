# config.py

import os
import json
import logging
from dotenv import load_dotenv

# Find the .env file in the same directory as the script
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path=dotenv_path)

# --- Load configuration from environment variables ---
PLEX_URL = os.getenv("PLEX_URL")
PLEX_TOKEN = os.getenv("PLEX_TOKEN")
BASE_DOWNLOAD_DIR = os.getenv("BASE_DOWNLOAD_DIR")
LOG_FILE = os.getenv("LOG_FILE_PATH")

# Path to the JSON file for storing tags
TAGS_FILE = os.path.join(os.path.dirname(__file__), 'tags.json')

# Path to the JSON file for storing settings
SETTINGS_FILE = os.path.join(os.path.dirname(__file__), 'settings.json')

# --- Settings Management ---
def load_settings():
    """Loads settings from the JSON file with default fallbacks."""
    default_settings = {
        "tag_placement": "filename",  # Options: "filename", "title", "both"
        "version": "1.0",
        "mcp_servers": {}
    }
    
    if not os.path.exists(SETTINGS_FILE):
        save_settings(default_settings)
        return default_settings
    
    try:
        with open(SETTINGS_FILE, 'r') as f:
            settings = json.load(f)
            # Merge with defaults to ensure all required settings exist
            merged_settings = {**default_settings, **settings}
            return merged_settings
    except (IOError, json.JSONDecodeError) as e:
        logging.error(f"Error loading settings file: {e}")
        return default_settings

def save_settings(settings):
    """Saves settings to the JSON file."""
    try:
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(settings, f, indent=4)
        logging.info("Settings saved successfully")
    except IOError as e:
        logging.error(f"Error saving settings file: {e}")
        raise

def get_tag_placement_setting():
    """Convenience function to get the current tag placement setting."""
    settings = load_settings()
    return settings.get("tag_placement", "filename")

# --- Validate essential variables ---
if not all([PLEX_URL, PLEX_TOKEN, BASE_DOWNLOAD_DIR, LOG_FILE]):
    raise ValueError(
        "One or more required environment variables are not set. "
        "Please copy .env.example to .env and fill it out."
    )

# --- Docker Path Mapping Configuration ---
# Maps Plex Docker paths to actual filesystem paths
# Format: {docker_path: filesystem_path}
PLEX_PATH_MAPPINGS = {
    "/music/": "/mnt/user/music/"
}

# Enable/disable direct file copying (set to False to always use Plex download)
USE_DIRECT_FILE_COPY = True

def translate_plex_path(plex_path):
    """Translates a Plex Docker path to the actual filesystem path."""
    for docker_path, fs_path in PLEX_PATH_MAPPINGS.items():
        if plex_path.startswith(docker_path):
            return plex_path.replace(docker_path, fs_path, 1)
    return plex_path
