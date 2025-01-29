import os
import argparse
import gc
import time
import datetime
import sys
from multiprocessing import Process, Queue, current_process
import subprocess
import json

# Maximum retries for processing a file
MAX_RETRIES = 3
# Timeout in seconds (not implemented in the current script)
TIMEOUT = 600  # 10 minutes

def get_available_gpus():
    """
    Retrieves available GPU indices using nvidia-smi.
    """
    try:
        command = ["nvidia-smi", "--query-gpu=index", "--format=csv,noheader"]
        result = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        gpu_indices = result.stdout.decode().strip().split('\n')
        gpu_ids = [int(idx) for idx in gpu_indices if idx.strip().isdigit()]
        return gpu_ids
    except Exception as e:
        print(f"Error while querying GPUs: {e}")
        return []

def get_audio_duration(audio_file):
    """
    Returns the duration of the audio file in seconds.
    """
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
        print(f"Failed to determine the duration of the audio file: {audio_file} - {e}")
        return 0

def worker(gpu_id, task_queue):
    """
    Function to handle processes assigned to GPUs.
    """
    # Set the CUDA_VISIBLE_DEVICES environment variable so only the specified GPU is visible
    os.environ["CUDA_VISIBLE_DEVICES"] = str(gpu_id)
    device = "cuda"  # 'cuda' now refers to the specific GPU

    model = None  # Initialize the model variable

    try:
        # Import libraries using CUDA within the worker function
        import torch
        import whisperx

        print(f"Process {current_process().name} set up for GPU-{gpu_id}.")

        # Load the WhisperX model
        print(f"GPU-{gpu_id}: Loading WhisperX model...")
        model = whisperx.load_model("large-v3", device=device, compute_type="float16")
        print(f"GPU-{gpu_id}: Model loaded.")

        while True:
            try:
                task = task_queue.get_nowait()
            except:
                # No more tasks
                break

            audio_file, retries = task
            json_file = os.path.splitext(audio_file)[0] + ".json"

            if os.path.exists(json_file):
                print(f"Already exists: {json_file}, skipping processing...")
                continue

            try:
                print(f"Processing with GPU-{gpu_id}: {audio_file}")
                start_time = time.time()
                start_datetime = datetime.datetime.now()

                # Load and transcribe audio
                audio = whisperx.load_audio(audio_file)
                result = model.transcribe(audio, batch_size=16)
                print(f"Transcription completed: {audio_file}")

                # Align transcription
                align_language_code = result["language"]  # Use detected language
                print(f"GPU-{gpu_id}: Loading alignment model for language: {align_language_code}")
                model_a, metadata = whisperx.load_align_model(language_code=align_language_code, device=device)
                result_aligned = whisperx.align(result["segments"], model_a, metadata, audio, device, return_char_alignments=False)
                print(f"Alignment completed: {audio_file}")

                # Save results
                with open(json_file, "w", encoding="utf-8") as f:
                    json.dump(result_aligned, f, ensure_ascii=False, indent=4)

                end_time = time.time()
                end_datetime = datetime.datetime.now()
                processing_time = end_time - start_time

                audio_duration = get_audio_duration(audio_file)
                ratio = audio_duration / processing_time if processing_time > 0 else 0

                print(f"Successfully processed by GPU-{gpu_id}:")
                print(f"Processed file: {audio_file},")
                print(f"Audio duration: {audio_duration:.2f} s,")
                print(f"Processing time: {processing_time:.2f} s,")
                print(f"Real time ratio: {ratio:.2f}")
                print(f"Start time: {start_datetime.strftime('%Y-%m-%d %H:%M')}")
                print(f"End time: {end_datetime.strftime('%Y-%m-%d %H:%M')}\n")

            except Exception as e:
                print(f"Error processing file on GPU-{gpu_id}: {audio_file} - {e}")
                if retries < MAX_RETRIES:
                    print(f"Retrying {retries + 1}/{MAX_RETRIES}...\n")
                    task_queue.put((audio_file, retries + 1))
                else:
                    print(f"Maximum retries reached: Failed to process {audio_file}.\n")

    except Exception as main_e:
        print(f"Main error in GPU-{gpu_id} process: {main_e}")

    finally:
        # Free GPU memory at the end of the process if the model was loaded
        if model is not None:
            try:
                print(f"GPU-{gpu_id}: Freeing GPU memory...")
                del model
                gc.collect()
                torch.cuda.empty_cache()
                print(f"GPU-{gpu_id}: GPU memory freed.")
            except Exception as cleanup_e:
                print(f"Error freeing GPU memory on GPU-{gpu_id}: {cleanup_e}")
        else:
            print(f"GPU-{gpu_id}: Model was not loaded, memory cleanup not needed.")

def get_audio_files(directory):
    """
    Collects all audio files in the specified directory and subdirectories.
    """
    audio_extensions = (".mp3", ".wav", ".flac", ".m4a", ".opus", ".ogg", ".wma", ".aac", ".webm", ".weba") 
    audio_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.lower().endswith(audio_extensions):
                audio_files.append(os.path.join(root, file))
    return audio_files

def transcribe_directory(directory, gpu_ids):
    """
    Function to launch processes and handle task lists.
    """
    audio_files = get_audio_files(directory)
    task_queue = Queue()
    tasks_added = 0

    for audio_file in audio_files:
        json_file = os.path.splitext(audio_file)[0] + ".json"
        if not os.path.exists(json_file):
            task_queue.put((audio_file, 0))
            tasks_added += 1
        else:
            print(f"Already exists: {json_file}, skipping task queue...")

    if tasks_added == 0:
        print("No files to process.")
        return

    processes = []
    for gpu_id in gpu_ids:
        p = Process(target=worker, args=(gpu_id, task_queue), name=f"GPU-{gpu_id}-Process")
        processes.append(p)
        p.start()
        print(f"Process started: {p.name} on GPU-{gpu_id}.")

    for p in processes:
        p.join()
        print(f"Process finished: {p.name}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Transcribe and align audio files in a directory and its subdirectories using WhisperX with multiple GPUs.")
    parser.add_argument("directory", type=str, help="The directory containing the audio files.")
    parser.add_argument('--gpus', type=str, default=None, help="Comma-separated list of GPU indices to use (e.g., '0,2,3')")

    args = parser.parse_args()

    if not os.path.isdir(args.directory):
        print(f"Error: The specified directory does not exist: {args.directory}")
        sys.exit(1)

    # Determine GPUs to use
    if args.gpus:
        try:
            specified_gpus = [int(x.strip()) for x in args.gpus.split(',')]
        except ValueError:
            print("Error: --gpus argument must be a comma-separated list of integers.")
            sys.exit(1)
        available_gpus = get_available_gpus()
        if not available_gpus:
            print("Error: No GPUs available.")
            sys.exit(1)
        invalid_gpus = [gpu for gpu in specified_gpus if gpu not in available_gpus]
        if invalid_gpus:
            print(f"Error: Specified GPUs are not available: {invalid_gpus}")
            sys.exit(1)
        gpu_ids = specified_gpus
    else:
        gpu_ids = get_available_gpus()
        if not gpu_ids:
            print("Error: No GPUs available.")
            sys.exit(1)

    print(f"Using GPUs: {gpu_ids}")

    # Start transcription and alignment with specified GPUs
    transcribe_directory(args.directory, gpu_ids)
