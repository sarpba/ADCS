"""
whisx_zero_round.py

This script processes audio files in a given input directory (`-i`), detects their language using WhisperX, 
and moves them to an output directory (`-o`) while preserving their original subdirectory structure. 
Each file is categorized into a folder named after the detected language.

Example usage:
    python whisx_zero_round.py -i /path/to/input -o /path/to/output

Dependencies:
    - Python 3
    - torch
    - whisperx
    - ffmpeg (installed system-wide)

The output structure will be:
    /path/to/output/
       ├── en/
       │    └── podcast/
       │         └── episode1.webm
       ├── hu/
       │    └── audiobook/
       │         └── story.wav
       └── ...

"""

import os
import argparse
import subprocess
import shutil

import torch
import whisperx

def find_audio_files(directory, extensions=None):
    """
    Recursively searches for audio files in the given directory and its subdirectories.
    Returns a list of file paths.
    """
    if extensions is None:
        extensions = {".mp3", ".wav", ".flac", ".m4a", ".opus", ".ogg", ".wma", ".aac", ".webm", ".weba"}
    audio_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if os.path.splitext(file)[1].lower() in extensions:
                audio_files.append(os.path.join(root, file))
    return audio_files

def create_30s_snippet(input_file, output_file):
    """
    Extracts the first 30 seconds of an audio file and saves it as a WAV file.
    If the file is shorter than 30 seconds, the full content is used.

    The snippet is re-encoded to PCM format to ensure compatibility with WhisperX.
    """
    command = [
        "ffmpeg",
        "-y",               # Overwrite if the file exists
        "-i", input_file,
        "-ss", "0",
        "-t", "30",
        "-vn",              # Disable video (if present)
        "-acodec", "pcm_s16le",  # PCM 16-bit format
        "-ar", "16000",     # 16 kHz sample rate
        "-ac", "1",         # Mono channel
        output_file
    ]
    try:
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except Exception as e:
        print(f"Error while creating the snippet: {e}")

def main():
    parser = argparse.ArgumentParser(description="WhisperX-based language detection script that preserves the folder structure.")
    parser.add_argument("-i", "--input", required=True, help="Input directory containing audio files.")
    parser.add_argument("-o", "--output", required=True, help="Output directory where files are organized by detected language.")
    args = parser.parse_args()

    input_dir = args.input
    output_dir = args.output

    if not os.path.isdir(input_dir):
        print(f"Error: The specified input directory does not exist: {input_dir}")
        return

    # Ensure the output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Select GPU if available, otherwise use CPU
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Loading WhisperX model on {device}...")

    try:
        # Change "large-v2" to another model (e.g., "medium", "tiny") if needed
        model = whisperx.load_model("large-v3-turbo", device=device, compute_type="float16" if device == "cuda" else "float32")
        print("Model loaded successfully.")
    except Exception as e:
        print(f"Error while loading the model: {e}")
        return

    # Find all audio files in the input directory
    audio_files = find_audio_files(input_dir)
    if not audio_files:
        print("No audio files found in the specified directory.")
        return

    for idx, audio_file in enumerate(audio_files, start=1):
        print(f"[{idx}/{len(audio_files)}] Processing file: {audio_file}")

        # Create a temporary snippet of the first 30 seconds
        snippet_file = "temp_snippet.wav"
        create_30s_snippet(audio_file, snippet_file)

        # Load the snippet and detect the language
        try:
            snippet_audio = whisperx.load_audio(snippet_file)
            result = model.transcribe(snippet_audio, batch_size=16)
            detected_language = result.get("language", "unknown")
        except Exception as e:
            print(f"Error detecting language: {e}")
            detected_language = "unknown"

        print(f"Detected language: {detected_language}")

        # Get the relative path of the file within the input directory
        rel_path = os.path.relpath(audio_file, start=input_dir)

        # Construct the target path in the output directory
        target_file = os.path.join(output_dir, detected_language, rel_path)

        # Create necessary directories before moving the file
        os.makedirs(os.path.dirname(target_file), exist_ok=True)

        # Move the original file to the new location
        try:
            shutil.move(audio_file, target_file)
        except Exception as e:
            print(f"Error while moving the file: {e}")

        # Delete the temporary snippet
        if os.path.exists(snippet_file):
            os.remove(snippet_file)

    print("Processing completed successfully.")

if __name__ == "__main__":
    main()
