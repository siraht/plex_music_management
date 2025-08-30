# config.py

import os
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

# --- Validate essential variables ---
if not all([PLEX_URL, PLEX_TOKEN, BASE_DOWNLOAD_DIR, LOG_FILE]):
    raise ValueError(
        "One or more required environment variables are not set. "
        "Please copy .env.example to .env and fill it out."
    )