#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import argparse
import gc
import time
import datetime
import sys
from multiprocessing import Process, Queue, current_process, Manager
import subprocess
import json
import queue  # Required for the queue.Empty exception

# Maximum number of attempts to process a file
MAX_RETRIES = 3
# Timeout in seconds (not implemented in the current script)
TIMEOUT = 600  # 10 minutes

def get_available_gpus():
    """
    Retrieves the indices of available GPUs using nvidia-smi.
    """
    try:
        command = ["nvidia-smi", "--query-gpu=index", "--format=csv,noheader"]
        result = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        gpu_indices = result.stdout.decode().strip().split('\n')
        gpu_ids = [int(idx) for idx in gpu_indices if idx.strip().isdigit()]
        return gpu_ids
    except Exception as e:
        print(f"Error retrieving GPUs: {e}")
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
        print(f"Failed to determine audio duration for file: {audio_file} - {e}")
        return 0

def worker(gpu_id, task_queue, progress_queue, last_activity):
    """
    Function to handle processes assigned to GPUs (transcription only, no alignment).
    Signals the main process using progress_queue: every successful file processing sends a message
    {'status': 'done', 'file': audio_file, 'processing_time': ... }.

    Updates last_activity[gpu_id] = time.time() to indicate when the GPU was last active.
    """
    # Set CUDA_VISIBLE_DEVICES environment variable to make only the assigned GPU visible
    os.environ["CUDA_VISIBLE_DEVICES"] = str(gpu_id)
    device = "cuda"  # 'cuda' now refers to the assigned GPU

    model = None  # Initialize the model variable

    try:
        import torch
        import whisperx

        print(f"Process {current_process().name} set up for GPU-{gpu_id}.")
        print(f"GPU-{gpu_id}: Loading WhisperX model...")
        model = whisperx.load_model("large-v3-turbo", device=device, compute_type="float16")
        print(f"GPU-{gpu_id}: Model loaded.")

        no_task_count = 0
        max_no_task_tries = 3

        while True:
            try:
                # Immediately try to retrieve a task from the queue
                task = task_queue.get_nowait()
                # Update last activity if a task is retrieved
                last_activity[gpu_id] = time.time()
            except queue.Empty:
                # If no task is in the queue, wait 1 second
                if no_task_count < max_no_task_tries:
                    no_task_count += 1
                    time.sleep(1)
                    continue
                else:
                    # Exit the worker if the queue remains empty after 3 tries
                    print(f"GPU-{gpu_id}: No more tasks, exiting after 3 tries.")
                    break
            except Exception as e:
                # Handle other errors when retrieving a task
                print(f"GPU-{gpu_id}: Error retrieving task: {e}")
                break

            # Reset the counter if a task is retrieved
            no_task_count = 0

            audio_file, retries = task
            json_file = os.path.splitext(audio_file)[0] + ".json"

            # Skip processing if the JSON already exists
            if os.path.exists(json_file):
                print(f"Already exists: {json_file}, skipping...")
                continue

            try:
                print(f"Processing {audio_file} using GPU-{gpu_id}")
                start_time = time.time()
                start_datetime = datetime.datetime.now()

                # Load and transcribe audio
                audio = whisperx.load_audio(audio_file)
                result = model.transcribe(audio, batch_size=16)
                print(f"Transcription completed: {audio_file}")

                # Update activity after completing work
                last_activity[gpu_id] = time.time()

                # Save results to JSON
                with open(json_file, "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False, indent=4)

                end_time = time.time()
                end_datetime = datetime.datetime.now()
                processing_time = end_time - start_time

                audio_duration = get_audio_duration(audio_file)
                ratio = audio_duration / processing_time if processing_time > 0 else 0

                print(f"Successfully processed by GPU-{gpu_id}:")
                print(f"Processed file: {audio_file}")
                print(f"Audio duration: {audio_duration:.2f} s")
                print(f"Processing time: {processing_time:.2f} s")
                print(f"Ratio: {ratio:.2f}")
                print(f"Start time: {start_datetime.strftime('%Y.%m.%d %H:%M')}")
                print(f"End time: {end_datetime.strftime('%Y.%m.%d %H:%M')}\n")

                # Send a message to progress_queue to indicate task completion
                progress_queue.put({
                    "status": "done",
                    "file": audio_file,
                    "processing_time": processing_time
                })

            except Exception as e:
                print(f"Error processing file {audio_file} on GPU-{gpu_id}: {e}")
                if retries < MAX_RETRIES:
                    print(f"Retrying {retries + 1}/{MAX_RETRIES}...\n")
                    task_queue.put((audio_file, retries + 1))
                else:
                    print(f"Maximum retries reached: {audio_file} failed to process.\n")

    except Exception as main_e:
        print(f"Major error in GPU-{gpu_id} process: {main_e}")

    finally:
        # Free GPU memory when the worker ends (once at the end of the process)
        if model is not None:
            try:
                print(f"GPU-{gpu_id}: Releasing GPU memory...")
                del model
                gc.collect()
                import torch
                torch.cuda.empty_cache()
                print(f"GPU-{gpu_id}: GPU memory released.")
            except Exception as cleanup_e:
                print(f"Error releasing memory on GPU-{gpu_id}: {cleanup_e}")
        else:
            print(f"GPU-{gpu_id}: Model not loaded, no memory to release.")

def get_audio_files(directory):
    """
    Collects all audio files in the given directory and its subdirectories.
    """
    audio_extensions = (".mp3", ".wav", ".flac", ".m4a", ".opus")
    audio_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.lower().endswith(audio_extensions):
                audio_files.append(os.path.join(root, file))
    return audio_files

def transcribe_directory(directory, gpu_ids):
    """
    Function to start processes and manage the task list (transcription only).
    Includes progress tracking and estimated completion time calculation
    based on elapsed time (since the main process started).

    Additionally, if multiple GPUs are used and any GPU is inactive for 10 seconds,
    all processes are terminated, and the script restarts.
    """
    audio_files = get_audio_files(directory)
    task_queue = Queue()
    tasks_added = 0

    # Add all files without existing .json outputs to the task queue
    for audio_file in audio_files:
        json_file = os.path.splitext(audio_file)[0] + ".json"
        if not os.path.exists(json_file):
            task_queue.put((audio_file, 0))
            tasks_added += 1
        else:
            print(f"Already exists: {json_file}, skipping...")

    if tasks_added == 0:
        print("No files to process.")
        return

    print(f"A total of {tasks_added} files need to be processed.")

    # Pass progress_queue to workers to signal when a task is completed
    manager = Manager()
    progress_queue = manager.Queue()

    # Shared dict where workers log the last activity of GPUs
    last_activity = manager.dict()
    for gpu_id in gpu_ids:
        last_activity[gpu_id] = time.time()  # Initialize with current time

    # Start worker processes
    processes = []
    for gpu_id in gpu_ids:
        p = Process(
            target=worker,
            args=(gpu_id, task_queue, progress_queue, last_activity),
            name=f"GPU-{gpu_id}-Process"
        )
        processes.append(p)
        p.start()
        print(f"Process started: {p.name} on GPU-{gpu_id}.")

    tasks_done = 0
    start_time = time.time()

    # Main process tracks completed files, estimates finish time,
    # and monitors GPU inactivity (if multiple GPUs are used).
    while tasks_done < tasks_added:
        try:
            # Wait for a worker to signal task completion
            message = progress_queue.get(timeout=1.0)
            if message["status"] == "done":
                tasks_done += 1
                elapsed_time = time.time() - start_time  # Time elapsed so far

                remaining = tasks_added - tasks_done
                if tasks_done > 0:
                    avg_time_per_file = elapsed_time / tasks_done
                else:
                    avg_time_per_file = 0

                est_remaining_time = avg_time_per_file * remaining
                finish_time_est = datetime.datetime.now() + datetime.timedelta(seconds=est_remaining_time)
                progress_percent = (tasks_done / tasks_added) * 100

                print(
                    f"[{tasks_done}/{tasks_added} - {progress_percent:.1f}%] "
                    f"Done: {message['file']} | "
                    f"Estimated finish: {finish_time_est.strftime('%Y-%m-%d %H:%M:%S')}"
                )

        except:
            # If no message is received within 1 second, simply continue
            pass

        # Monitor 10-second inactivity for multiple GPUs
        if len(gpu_ids) > 1:
            now = time.time()
            for g in gpu_ids:
                if (now - last_activity[g]) > 10:
                    print(f"WARNING: GPU-{g} has been inactive for over 10 seconds.")
                    print("Terminating all processes and restarting the script...")
                    # Terminate all processes
                    for proc in processes:
                        if proc.is_alive():
                            proc.terminate()

                    # Restart the script
                    python = sys.executable
                    os.execl(python, python, *sys.argv)
                    # os.execl() does not return.

    # Wait for all worker processes to finish (if all tasks are completed)
    for p in processes:
        p.join()
        print(f"Process completed: {p.name}")

    total_time = time.time() - start_time
    print(f"All tasks completed. Total processing time: {total_time:.2f} seconds")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Transcription of audio files (using WhisperX) with multiple GPUs. No alignment."
    )
    parser.add_argument("directory", type=str, help="The directory containing the audio files.")
    parser.add_argument('--gpus', type=str, default=None,
                        help="Comma-separated list of GPU indices to use (e.g., '0,2,3')")

    args = parser.parse_args()

    if not os.path.isdir(args.directory):
        print(f"Error: Specified directory does not exist: {args.directory}")
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

    # Start transcription with the specified GPUs
    transcribe_directory(args.directory, gpu_ids)
