# plex_manager.py

import os
import shutil
import logging
import config
from archive_manager import load_download_archive, add_track_to_archive

def connect_to_plex(url, token):
    """Connect to the Plex server and return the server instance."""
    from plexapi.server import PlexServer
    logging.info("Attempting to connect to Plex server...")
    try:
        plex = PlexServer(url, token)
        logging.info("Successfully connected to Plex server.")
        return plex
    except Exception as e:
        logging.error("Failed to connect to Plex server: %s", e)
        return None

def get_original_file_path(track):
    """Get the original file path from a Plex track object."""
    try:
        if track.media and track.media[0].parts:
            return track.media[0].parts[0].file
    except (AttributeError, IndexError) as e:
        logging.debug("Could not get file path for track '%s': %s", track.title, e)
    return None

def copy_file_with_metadata(src_path, dest_path):
    """
    Copy a file preserving all metadata and timestamps.
    Returns True if successful, False otherwise.
    """
    try:
        # Create destination directory if it doesn't exist
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        
        # Use shutil.copy2 to preserve metadata and timestamps
        shutil.copy2(src_path, dest_path)
        logging.info("Successfully copied file with metadata: %s -> %s", src_path, dest_path)
        return True
    except Exception as e:
        logging.error("Failed to copy file: %s. Error: %s", src_path, e)
        return False

def download_track_with_fallback(track, save_dir, use_direct_copy=True):
    """
    Download a track using direct file copy if possible, falling back to Plex download.
    Returns True if successful, False otherwise.
    """
    track_filename = None
    
    # Try direct file copy first if enabled
    if use_direct_copy and config.USE_DIRECT_FILE_COPY:
        plex_path = get_original_file_path(track)
        if plex_path:
            # Translate the Docker path to filesystem path
            fs_path = config.translate_plex_path(plex_path)
            
            if os.path.exists(fs_path):
                # Generate destination filename
                track_filename = os.path.basename(fs_path)
                dest_path = os.path.join(save_dir, track_filename)
                
                # Check if file already exists
                if os.path.exists(dest_path):
                    logging.info("File already exists, skipping: %s", dest_path)
                    return True
                
                # Try to copy the file
                if copy_file_with_metadata(fs_path, dest_path):
                    logging.info("Direct copy successful for track '%s'", track.title)
                    return True
                else:
                    logging.warning("Direct copy failed for track '%s', will try Plex download", track.title)
            else:
                logging.debug("Original file not found at: %s", fs_path)
    
    # Fallback to Plex download
    try:
        logging.info("Using Plex download for track '%s'...", track.title)
        track.download(savepath=save_dir, keep_original_name=True)
        logging.info("Plex download successful for track '%s'", track.title)
        return True
    except Exception as e:
        logging.error("Failed to download track '%s' via Plex: %s", track.title, e)
        return False

def sync_playlists_to_collections(music_section, plex):
    """Creates collections from playlists starting with 'To Mix - ' if they don't exist.
    
    Args:
        music_section: The Plex music library section.
        plex: The Plex server instance.
    """
    logging.info("Starting sync from playlists to collections.")
    existing_collections = {c.title: c for c in music_section.collections() if c.title.startswith("To Mix - ")}
    playlists = [p for p in plex.playlists() if p.title.startswith("To Mix - ")]

    for playlist in playlists:
        if playlist.title not in existing_collections:
            logging.info("Creating collection '%s' from playlist.", playlist.title)
            try:
                music_section.createCollection(title=playlist.title, items=playlist.items())
                logging.info("Collection '%s' successfully created.", playlist.title)
            except Exception as e:
                logging.error("Error creating collection for playlist '%s': %s", playlist.title, e)
        else:
            logging.info("Collection '%s' already exists.", playlist.title)

def sync_collections_and_playlists(music_section, plex):
    """Ensures tracks are synchronized between corresponding collections and playlists.
    
    Args:
        music_section: The Plex music library section.
        plex: The Plex server instance.
    """
    logging.info("Starting two-way sync between collections and playlists.")
    collections = [c for c in music_section.collections() if c.title.startswith("To Mix - ")]
    # plex parameter is already available
    
    for collection in collections:
        playlist = next((p for p in plex.playlists() if p.title == collection.title), None)
        
        if not playlist:
            collection_items = collection.items()
            if collection_items:
                logging.info("Playlist for '%s' not found, creating it with %d items.", collection.title, len(collection_items))
                try:
                    plex.createPlaylist(collection.title, items=collection_items)
                    logging.info("Playlist '%s' successfully created.", collection.title)
                except Exception as e:
                    logging.error("Error creating playlist for collection '%s': %s", collection.title, e)
            else:
                logging.info("Collection '%s' is empty, skipping playlist creation.", collection.title)
        else:
            collection_tracks = set(collection.items())
            playlist_tracks = set(playlist.items())
            
            tracks_to_add_to_playlist = collection_tracks - playlist_tracks
            tracks_to_add_to_collection = playlist_tracks - collection_tracks
            
            if tracks_to_add_to_playlist:
                logging.info("Adding %d tracks to playlist '%s'.", len(tracks_to_add_to_playlist), playlist.title)
                try:
                    playlist.addItems(list(tracks_to_add_to_playlist))
                    logging.info("Tracks successfully added to playlist '%s'.", playlist.title)
                except Exception as e:
                    logging.error("Error adding tracks to playlist '%s': %s", playlist.title, e)
            
            if tracks_to_add_to_collection:
                logging.info("Adding %d tracks to collection '%s'.", len(tracks_to_add_to_collection), collection.title)
                try:
                    collection.addItems(list(tracks_to_add_to_collection))
                    logging.info("Tracks successfully added to collection '%s'.", collection.title)
                except Exception as e:
                    logging.error("Error adding tracks to collection '%s': %s", collection.title, e)

