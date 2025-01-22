import os
import argparse
import subprocess
import time
import datetime  # Required for timestamps
import sys
from multiprocessing import Process, Queue

# Maximum number of retries for processing a single file
MAX_RETRIES = 3
# Timeout in seconds
TIMEOUT = 600  # 10 minutes

def get_available_gpus():
    """
    Queries the available GPU indices using nvidia-smi.
    """
    try:
        command = ["nvidia-smi", "--query-gpu=index", "--format=csv,noheader"]
        result = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        gpu_indices = result.stdout.decode().strip().split('\n')
        gpu_ids = [int(idx) for idx in gpu_indices if idx.strip().isdigit()]
        return gpu_ids
    except Exception as e:
        print(f"Error querying GPUs: {e}")
        return []

# This function returns the duration of the audio file in seconds.
def get_audio_duration(audio_file):
    command = [
        "ffprobe",
        "-i", audio_file,
        "-show_entries", "format=duration",
        "-v", "quiet",
        "-of", "csv=p=0"
    ]
    try:
        result = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        duration_str = result.stdout.decode().strip()
        duration = float(duration_str)
        return duration
    except Exception as e:
        print(f"Failed to determine audio length for {audio_file}: {e}")
        return 0

# This function handles processes assigned to each GPU.
def worker(gpu_id, task_queue):
    while True:
        try:
            # Try to get a new audio file from the task list.
            task = task_queue.get_nowait()
            audio_file, retries = task
        except Exception:
            # If the task list is empty, exit the loop.
            break

        # Determine the output JSON file path.
        json_file = os.path.splitext(audio_file)[0] + ".json"

        # Safety check, although such a file should no longer exist.
        if os.path.exists(json_file):
            print(f"Already exists: {json_file}, skipping in worker...")
            continue

        # Use the audio file's directory as the output directory.
        output_dir = os.path.dirname(audio_file)

        # Assemble the WhisperX command with the appropriate parameters.
        command = [
            "whisperx",
            audio_file,
            "--model", "large-v3",
            "--output_format", "json",
            "--language", "hu",
            "--task", "transcribe",
            "--beam_size", "5",
            "--fp16", "False",
            "--verbose", "True",
            "--device", "cuda",
            "--device_index", str(gpu_id),
            # "--batch_size", "12",
            "--output_dir", output_dir
        ]

        try:
            print(f"Processing on GPU-{gpu_id}: {audio_file}")
            # Start timing the processing
            start_time = time.time()
            start_datetime = datetime.datetime.now()

            # Run the command with a timeout.
            result = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=TIMEOUT)

            # End timing the processing
            end_time = time.time()
            end_datetime = datetime.datetime.now()
            processing_time = end_time - start_time

            # Determine the audio length
            audio_duration = get_audio_duration(audio_file)
            # Calculate the ratio
            ratio = audio_duration / processing_time if processing_time > 0 else 0

            # Print the results in the requested format
            print(f"Successfully processed on GPU-{gpu_id}:")
            print(f"Processed file: {audio_file},")
            print(f"Audio length: {audio_duration:.2f} s,")
            print(f"Processing time: {processing_time:.2f} s,")
            print(f"Ratio: {ratio:.2f}")
            print(f"Start time: {start_datetime.strftime('%Y.%m.%d %H:%M')}")
            print(f"End time: {end_datetime.strftime('%Y.%m.%d %H:%M')}\n")
        except subprocess.TimeoutExpired:
            print(f"Timeout: Processing {audio_file} on GPU-{gpu_id} exceeded the {TIMEOUT} seconds limit.")
            if retries < MAX_RETRIES:
                print(f"Retrying {retries + 1}/{MAX_RETRIES}...")
                task_queue.put((audio_file, retries + 1))
            else:
                print(f"Maximum retries reached: Processing {audio_file} failed.\n")
        except subprocess.CalledProcessError as e:
            print(f"Error processing {audio_file} on GPU-{gpu_id}: {e.stderr.decode()}")
            if retries < MAX_RETRIES:
                print(f"Retrying {retries + 1}/{MAX_RETRIES}...")
                task_queue.put((audio_file, retries + 1))
            else:
                print(f"Maximum retries reached: Processing {audio_file} failed.\n")

# This function collects all audio files in the given directory and its subdirectories.
def get_audio_files(directory):
    # Supported audio file extensions.
    audio_extensions = (".mp3", ".wav", ".flac", ".m4a", ".opus")
    audio_files = []

    # Traverse the directories and subdirectories.
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.lower().endswith(audio_extensions):
                audio_files.append(os.path.join(root, file))

    return audio_files

# This function starts the processes assigned to GPUs and manages the task list.
def transcribe_directory(directory, gpu_ids):
    # Collect all audio files.
    audio_files = get_audio_files(directory)

    # Create the task list, including the number of retries.
    task_queue = Queue()

    # Only add audio files to the task list that do not have a JSON counterpart.
    tasks_added = 0
    for audio_file in audio_files:
        json_file = os.path.splitext(audio_file)[0] + ".json"
        if not os.path.exists(json_file):
            task_queue.put((audio_file, 0))  # (file, number of retries)
            tasks_added += 1
        else:
            print(f"Already exists: {json_file}, skipping in task list...")

    # If there are no files to process, notify the user and exit.
    if tasks_added == 0:
        print("No files to process.")
        return

    # List of processes.
    processes = []

    # Create a process for each GPU.
    for gpu_id in gpu_ids:
        p = Process(target=worker, args=(gpu_id, task_queue))
        processes.append(p)
        p.start()

    # Wait for all processes to finish.
    for p in processes:
        p.join()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Transcribe audio files in a directory and its subdirectories using WhisperX with multiple GPUs.")
    parser.add_argument("directory", type=str, help="The directory containing the audio files.")
    parser.add_argument('--gpus', type=str, default=None, help="GPU indices to use, separated by commas (e.g., '0,2,3')")

    args = parser.parse_args()

    if not os.path.isdir(args.directory):
        print(f"Error: The specified directory does not exist: {args.directory}")
        sys.exit(1)

    # Determine GPUs to use
    if args.gpus:
        try:
            specified_gpus = [int(x.strip()) for x in args.gpus.split(',')]
        except ValueError:
            print("Error: The --gpus argument must be a comma-separated list of integers.")
            sys.exit(1)
        available_gpus = get_available_gpus()
        if not available_gpus:
            print("Error: No GPUs available.")
            sys.exit(1)
        # Check if the specified GPUs are available
        invalid_gpus = [gpu for gpu in specified_gpus if gpu not in available_gpus]
        if invalid_gpus:
            print(f"Error: The specified GPUs are not available: {invalid_gpus}")
            sys.exit(1)
        gpu_ids = specified_gpus
    else:
        gpu_ids = get_available_gpus()
        if not gpu_ids:
            print("Error: No GPUs available.")
            sys.exit(1)

    # Start transcription with the determined GPUs
    transcribe_directory(args.directory, gpu_ids)
