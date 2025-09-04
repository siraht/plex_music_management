#!/usr/bin/env python3
"""Check and display current configuration for direct file copying."""

import config

print("\n=== Direct File Copy Configuration ===\n")
print(f"Direct copy enabled: {config.USE_DIRECT_FILE_COPY}")
print(f"\nPath mappings:")
for docker_path, fs_path in config.PLEX_PATH_MAPPINGS.items():
    print(f"  {docker_path} -> {fs_path}")

print("\nYou can disable direct copy by setting USE_DIRECT_FILE_COPY = False in config.py")
print("This will make the script always use Plex download (with potential metadata loss)")