def download_collection_tracks(music_section, base_dir):
    """Downloads tracks from all 'To Mix - ' collections using an archive to prevent re-downloads."""
    logging.info("Starting track download process for collections.")
    os.makedirs(base_dir, exist_ok=True)
    
    # MODIFICATION: Load the archive of already downloaded tracks
    downloaded_keys = load_download_archive()
    
    collections = [c for c in music_section.collections() if c.title.startswith("To Mix - ")]

    for collection in collections:
        subfolder_name = collection.title[9:].strip().lower().replace(" ", "_")
        collection_dir = os.path.join(base_dir, subfolder_name)
        os.makedirs(collection_dir, exist_ok=True)
        
        logging.info("Checking tracks for collection '%s' in '%s'.", collection.title, collection_dir)
        for track in collection.items():
            try:
                # MODIFICATION: Check against the archive using the track's unique ratingKey
                if str(track.ratingKey) in downloaded_keys:
                    logging.info("Track '%s' (key: %s) is in archive, skipping.", track.title, track.ratingKey)
                    continue
                
                logging.info("Processing track '%s'...", track.title)
                
                # Use the new download function with direct copy support
                if download_track_with_fallback(track, collection_dir):
                    # MODIFICATION: Add the newly downloaded track to the archive
                    add_track_to_archive(track)
                else:
                    logging.error("Failed to download/copy track '%s'", track.title)

            except Exception as e:
                logging.error("Unexpected error processing track '%s': %s", track.title, e)

def process_unsorted_tracks(music_section, plex):
    """Finds tracks in 'To Mix' that aren't in other 'To Mix - ' collections and adds them to 'To Mix - Unsorted'."""
    logging.info("Processing 'To Mix' for unsorted tracks.")
    try:
        all_collections = music_section.collections()
        to_mix_collection = next((c for c in all_collections if c.title == 'To Mix'), None)
        
        if not to_mix_collection:
            logging.info("'To Mix' collection not found. Nothing to process.")
            return
            
        unsorted_collection = next((c for c in all_collections if c.title == 'To Mix - Unsorted'), None)
        if not unsorted_collection:
            unsorted_collection = music_section.createCollection(title="To Mix - Unsorted", smart=False, items=[])
        
        all_to_mix_tracks = set(to_mix_collection.items())
        sorted_tracks = set()

        for collection in all_collections:
            if collection.title.startswith("To Mix - ") and collection.title != "To Mix - Unsorted":
                sorted_tracks.update(collection.items())
        
        unsorted_tracks = all_to_mix_tracks - sorted_tracks
        
        if unsorted_tracks:
            logging.info("Adding %d unsorted tracks to 'To Mix - Unsorted'.", len(unsorted_tracks))
            unsorted_collection.addItems(list(unsorted_tracks))
        else:
            logging.info("No unsorted tracks found.")
    
    except Exception as e:
        logging.error("Error processing unsorted tracks: %s", e)

def download_single_playlist(plex, playlist_name, base_dir):
    """Downloads all tracks from a single playlist."""
    logging.info("Looking for playlist: '%s'", playlist_name)
    
    try:
        # Find the playlist
        playlist = next((p for p in plex.playlists() if p.title == playlist_name), None)
        
        if not playlist:
            logging.error("Playlist '%s' not found.", playlist_name)
            return None
        
        # Create directory for the playlist
        subfolder_name = playlist_name.lower().replace(" ", "_")
        playlist_dir = os.path.join(base_dir, subfolder_name)
        os.makedirs(playlist_dir, exist_ok=True)
        
        logging.info("Found playlist '%s' with %d tracks.", playlist_name, len(playlist.items()))
        
        # Load the archive of already downloaded tracks
        downloaded_keys = load_download_archive()
        
        # Download each track
        for track in playlist.items():
            try:
                # Check against the archive
                if str(track.ratingKey) in downloaded_keys:
                    logging.info("Track '%s' (key: %s) is in archive, skipping.", track.title, track.ratingKey)
                    continue

                logging.info("Processing track '%s'...", track.title)
                
                # Use the new download function with direct copy support
                if download_track_with_fallback(track, playlist_dir):
                    # Add the newly downloaded track to the archive
                    add_track_to_archive(track)
                else:
                    logging.error("Failed to download/copy track '%s'", track.title)

            except Exception as e:
                logging.error("Unexpected error processing track '%s': %s", track.title, e)

        logging.info("Finished downloading tracks for playlist '%s'.", playlist_name)
        return playlist_dir

    except Exception as e:
        logging.critical("An unexpected error occurred during playlist download: %s", e)
        return None
