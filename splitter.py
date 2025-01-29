import os
import json
import re
import argparse
import random
from pydub import AudioSegment
from concurrent.futures import ProcessPoolExecutor, as_completed
from tqdm import tqdm

def truncated_gauss(mean, std, lower, upper):
    """
    Simple "retry" approach to draw a truncated Gaussian value (float).
    Keeps drawing random.gauss(mean, std) until it falls within [lower, upper].
    """
    while True:
        val = random.gauss(mean, std)
        if lower <= val <= upper:
            return val

def build_sentences(word_segments):
    """
    Splits the 'word_segments' list into sentence-like units based on sentence-ending
    punctuation and uppercase start of the next word.
    Returns a list where each element is:
        {
            'start': (ms),
            'end': (ms),
            'text': (str),
            'words': (list of word dicts)
        }
    """
    sentences = []
    current_words = []
    sentence_start_time = None
    new_sentence = True

    for idx, w in enumerate(word_segments):
        word_text = w.get('word', '')
        start_t = w.get('start', None)
        end_t = w.get('end', None)

        if start_t is None or end_t is None:
            # Skip if there's no start or end time
            continue

        # Store the start time if starting a new sentence
        if new_sentence:
            sentence_start_time = int(start_t * 1000)
            new_sentence = False

        current_words.append(w)

        # Check for sentence-ending punctuation (., !, ?)
        sentence_boundary = False
        if re.search(r'[.!?]$', word_text.strip()):
            sentence_boundary = True

        # Look at the next word if available
        if idx < len(word_segments) - 1:
            next_word = word_segments[idx + 1].get('word', '')
            # If the previous ends with punctuation and the next starts with an uppercase letter
            if sentence_boundary and next_word and next_word[0].isupper():
                sentence_boundary = True
        else:
            # Always end sentence at the last word
            sentence_boundary = True

        if sentence_boundary:
            # End of sentence
            sentence_end_time = int(end_t * 1000)
            text = ' '.join(word['word'].strip() for word in current_words)
            text = re.sub(r'\s+([,.!?])', r'\1', text)  # Remove spaces before punctuation
            sentences.append({
                'start': sentence_start_time,
                'end': sentence_end_time,
                'text': text.strip(),
                'words': current_words
            })
            # Start a new sentence
            current_words = []
            new_sentence = True

    return sentences

def chunk_sentences_random(
    sentences,
    min_sec=1,
    max_sec=30,
    mean_sec=15,
    std_sec=5,
    use_uniform=False
):
    """
    Splits the list of sentences into random chunks.
    - If use_uniform=False (default), chunk target duration is drawn from a Gaussian distribution
      (mean=mean_sec, std=std_sec) with "retry" truncation within [min_sec, max_sec].
    - If use_uniform=True, chunk target duration is drawn from random.uniform(min_sec, max_sec).

    Chunks will never exceed max_sec and aim to reach at least min_sec.
    """
    chunks = []
    i = 0
    n = len(sentences)

    while i < n:
        if use_uniform:
            # Uniform distribution
            target = random.uniform(min_sec, max_sec)
        else:
            # Gaussian (normal) distribution
            target = truncated_gauss(mean_sec, std_sec, min_sec, max_sec)

        chunk_start = sentences[i]['start']
        chunk_end = chunk_start
        chunk_texts = []

        while i < n:
            sent_start = sentences[i]['start']
            sent_end = sentences[i]['end']
            sent_text = sentences[i]['text']

            # If this is the first sentence in the chunk
            if chunk_end == chunk_start:
                chunk_end = sent_end
                chunk_texts.append(sent_text)
                i += 1
            else:
                candidate_end = sent_end
                candidate_dur = (candidate_end - chunk_start) / 1000.0

                if candidate_dur <= max_sec:
                    chunk_end = candidate_end
                    chunk_texts.append(sent_text)
                    i += 1
                else:
                    # Exceeds max_sec, close the chunk
                    break

            current_dur = (chunk_end - chunk_start) / 1000.0
            # Close the chunk if target is reached and at least min_sec is achieved
            if current_dur >= target and current_dur >= min_sec:
                break

        # Extend the chunk if still below min_sec, as long as within max_sec
        current_dur = (chunk_end - chunk_start) / 1000.0
        while current_dur < min_sec and i < n:
            sent_start = sentences[i]['start']
            sent_end = sentences[i]['end']
            sent_text = sentences[i]['text']
            candidate_end = sent_end
            candidate_dur = (candidate_end - chunk_start) / 1000.0

            if candidate_dur <= max_sec:
                chunk_end = candidate_end
                chunk_texts.append(sent_text)
                i += 1
                current_dur = (chunk_end - chunk_start) / 1000.0
            else:
                break

        chunks.append({
            'start': chunk_start,
            'end': chunk_end,
            'text': ' '.join(chunk_texts)
        })

    return chunks

