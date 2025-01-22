# under construction ...

# 1, step: "big_audio_cutter.py" - MP3 Splitting and Organizing Script

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

# 2. step: "audio_converter.py" Audio Converter Script

## Overview

This script is a parallel audio converter that processes audio files in a directory and its subdirectories, converting them to specified parameters. It utilizes Python's `pydub` library and supports customization of sampling rate, bit depth, and number of channels.

## Features

- **Parallel Processing**: Uses multiple CPU cores for efficient conversion.
- **Customizable Parameters**: Supports frame rate (sampling rate), bit depth, and channels.
- **Wide Format Support**: Works with various audio formats including MP3, WAV, FLAC, AAC, OGG, and more.
- **Preserves Directory Structure**: Maintains the original folder structure in the output directory.

## Requirements

- Python 3.7+
- `pydub` library
- `tqdm` library for progress visualization
- `argparse` for command-line argument handling

## Installation

1. Install the required Python libraries:

   ```bash
   pip install pydub tqdm
   ```

2. Ensure you have a supported audio backend (e.g., `ffmpeg` or `libav`) installed and accessible in your system's PATH.

## Usage

Run the script from the command line:

```bash
python audio_converter.py --input_dir <input_directory> --output_dir <output_directory> [options]
```

### Command-Line Arguments

| Argument       | Description                             | Default             |
| -------------- | --------------------------------------- | ------------------- |
| `--input_dir`  | Path to the input directory (required)  | None                |
| `--output_dir` | Path to the output directory (required) | None                |
| `--workers`    | Number of parallel processes            | Number of CPU cores |
| `--frame_rate` | Sampling rate in Hz                     | 24000               |
| `--bit_depth`  | Bit depth in bits (8, 16, 24, or 32)    | 16                  |
| `--channels`   | Number of channels (1: mono, 2: stereo) | 1                   |

### Example

Convert all audio files in the `input_music` directory to mono, 16-bit, 24000 Hz files in the `output_music` directory:

```bash
python audio_converter.py --input_dir input_music --output_dir output_music --frame_rate 24000 --bit_depth 16 --channels 1
```

## How It Works

1. **Collecting Files**: The script scans the input directory for supported audio files.
2. **Conversion**: Each file is converted to the specified parameters using the `pydub` library.
3. **Parallel Execution**: Conversion tasks are distributed across multiple processes for faster execution.
4. **Progress Reporting**: The `tqdm` library provides a real-time progress bar.
5. **Output Directory Structure**: The original directory structure is replicated in the output directory.

## Supported Audio Formats

The script supports the following audio formats:

- MP3
- WAV
- FLAC
- OGG
- AAC
- WMA
- M4A
- OPUS
- AIFF
- ALAC

## Error Handling

If a file cannot be processed, the error message will be printed to the console, and the script will continue processing other files. A summary of successful and failed conversions is displayed at the end.

## Notes

- Ensure the output directory has sufficient storage for the converted files.
- The script uses the file's original extension for output, so ensure the input files have proper extensions.

# 3. step: "whisx_first_round.py" Transcription Script with WhisperX and Multi-GPU Support

## Overview
This Python script transcribes audio files from a specified directory and its subdirectories using WhisperX, leveraging multiple GPUs to process files in parallel. It ensures efficient transcription with retry mechanisms and timeout handling.

## Features
- Transcribes audio files in various formats (`.mp3`, `.wav`, `.flac`, `.m4a`, `.opus`).
- Utilizes multiple GPUs to speed up processing.
- Automatically skips files that have already been processed (JSON output exists).
- Handles retries for failed transcriptions, with a configurable maximum retry count.
- Provides detailed processing logs, including start and end times, processing duration, and performance metrics.
- Implements a timeout mechanism to prevent long-running processes.

## Requirements
### Dependencies
- Python 3.7+
- Required Python packages:
  - `argparse`
  - `multiprocessing`
  - `subprocess`
  - `os`
  - `datetime`
  - `time`
- WhisperX must be installed and accessible from the command line.
- `ffmpeg` for audio processing (`ffprobe` is used to determine audio duration).

### System Requirements
- At least one GPU with CUDA support.
- Sufficient storage for the generated transcription JSON files.

## Installation
1. Clone the repository:
   ```bash
   git clone <repository_url>
   cd <repository_directory>
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Ensure `whisperx` and `ffmpeg` are installed and properly configured.

## Usage
### Command Line
Run the script from the command line, specifying the directory containing the audio files:
```bash
python whisx_first_round.py <directory>
```
Replace `<directory>` with the path to the folder containing your audio files.

### Example
```bash
python whisx_first_round.py /path/to/audio/files
```

### Script Behavior
1. The script scans the specified directory and its subdirectories for supported audio files.
2. Files that do not have a corresponding `.json` output file are added to the processing queue.
3. Multiple GPUs are utilized, with each GPU assigned specific tasks.
4. For each audio file:
   - The script attempts transcription using WhisperX.
   - Processing time, audio duration, and performance ratio are logged.
   - If an error occurs, the script retries up to the specified maximum number of retries.
5. Once all tasks are completed, the script exits.

## Configuration
### Timeout and Retry
- Timeout duration: 10 minutes (600 seconds, adjustable via the `TIMEOUT` constant).
- Maximum retries: 3 (configurable via the `MAX_RETRIES` constant).

### GPU Configuration
- By default, the script uses GPU IDs `[0, 1]`. You can modify the `gpu_ids` list in the script to match your system.

## Logging
The script outputs detailed logs to the console, including:
- Start and end times for processing.
- Audio file details (name, duration, processing time).
- Performance ratio (audio duration vs. processing time).
- Error messages and retry attempts.

## Limitations
- Currently supports only the audio formats listed above.
- Assumes that WhisperX and CUDA are correctly configured on the system.

## License
This project is licensed under the MIT License. See the `LICENSE` file for more details.

## Contribution
Feel free to submit issues or pull requests to improve this script. Contributions are welcome!



## License

This script is open-source and available under the MIT License.



