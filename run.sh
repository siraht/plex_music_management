#!/bin/bash

# Navigate to the script's directory
cd /mnt/user/appdata/plex_music_management/

# Install/update Python dependencies
pip install -r requirements.txt

# Run the main Python script
python3 main.py