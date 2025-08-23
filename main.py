# main.py

import argparse
import logging
import config
from logger_config import setup_logging
import plex_manager
import file_converter

def run_full_sync():
    """Runs the original, full synchronization and conversion process."""
    logging.info("========== STARTING FULL SYNC ==========")

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
    plex_manager.sync_playlists_to_collections(music_section, plex)
    plex_manager.sync_collections_and_playlists(music_section, plex)
    plex_manager.process_unsorted_tracks(music_section, plex)
    
    # Filesystem tasks
    plex_manager.download_collection_tracks(music_section, config.BASE_DOWNLOAD_DIR)
    file_converter.convert_all_flac(config.BASE_DOWNLOAD_DIR)

    logging.info("=========== FULL SYNC FINISHED ===========")


def run_single_playlist_download(playlist_name):
    """Runs the download and conversion process for a single playlist."""
    logging.info("========== STARTING SINGLE PLAYLIST DOWNLOAD: %s ==========", playlist_name)
    
    plex = plex_manager.connect_to_plex(config.PLEX_URL, config.PLEX_TOKEN)
    if not plex:
        logging.critical("Could not connect to Plex. Exiting.")
        return

    # Download the tracks
    playlist_path = plex_manager.download_single_playlist(plex, playlist_name, config.BASE_DOWNLOAD_DIR)

    # If download was successful and returned a path, convert the files
    if playlist_path:
        logging.info("Starting conversion for files in '%s'...", playlist_path)
        file_converter.convert_all_flac(playlist_path)
    else:
        logging.error("Skipping conversion because playlist download failed or was empty.")
    
    logging.info("=========== SINGLE PLAYLIST DOWNLOAD FINISHED ===========")


def main():
    """Main entry point for the script."""
    # Set up command-line argument parsing
    parser = argparse.ArgumentParser(description="Plex music utility for syncing, downloading, and converting tracks.")
    parser.add_argument(
        "-p", "--playlist",
        type=str,
        help="Download and convert a single playlist by its exact name. Skips the full sync process."
    )
    args = parser.parse_args()

    # Setup logging
    setup_logging()

    # Decide which function to run based on arguments
    if args.playlist:
        run_single_playlist_download(args.playlist)
    else:
        run_full_sync()


if __name__ == "__main__":
    main()