def export_chunk_audio_and_text(audio, chunk, output_dir, base_name,
                                original_extension, chunk_index):
    """
    Extracts the time interval (in ms) specified by 'chunk' from the audio,
    exports it in the appropriate format (original or mp4), and also exports
    the corresponding text to a .txt file.
    """
    new_start_ms = chunk['start']
    new_end_ms = min(chunk['end'], len(audio))

    if new_start_ms >= new_end_ms:
        return f"Invalid cutting points: start={new_start_ms}, end={new_end_ms}", False

    # Extract the segment
    audio_segment = audio[new_start_ms:new_end_ms]
    duration_ms = len(audio_segment)

    # Skip if the audio is too short
    if duration_ms < 200:  # Less than 0.2s
        return None, True  # True indicates too short

    output_audio_path = os.path.join(output_dir, f"{base_name}_chunk_{chunk_index}.{original_extension}")
    try:
        # Export as 'mp4' if the original file was .m4a
        if original_extension == 'm4a':
            audio_segment.export(output_audio_path, format='mp4')
        elif original_extension == 'opus':
            # Decide to save as ogg or opus; here it's opus:
            audio_segment.export(output_audio_path, format='opus')
        else:
            audio_segment.export(output_audio_path, format=original_extension)
    except Exception as e:
        return f"Audio export error: '{output_audio_path}': {e}", False

    # Save text
    output_text_path = os.path.join(output_dir, f"{base_name}_chunk_{chunk_index}.txt")
    try:
        with open(output_text_path, 'w', encoding='utf-8') as txt_file:
            txt_file.write(chunk['text'].strip() + "\n")
    except Exception as e:
        return f"Text file writing error: '{output_text_path}': {e}", False

    return None, False

def process_json_file(args):
    """
    Processes a JSON file (and its corresponding audio file).
    Returns a summary string (with errors or success).
    """
    (json_path,
     audio_dir,
     output_dir,
     relative_path,
     min_sec,
     max_sec,
     mean_sec,
     std_sec,
     use_uniform,
     start_time  # <-- Hozzáadott paraméter
    ) = args

    base_name = os.path.splitext(os.path.basename(json_path))[0]

    audio_extensions = ['.wav', '.mp3', '.flac', '.m4a', '.ogg', '.aac', '.opus', '.webm', '.weba']

    audio_file = None
    original_extension = None
    for ext in audio_extensions:
        potential_audio_path = os.path.join(audio_dir, base_name + ext)
        if os.path.exists(potential_audio_path):
            audio_file = potential_audio_path
            original_extension = ext.lstrip('.').lower()
            break

    if not audio_file:
        return f"Audio file not found: '{base_name}' (JSON: '{json_path}')."

    # Load audio
    try:
        if original_extension == 'opus':
            # Read .opus as 'ogg'
            audio = AudioSegment.from_file(audio_file, format='ogg')
        elif original_extension == 'm4a':
            # Read .m4a as 'mp4'
            audio = AudioSegment.from_file(audio_file, format='mp4')
        else:
            audio = AudioSegment.from_file(audio_file, format=original_extension)
    except Exception as e:
        return f"Error loading audio file '{audio_file}': {e}"

    # Load JSON
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        return f"Error loading JSON file '{json_path}': {e}"

    # Check
    if 'word_segments' not in data:
        return f"The file '{json_path}' does not contain 'word_segments'."

    word_segments = data['word_segments']
    if not word_segments:
        return f"The 'word_segments' list in '{json_path}' is empty."

    # 1) Create sentences
    sentences = build_sentences(word_segments)

    ### START_TIME FEATURE ###
    # Ha a --start_time > 0, akkor csak azokat a mondatokat hagyjuk meg,
    # amelyeknek a 'start' értéke (ms-ben) >= start_time * 1000
    if start_time > 0:
        start_time_ms = int(start_time * 1000)
        sentences = [s for s in sentences if s['start'] >= start_time_ms]
        if not sentences:
            return (f"No sentences found after start_time={start_time}s "
                    f"in '{json_path}'. Skipping.")

    # 2) Random chunking (Gauss or Uniform) – see switch
    final_chunks = chunk_sentences_random(
        sentences,
        min_sec=min_sec,
        max_sec=max_sec,
        mean_sec=mean_sec,
        std_sec=std_sec,
        use_uniform=use_uniform
    )

    # Create output directory
    output_subdir = os.path.join(output_dir, os.path.dirname(relative_path))
    os.makedirs(output_subdir, exist_ok=True)

    # 3) Export chunks
    errors = []
    too_short_skipped = 0
    for i, chunk in enumerate(final_chunks):
        result, is_short = export_chunk_audio_and_text(
            audio, chunk, output_subdir, base_name, original_extension, i
        )
        if result:  # Log an error
            errors.append(result)
        if is_short:
            too_short_skipped += 1

    # Statistics
    stats = (
        f"File: '{base_name}'\n"
        f"Total number of chunks created: {len(final_chunks)}\n"
        f"Skipped too short chunks: {too_short_skipped}"
    )

    if errors:
        return f"{stats}\nErrors:\n" + "\n".join(errors)
    else:
        return f"{stats}\nProcessing completed successfully."

