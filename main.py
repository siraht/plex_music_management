# main.py

import logging
import config
from logger_config import setup_logging
import plex_manager
import file_converter

def main():
    """Main function to run the entire workflow."""
    setup_logging()
    logging.info("========== SCRIPT STARTED ==========")

    plex = plex_manager.connect_to_plex(config.PLEX_URL, config.PLEX_TOKEN)
    if not plex:
        logging.critical("Could not connect to Plex. Exiting.")
        return

    try:
        music_section = plex.library.section('Music')
    except Exception as e:
        logging.error("Could not retrieve 'Music' library section: %s", e)
        return
    
    # Plex-related tasks
    plex_manager.sync_playlists_to_collections(music_section)
    plex_manager.sync_collections_and_playlists(music_section)
    plex_manager.process_unsorted_tracks(music_section)
    
    # Filesystem tasks
    plex_manager.download_collection_tracks(music_section, config.BASE_DOWNLOAD_DIR)
    file_converter.convert_all_flac(config.BASE_DOWNLOAD_DIR)

    logging.info("=========== SCRIPT FINISHED ===========")

if __name__ == "__main__":
    main()