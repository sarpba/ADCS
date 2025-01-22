#!/usr/bin/env python3

import os
import argparse
import multiprocessing
from mutagen import File
import matplotlib.pyplot as plt
from tqdm import tqdm

def get_audio_duration(file_path):
    """
    Returns the duration of the given audio file in seconds using Mutagen.
    """
    audio = File(file_path)
    if audio is not None and audio.info is not None:
        return audio.info.length
    else:
        return None

def get_audio_duration_safe(file_path):
    """
    Safely retrieves the duration of an audio file.
    Returns None if the file is not a valid audio file or an error occurs.
    """
    try:
        return get_audio_duration(file_path)
    except Exception:
        return None

def init(tqdm_lock_):
    """
    Initializer function for the multiprocessing Pool.
    """
    global tqdm_lock
    tqdm_lock = tqdm_lock_

def main():
    parser = argparse.ArgumentParser(
        description="Generate a distribution curve of audio file durations in a directory, using Mutagen, parallel processing, and a progress bar. Excludes files longer than 30 seconds from the distribution curve."
    )
    parser.add_argument(
        "-i", 
        "--input_dir", 
        required=True, 
        help="Directory containing the audio files to process."
    )
    parser.add_argument(
        "-o",
        "--output_file",
        default="distribution.png",
        help="Filename for the output image (default: distribution.png)."
    )
    parser.add_argument(
        "--kde",
        action="store_true",
        help="If set, plot a KDE curve alongside the histogram (requires scipy)."
    )
    parser.add_argument(
        "--max_duration",
        type=float,
        default=30.0,
        help="Maximum duration (in seconds) of audio files to include in the distribution curve (default: 30.0)."
    )

    args = parser.parse_args()
    
    # Collect all supported audio files from the input directory
    file_paths = []
    valid_extensions = ('.mp3', '.flac', '.aac', '.ogg', '.m4a', '.wma', '.alac', '.wav')  # Extend as needed
    for root, dirs, files in os.walk(args.input_dir):
        for f in files:
            if f.lower().endswith(valid_extensions):
                file_paths.append(os.path.join(root, f))

    if not file_paths:
        print("No supported audio files found in the specified directory.")
        return

    # Parallel processing with a progress bar
    durations = []
    num_cpus = multiprocessing.cpu_count()
    
    # Create a multiprocessing Lock for tqdm
    tqdm_lock = multiprocessing.Lock()
    
    with multiprocessing.Pool(processes=num_cpus, initializer=init, initargs=(tqdm_lock,)) as pool:
        # Use imap_unordered with tqdm for the progress bar
        for duration in tqdm(pool.imap_unordered(get_audio_duration_safe, file_paths), total=len(file_paths), desc="Processing"):
            if duration is not None:
                durations.append(duration)

    if not durations:
        print("No readable audio files were found in the specified directory.")
        return

    # Calculate statistics based on all durations
    longest = max(durations)
    shortest = min(durations)
    average = sum(durations) / len(durations)

    # Filter durations to exclude files longer than max_duration
    filtered_durations = [d for d in durations if d <= args.max_duration]
    excluded_count = len(durations) - len(filtered_durations)

    if not filtered_durations:
        print(f"No audio files with duration <= {args.max_duration} seconds found.")
        return

    # Create the distribution plot
    plt.figure(figsize=(10, 6))
    plt.hist(filtered_durations, bins=30, alpha=0.6, color='g', label="Histogram")

    if args.kde:
        from scipy.stats import gaussian_kde
        import numpy as np

        durations_np = np.array(filtered_durations)
        kde = gaussian_kde(durations_np)
        x_min = durations_np.min()
        x_max = durations_np.max()
        x_values = np.linspace(x_min, x_max, 200)
        y_values = kde(x_values)

        # Plot KDE on a secondary y-axis
        plt.twinx()
        plt.plot(x_values, y_values, 'r-', label="KDE Curve")
        plt.ylabel("KDE Value")

    plt.title("Distribution of Audio File Durations (Mutagen & Parallelized)")
    plt.xlabel("Duration (seconds)")
    plt.ylabel("Frequency")
    plt.legend(loc='upper right')

    # Annotate the plot with statistics
    stats_text = (
        f"Longest Duration: {longest:.2f} sec\n"
        f"Shortest Duration: {shortest:.2f} sec\n"
        f"Average Duration: {average:.2f} sec\n"
        f"Excluded > {args.max_duration} sec: {excluded_count} files"
    )
    plt.text(0.95, 0.95, stats_text, transform=plt.gca().transAxes, 
             verticalalignment='top', horizontalalignment='right',
             bbox=dict(boxstyle="round,pad=0.5", facecolor="white", alpha=0.8))

    plt.tight_layout()
    plt.savefig(args.output_file)
    plt.close()
    
    print(f"The distribution curve has been saved to: {args.output_file}")

if __name__ == "__main__":
    main()