def process_directory(input_dir, output_dir,
                      min_sec, max_sec, mean_sec, std_sec,
                      use_uniform, num_workers,
                      start_time  # <-- Továbbadjuk
                      ):
    """
    Iterates through input_dir, finds all .json files, and processes them.
    """
    json_files = []
    for root, dirs, files in os.walk(input_dir):
        for file in files:
            if file.endswith('.json'):
                json_path = os.path.join(root, file)
                audio_dir = root
                relative_path = os.path.relpath(json_path, input_dir)
                # Pass parameters to process_json_file
                args = (json_path, 
                        audio_dir, 
                        output_dir, 
                        relative_path,
                        min_sec, 
                        max_sec, 
                        mean_sec, 
                        std_sec,
                        use_uniform,
                        start_time)  # <-- Hozzáadjuk az args végére
                json_files.append(args)

    total_files = len(json_files)
    if total_files == 0:
        print("No JSON files to process in the specified input directory.")
        return

    # Parallel processing
    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        future_to_file = {executor.submit(process_json_file, args): args[0] for args in json_files}
        for future in tqdm(as_completed(future_to_file), total=total_files, desc="Processing"):
            json_path = future_to_file[future]
            try:
                result = future.result()
                if result:
                    print(result)
            except Exception as exc:
                print(f"Error occurred while processing '{json_path}': {exc}")

def main():
    parser = argparse.ArgumentParser(
        description="Randomly chunk JSON and audio files between 1–30s (default: 15±5 Gaussian). "
                    "Use the --uniform_dist flag for uniform distribution instead.",
        epilog="""
Example:
  python splitter_gauss.py \\
    --input_dir ./input \\
    --output_dir ./output \\
    --min_sec 5 --max_sec 30 --mean_sec 15 --std_sec 5 \\
    --num_workers 4
  # For uniform distribution:
  python splitter_gauss.py \\
    --input_dir ./input \\
    --output_dir ./output \\
    --min_sec 1 --max_sec 30 \\
    --uniform_dist
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '--input_dir', '-i',
        type=str,
        required=True,
        help='Path to the input directory containing JSON and audio files.'
    )

    parser.add_argument(
        '--output_dir', '-o',
        type=str,
        required=True,
        help='Path to the output directory where processed audio and text files will be saved.'
    )

    parser.add_argument(
        '--min_sec',
        type=float,
        default=1.0,
        help='Minimum duration of the resulting chunks (in seconds). Default: 1.'
    )

    parser.add_argument(
        '--max_sec',
        type=float,
        default=30.0,
        help='Maximum duration of the resulting chunks (in seconds). Default: 30.'
    )

    parser.add_argument(
        '--mean_sec',
        type=float,
        default=15.0,
        help='Mean of the Gaussian distribution for the desired chunk duration. Default: 15. '
             '(Only applies if --uniform_dist is not set.)'
    )

    parser.add_argument(
        '--std_sec',
        type=float,
        default=5.0,
        help='Standard deviation of the Gaussian distribution for the desired chunk duration. Default: 5. '
             '(Only applies if --uniform_dist is not set.)'
    )

    parser.add_argument(
        '--uniform_dist',
        action='store_true',
        default=False,
        help='If set, uses a uniform distribution instead of Gaussian, i.e., selects chunk target duration based on random.uniform(min_sec, max_sec).'
    )

    parser.add_argument(
        '--num_workers',
        type=int,
        default=(os.cpu_count() or 1),
        help='Number of parallel processes. Default: number of CPU cores.'
    )

    ### START_TIME FEATURE ###
    parser.add_argument(
        '--start_time',
        type=float,
        default=0.0,
        help='If specified (> 0), processing will skip all sentences that start before this time (seconds). Default: 0.'
    )

    args = parser.parse_args()

    # Create output directory if it does not exist
    os.makedirs(args.output_dir, exist_ok=True)

    # Optional random seed setup
    # random.seed(42)

    process_directory(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        min_sec=args.min_sec,
        max_sec=args.max_sec,
        mean_sec=args.mean_sec,
        std_sec=args.std_sec,
        use_uniform=args.uniform_dist,
        num_workers=args.num_workers,
        start_time=args.start_time  # <-- Továbbadjuk a process_directory-nak
    )

if __name__ == "__main__":
    main()
