import os
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from mutagen import File
from mutagen.mp3 import MP3
from mutagen.wave import WAVE
from mutagen.flac import FLAC
from mutagen.aac import AAC
from mutagen.oggvorbis import OggVorbis
from mutagen.mp4 import MP4
from mutagen.oggopus import OggOpus

# Mapping of file extensions to their corresponding mutagen classes
AUDIO_CLASSES = {
    '.mp3': MP3,
    '.wav': WAVE,
    '.flac': FLAC,
    '.aac': AAC,
    '.ogg': OggVorbis,
    '.m4a': MP4,
    '.opus': OggOpus
}

AUDIO_EXTENSIONS = set(AUDIO_CLASSES.keys())

def get_audio_length(file_path):
    try:
        ext = os.path.splitext(file_path)[1].lower()
        audio_class = AUDIO_CLASSES.get(ext)
        if audio_class:
            audio = audio_class(file_path)
            return audio.info.length
        else:
            return 0
    except Exception as e:
        print(f"Failed to process the following file: {file_path} - {e}")
        return 0

def count_total_audio_length(directory, max_workers=8):
    total_length = 0
    long_files_length = 0
    futures = []
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for root, dirs, files in os.walk(directory):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in AUDIO_EXTENSIONS:
                    file_path = os.path.join(root, file)
                    futures.append(executor.submit(get_audio_length, file_path))
        
        for future in as_completed(futures):
            length = future.result()
            total_length += length
            if length > 30:
                long_files_length += length

    return total_length, long_files_length

def format_time(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours} hours, {minutes} minutes and {secs} seconds"

def main():
    parser = argparse.ArgumentParser(description='Calculator for the duration of audio files.')
    parser.add_argument('directory', type=str, help='The target directory in which to search for audio files.')
    parser.add_argument('--workers', type=int, default=8, help='Number of threads to use for parallel processing.')
    args = parser.parse_args()

    target_directory = args.directory
    max_workers = args.workers

    print("Processing started...")
    total_seconds, long_files_seconds = count_total_audio_length(target_directory, max_workers)
    print("Processing completed.\n")

    total_time_formatted = format_time(total_seconds)
    long_files_time_formatted = format_time(long_files_seconds)

    print(f"Total {total_time_formatted} of audio content found in the '{target_directory}' directory.")
    print(f"{long_files_time_formatted} of audio content is in files longer than 30 seconds.")

if __name__ == '__main__':
    main()
