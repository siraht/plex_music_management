# plex_manager.py

import os
import logging
from plexapi.server import PlexServer
from archive_manager import load_download_archive, add_track_to_archive

def connect_to_plex(url, token):
    """Connects to the Plex server and returns the server object."""
    try:
        logging.info("Connecting to Plex server at %s", url)
        plex = PlexServer(url, token)
        logging.info("Successfully connected to Plex server.")
        return plex
    except Exception as e:
        logging.error("Failed to connect to Plex server: %s", e)
        return None

def sync_playlists_to_collections(music_section):
    """Creates collections from playlists starting with 'To Mix - ' if they don't exist.
    
    Args:
        music_section: The Plex music library section
    """
    logging.info("Starting sync from playlists to collections.")
    existing_collections = {c.title: c for c in music_section.collections() if c.title.startswith("To Mix - ")}
    playlists = [p for p in music_section.server.playlists() if p.title.startswith("To Mix - ")]

    for playlist in playlists:
        if playlist.title not in existing_collections:
            logging.info("Creating collection '%s' from playlist.", playlist.title)
            try:
                music_section.createCollection(title=playlist.title, items=playlist.items())
                logging.info("Collection '%s' successfully created.", playlist.title)
            except Exception as e:
                logging.error("Error creating collection for playlist '%s': %s", playlist.title, e)
        else:
            logging.info("Collection for playlist '%s' already exists.", playlist.title)

def sync_collections_and_playlists(music_section):
    """Ensures tracks are synchronized between corresponding collections and playlists.
    
    Args:
        music_section: The Plex music library section
    """
    logging.info("Starting two-way sync between collections and playlists.")
    collections = [c for c in music_section.collections() if c.title.startswith("To Mix - ")]
    plex = music_section.server
    
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
                    logging.error("Failed to create playlist '%s': %s", collection.title, e)
            else:
                logging.info("Collection '%s' is empty, skipping playlist creation for now.", collection.title)
            continue

        collection_tracks = set(collection.items())
        playlist_tracks = set(playlist.items())

        tracks_to_add_to_playlist = list(collection_tracks - playlist_tracks)
        if tracks_to_add_to_playlist:
            playlist.addItems(tracks_to_add_to_playlist)
            logging.info("Added %d tracks to playlist '%s'.", len(tracks_to_add_to_playlist), playlist.title)

        tracks_to_add_to_collection = list(playlist_tracks - collection_tracks)
        if tracks_to_add_to_collection:
            collection.addItems(tracks_to_add_to_collection)
            logging.info("Added %d tracks to collection '%s'.", len(tracks_to_add_to_collection), collection.title)

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
                
                logging.info("Downloading '%s'...", track.title)
                track.download(savepath=collection_dir, keep_original_name=True)
                logging.info("Successfully downloaded '%s'.", track.title)

                # MODIFICATION: Add the newly downloaded track to the archive
                add_track_to_archive(track)

            except Exception as e:
                logging.error("Failed to download track '%s': %s", track.title, e)

def process_unsorted_tracks(music_section):
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

        specific_collections = [c for c in all_collections if c.title.startswith("To Mix - ") and c.title not in ["To Mix", "To Mix - Unsorted"]]
        for coll in specific_collections:
            sorted_tracks.update(coll.items())
            
        unsorted_tracks = list(all_to_mix_tracks - sorted_tracks)
        current_unsorted_tracks = set(unsorted_collection.items())
        new_unsorted_tracks = list(set(unsorted_tracks) - current_unsorted_tracks)
        
        if new_unsorted_tracks:
            logging.info("Found %d new unsorted tracks. Adding to 'To Mix - Unsorted'.", len(new_unsorted_tracks))
            unsorted_collection.addItems(new_unsorted_tracks)
        else:
            logging.info("No new unsorted tracks to add.")
    except Exception as e:
        logging.warning("Could not process unsorted tracks: %s", e)

def download_single_playlist(plex, playlist_name, base_dir):
    """
    Finds a single playlist by name, downloads its tracks to a dedicated folder using an archive,
    and returns the path to that folder.
    """
    logging.info("Attempting to download single playlist: '%s'", playlist_name)
    
    try:
        playlist = next((p for p in plex.playlists() if p.title == playlist_name), None)
        if not playlist:
            logging.error("Playlist '%s' not found on the server.", playlist_name)
            return None

        # MODIFICATION: Load the archive of already downloaded tracks
        downloaded_keys = load_download_archive()

        subfolder_name = playlist_name.strip().lower().replace(" ", "_")
        playlist_dir = os.path.join(base_dir, subfolder_name)
        os.makedirs(playlist_dir, exist_ok=True)
        logging.info("Created download directory: '%s'", playlist_dir)
        
        logging.info("Downloading %d tracks from playlist '%s'...", len(playlist.items()), playlist_name)
        for track in playlist.items():
            try:
                # MODIFICATION: Check against the archive using the track's unique ratingKey
                if str(track.ratingKey) in downloaded_keys:
                    logging.info("Track '%s' (key: %s) is in archive, skipping.", track.title, track.ratingKey)
                    continue

                logging.info("Downloading '%s'...", track.title)
                track.download(savepath=playlist_dir, keep_original_name=True)

                # MODIFICATION: Add the newly downloaded track to the archive
                add_track_to_archive(track)

            except Exception as e:
                logging.error("Failed to download track '%s': %s", track.title, e)

        logging.info("Finished downloading tracks for playlist '%s'.", playlist_name)
        return playlist_dir

    except Exception as e:
        logging.critical("An unexpected error occurred during playlist download: %s", e)
        return None