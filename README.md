# under construction ...

# 1, step big_audio_cutter.py - MP3 Splitting and Organizing Script

This script is designed to split large MP3 files into smaller segments based on a specified maximum duration. It's nessesery becouse the larger files need more vRAM. Additionally, it organizes the processed files by moving the original MP3 files to an archive directory after splitting.

## Features
- Query the duration of an MP3 file using `ffprobe`.
- Split MP3 files into segments using `ffmpeg`.
- Organize files:
  - Store split files in an output directory.
  - Move the original MP3 files to an archive directory.
- Skip processing if a corresponding JSON file exists for an MP3 file.

## Requirements
- Python 3.x
- `ffmpeg` and `ffprobe` installed and available in the system's PATH.
- The `shutil` and `argparse` Python libraries (included in the Python standard library).

## Installation
1. Clone or download the repository containing this script.
2. Ensure `ffmpeg` and `ffprobe` are installed and properly configured on your system.

## Usage
Run the script from the command line:

```bash
python script_name.py <input_dir> <output_dir> <archive_dir> [--max_duration MAX_DURATION]
```

### Parameters
- `input_dir`: Path to the directory containing MP3 files to be processed.
- `output_dir`: Path to the directory where split files will be saved.
- `archive_dir`: Path to the directory where original MP3 files will be moved after processing.
- `--max_duration`: (Optional) Maximum duration of each segment in seconds. Defaults to `10000` seconds.

### Example
To split MP3 files in the `input` directory, save the segments to the `output` directory, and move original files to the `archive` directory with a maximum segment duration of 3600 seconds:

```bash
python script_name.py input output archive --max_duration 3600
```

## Workflow
1. The script scans the `input_dir` for MP3 files.
2. For each MP3 file:
   - If a corresponding JSON file exists, the file is skipped.
   - The script queries the file's duration.
   - If the duration exceeds the specified maximum, the file is split into smaller segments and stored in the `output_dir`.
   - The original file is then moved to the `archive_dir`.
3. Files shorter than or equal to the maximum duration are skipped without further processing.

## Error Handling
- Errors during duration querying or file splitting are logged to the console.
- The script will continue processing remaining files even if an error occurs.

## License
This script is open-source and can be modified or distributed under the terms of your chosen license.

## Contact
For any issues or questions, feel free to reach out to the author of the script.



