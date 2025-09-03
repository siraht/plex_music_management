# Duplicate Detection Feature

## Overview
The duplicate detection feature uses advanced fuzzy matching to identify potential duplicate audio files in your music library. It combines multiple similarity algorithms to provide accurate results while minimizing false positives.

## Features

### Fuzzy Matching Algorithms
- **String Similarity**: Uses multiple fuzzywuzzy algorithms (ratio, partial_ratio, token_sort_ratio)
- **Metadata Comparison**: Compares title, artist, album, albumartist
- **File Properties**: Considers duration, file size, bitrate, and format
- **Filename Analysis**: Normalized filename comparison

### Weighted Scoring System
- Title: 35% weight (most important)
- Artist: 30% weight 
- Album: 10% weight
- Filename: 10% weight
- Duration: 10% weight
- File Size: 3% weight
- Bitrate: 2% weight

### Smart Grouping
- Pre-groups files by signature for performance optimization
- Uses duration and size buckets to reduce unnecessary comparisons
- Handles different metadata formats (string vs list)

## Web Interface

### Scanning Process
1. Click "Find Duplicates" button in the main header
2. Start scan from the duplicate detection page
3. Real-time progress updates during scan
4. Background processing with threading

### Results Display
- **Statistics Dashboard**: Shows total groups, files, and potential space savings
- **Duplicate Groups**: Files grouped by similarity
- **Best Match Highlighting**: First file in each group is marked as the best match
- **Similarity Scores**: Color-coded similarity percentages
- **File Details**: Size, duration, bitrate, format information

### Actions Available
- **Delete**: Remove duplicate files (with confirmation)
- **Keep**: Mark files to keep (visual feedback)
- **Auto-removal**: Only non-best-match files can be deleted

## Technical Details

### Dependencies
- `fuzzywuzzy>=0.18.0`: Fuzzy string matching
- `python-levenshtein>=0.25.0`: Fast string distance calculations

### API Endpoints
- `POST /scan-duplicates`: Start duplicate scan
- `GET /scan-duplicates/progress`: Get scan progress
- `GET /scan-duplicates/results`: Get scan results
- `POST /delete-duplicate`: Delete a duplicate file
- `GET /duplicates`: Duplicate detection page

### Performance Optimizations
- **Caching**: Leverages existing file metadata cache
- **Threading**: Background scanning doesn't block UI
- **Signature Grouping**: Reduces comparison complexity from O(n²) to O(n×g) where g is average group size
- **Thresholds**: Configurable similarity thresholds to tune sensitivity

### Default Thresholds
- Overall similarity: 78%
- Title similarity: 85%
- Artist similarity: 80%
- Album similarity: 80%
- Filename similarity: 75%

## Usage Tips

### Best Practices
1. Run cache refresh before duplicate detection for best results
2. Review results carefully before deleting files
3. Consider keeping highest bitrate/quality versions
4. Use the "best match" guidance as a starting point

### Fine-tuning
- Adjust thresholds in `duplicate_detector.py` if needed
- Lower thresholds = more matches (potentially more false positives)
- Higher thresholds = fewer matches (potentially missed duplicates)

### Safety Features
- Confirmation dialogs for file deletion
- Best match files cannot be accidentally deleted
- Files removed from cache when deleted
- Detailed logging of all operations

## File Structure
```
duplicate_detector.py       # Main detection logic
templates/duplicates.html   # Web interface
app.py                     # Flask routes (duplicate detection section)
```
