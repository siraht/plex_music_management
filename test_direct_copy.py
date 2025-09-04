#!/usr/bin/env python3
"""Test script to verify direct file copying functionality."""

import os
import sys
import logging
import config
import plex_manager
from plexapi.server import PlexServer

# Setup basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def test_path_translation():
    """Test the path translation function."""
    print("\n=== Testing Path Translation ===")
    
    test_paths = [
        "/music/Tagged/Artist/Album/song.flac",
        "/music/file.mp3",
        "/other/path/file.wav"
    ]
    
    for path in test_paths:
        translated = config.translate_plex_path(path)
        print(f"  {path} -> {translated}")
    
    print("\n✓ Path translation test completed")

def test_plex_connection():
    """Test connection to Plex server."""
    print("\n=== Testing Plex Connection ===")
    
    plex = plex_manager.connect_to_plex(config.PLEX_URL, config.PLEX_TOKEN)
    if plex:
        print(f"  ✓ Connected to Plex server: {plex.friendlyName}")
        return plex
    else:
        print("  ✗ Failed to connect to Plex server")
        return None

def test_track_file_access(plex, limit=3):
    """Test accessing original file paths from tracks."""
    print(f"\n=== Testing Track File Access (first {limit} tracks) ===")
    
    try:
        music_section = plex.library.section('Music')
        tracks = list(music_section.searchTracks())[:limit]
        
        if not tracks:
            print("  No tracks found in music library")
            return
        
        for i, track in enumerate(tracks, 1):
            print(f"\n  Track {i}: {track.title} by {track.artist().title}")
            
            # Get original file path
            plex_path = plex_manager.get_original_file_path(track)
            if plex_path:
                print(f"    Plex path: {plex_path}")
                
                # Translate to filesystem path
                fs_path = config.translate_plex_path(plex_path)
                print(f"    FS path:   {fs_path}")
                
                # Check if file exists
                if os.path.exists(fs_path):
                    file_size = os.path.getsize(fs_path) / (1024 * 1024)  # MB
                    print(f"    ✓ File exists ({file_size:.2f} MB)")
                else:
                    print(f"    ✗ File not found at filesystem path")
            else:
                print(f"    ✗ Could not get file path from Plex")
    
    except Exception as e:
        print(f"  Error during track file access test: {e}")

def test_direct_copy_function(plex):
    """Test the direct copy functionality with a single track."""
    print("\n=== Testing Direct Copy Function ===")
    
    try:
        music_section = plex.library.section('Music')
        
        # Find a track to test with
        tracks = list(music_section.searchTracks())[:1]
        if not tracks:
            print("  No tracks available for testing")
            return
        
        track = tracks[0]
        print(f"  Testing with track: {track.title} by {track.artist().title}")
        
        # Create a test directory
        test_dir = "/mnt/user/appdata/plex_music_management/test_copy"
        os.makedirs(test_dir, exist_ok=True)
        
        # Test the download function with direct copy
        print("  Attempting direct copy...")
        success = plex_manager.download_track_with_fallback(track, test_dir, use_direct_copy=True)
        
        if success:
            print("  ✓ Track successfully copied/downloaded")
            
            # Check if file exists in test directory
            files = os.listdir(test_dir)
            if files:
                print(f"  Files in test directory: {files}")
                
                # Clean up test
                for file in files:
                    os.remove(os.path.join(test_dir, file))
            else:
                print("  Warning: No files found in test directory after copy")
        else:
            print("  ✗ Failed to copy/download track")
        
        # Clean up test directory
        os.rmdir(test_dir)
        
    except Exception as e:
        print(f"  Error during direct copy test: {e}")

def main():
    """Run all tests."""
    print("=" * 50)
    print("Direct File Copy Implementation Test")
    print("=" * 50)
    
    # Test path translation
    test_path_translation()
    
    # Test Plex connection
    plex = test_plex_connection()
    if not plex:
        print("\nCannot proceed without Plex connection")
        sys.exit(1)
    
    # Test track file access
    test_track_file_access(plex)
    
    # Test direct copy function
    test_direct_copy_function(plex)
    
    print("\n" + "=" * 50)
    print("Test completed!")
    print("=" * 50)

if __name__ == "__main__":
    main()
