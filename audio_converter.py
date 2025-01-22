import os
from pydub import AudioSegment
import argparse
import concurrent.futures
from tqdm import tqdm
from functools import partial

def convert_audio(file_info, frame_rate, sample_width, channels):
    """
    Converts an audio file to the specified parameters and saves it to the output directory.

    Args:
        file_info (tuple): A tuple containing the input file path and the output file path.
        frame_rate (int): The desired sampling rate (Hz).
        sample_width (int): The desired bit depth (bytes).
        channels (int): The desired number of channels.

    Returns:
        str: The path of the successfully converted file or an error message.
    """
    input_file, output_file = file_info
    try:
        # Load the audio file
        audio = AudioSegment.from_file(input_file)
        
        # Convert to the specified parameters
        audio = audio.set_frame_rate(frame_rate)
        audio = audio.set_sample_width(sample_width)
        audio = audio.set_channels(channels)
        
        # Create the output directory if it doesn't exist
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        # Export the converted audio file
        audio.export(output_file, format=os.path.splitext(output_file)[1][1:])  # Use the original extension
        
        return f"Success: {input_file} -> {output_file}"
    except Exception as e:
        return f"Error: {input_file} -> {e}"

def get_all_audio_files(input_dir, output_dir):
    """
    Collects all audio file paths from the input directory and its subdirectories.

    Args:
        input_dir (str): The path to the input directory.
        output_dir (str): The path to the output directory.

    Returns:
        list: A list of tuples containing input and output file paths.
    """
    audio_extensions = {".mp3", ".wav", ".flac", ".ogg", ".aac", ".wma", ".m4a", ".opus", ".aiff", ".alac"}
    file_pairs = []
    for root, dirs, files in os.walk(input_dir):
        for file in files:
            if os.path.splitext(file.lower())[1] in audio_extensions:
                input_file = os.path.join(root, file)
                # Preserve directory structure in output
                relative_path = os.path.relpath(root, input_dir)
                output_path = os.path.join(output_dir, relative_path)
                output_file = os.path.join(output_path, file)
                file_pairs.append((input_file, output_file))
    return file_pairs

def main(input_dir, output_dir, num_workers, frame_rate, bit_depth, channels):
    # Convert bit depth from bits to bytes
    sample_width = bit_depth // 8

    # Collect all audio file pairs
    file_pairs = get_all_audio_files(input_dir, output_dir)
    
    if not file_pairs:
        print("No audio files found in the input directory.")
        return
    
    # Prepare the conversion function with the specified parameters
    convert_func = partial(convert_audio, frame_rate=frame_rate, sample_width=sample_width, channels=channels)
    
    # Parallel processing
    with concurrent.futures.ProcessPoolExecutor(max_workers=num_workers) as executor:
        # Use TQDM for the progress bar
        results = list(tqdm(executor.map(convert_func, file_pairs), total=len(file_pairs), desc="Converting", unit="file"))
    
    # Display results
    success_count = 0
    failure_count = 0
    for result in results:
        if result.startswith("Success"):
            success_count += 1
        else:
            failure_count += 1
            print(result)
    
    print(f"\nConverted: {success_count} files")
    if failure_count > 0:
        print(f"Failed: {failure_count} files")

if __name__ == "__main__":
    # Handle command-line arguments
    parser = argparse.ArgumentParser(description="Parallel audio converter with customizable parameters")
    parser.add_argument('--input_dir', '-i', type=str, required=True, help='Path to the input directory')
    parser.add_argument('--output_dir', '-o', type=str, required=True, help='Path to the output directory')
    parser.add_argument('--workers', type=int, default=os.cpu_count(), help='Number of parallel processes (default: number of CPU cores)')
    parser.add_argument('--frame_rate', type=int, default=24000, help='Sampling rate in Hz (default: 24000)')
    parser.add_argument('--bit_depth', type=int, default=16, choices=[8, 16, 24, 32], help='Bit depth in bits (default: 16)')
    parser.add_argument('--channels', type=int, default=1, choices=[1, 2], help='Number of channels (1: mono, 2: stereo) (default: 1)')

    args = parser.parse_args()
    
    main(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        num_workers=args.workers,
        frame_rate=args.frame_rate,
        bit_depth=args.bit_depth,
        channels=args.channels
    )
