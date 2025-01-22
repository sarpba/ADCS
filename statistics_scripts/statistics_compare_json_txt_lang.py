import os
import json
import argparse
import multiprocessing as mp
from collections import defaultdict
from tqdm import tqdm

def get_all_basenames(root_dir):
    """
    Iterates through the given directory (and its subdirectories),
    and collects the base names (without extension) of files
    that have .mp3, .txt, or .json extensions.
    """
    basenames = set()
    for dirpath, dirnames, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename.endswith(('.mp3', '.txt', '.json')):
                basename = os.path.splitext(filename)[0]
                basenames.add(os.path.join(dirpath, basename))
    return basenames

def normalize_text(text):
    """
    Normalizes the text:
    - Trims leading and trailing whitespace
    - Replaces multiple spaces with a single space
    - Converts to lowercase
    """
    return ' '.join(text.strip().split()).lower()

def levenshtein_distance(s1, s2):
    """
    Calculates the Levenshtein distance between two strings.
    This is the minimum number of edit steps (insertion, deletion, substitution)
    required to transform s1 into s2.
    """
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)

    # Ensure that s1 is the longer string.
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1           # Inserting a character
            deletions = current_row[j] + 1                 # Deleting a character
            substitutions = previous_row[j] + (c1 != c2)   # Substitution (0 or 1)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]

def compare_files(basename, max_diff):
    """
    Compares the lines of .txt and .json files associated with a given basename.

    Returns:
    (exact_matches, normalized_matches, total_lines, lang_stats)

    - exact_matches: number of lines that match EXACTLY
    - normalized_matches: number of lines that match NORMALLY (considering max_diff character differences)
    - total_lines: the actual number of lines compared
    - lang_stats: { 
         language: {
            "matched_exact": ...,
            "unmatched_exact": ...,
            "matched_norm": ...,
            "unmatched_norm": ...
         }
      }
    """
    txt_path = basename + '.txt'
    json_path = basename + '.json'
    mp3_path = basename + '.mp3'

    # Only proceed if all three files exist
    if not (os.path.exists(txt_path) and os.path.exists(json_path) and os.path.exists(mp3_path)):
        return 0, 0, 0, {}

    # Read TXT file
    try:
        with open(txt_path, 'r', encoding='utf-8') as f:
            txt_lines = [line.strip() for line in f.readlines()]
    except OSError:
        return 0, 0, 0, {}

    # Read JSON file
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            json_texts = [segment['text'].strip() for segment in data.get('segments', [])]
    except (OSError, json.JSONDecodeError):
        return 0, 0, 0, {}

    # Extract language from JSON
    language = data.get("language", "UNKNOWN")

    # Statistics
    exact_matches = 0
    normalized_matches = 0
    total = min(len(txt_lines), len(json_texts))

    # Language-specific counters
    # Exact matches + non-matches, normalized matches + non-matches
    lang_stats = {
        language: {
            "matched_exact": 0,
            "unmatched_exact": 0,
            "matched_norm": 0,
            "unmatched_norm": 0
        }
    }

    for i in range(total):
        txt_line = txt_lines[i]
        json_line = json_texts[i]

        # 1) EXACT MATCH
        if txt_line == json_line:
            exact_matches += 1
            # If EXACT, then normalized also matches automatically
            normalized_matches += 1

            lang_stats[language]["matched_exact"] += 1
            lang_stats[language]["matched_norm"] += 1
        else:
            # Does not match exactly
            lang_stats[language]["unmatched_exact"] += 1

            # 2) NORMALIZED MATCH
            ntxt = normalize_text(txt_line)
            njson = normalize_text(json_line)

            if ntxt == njson:
                normalized_matches += 1
                lang_stats[language]["matched_norm"] += 1
            else:
                dist = levenshtein_distance(ntxt, njson)
                if dist <= max_diff:
                    normalized_matches += 1
                    lang_stats[language]["matched_norm"] += 1
                else:
                    # Does not match even when normalized
                    lang_stats[language]["unmatched_norm"] += 1

    return exact_matches, normalized_matches, total, lang_stats

def process_basename(args):
    """
    For the multiprocessing Pool: packages the call to compare_files.
    """
    basename, max_diff = args
    return compare_files(basename, max_diff)

def main():
    parser = argparse.ArgumentParser(
        description='Generate statistics for .mp3, .txt, .json files found in a directory.'
    )
    parser.add_argument('-i', '--input', required=True, 
                        help='Path to the directory')
    parser.add_argument('-d', '--max_diff', type=int, default=0, 
                        help='Maximum allowed character difference for normalized comparison (default: 0)')
    
    args = parser.parse_args()
    root_dir = args.input
    max_diff = args.max_diff

    if not os.path.isdir(root_dir):
        print(f"The provided path is not a valid directory: {root_dir}")
        return
    
    # 1) Collect all basenames
    basenames = get_all_basenames(root_dir)

    # 2) Prepare the tasks
    tasks = [(bn, max_diff) for bn in basenames]

    # 3) Aggregate statistics
    total_exact_matches = 0
    total_normalized_matches = 0
    total_lines = 0
    file_count = 0

    # 4) Language-specific statistics
    # Stores the summary per language:
    #   "matched_exact": total EXACT matches
    #   "unmatched_exact": total EXACT non-matches
    #   "matched_norm": total NORMALIZED matches
    #   "unmatched_norm": total NORMALIZED non-matches
    global_lang_stats = defaultdict(lambda: {
        "matched_exact": 0,
        "unmatched_exact": 0,
        "matched_norm": 0,
        "unmatched_norm": 0
    })

    # 5) Parallel processing
    with mp.Pool() as pool:
        # Progress bar
        for exact_matches, normalized_matches, lines, lang_stats in tqdm(
            pool.imap_unordered(process_basename, tasks),
            total=len(tasks),
            desc="Processing"
        ):
            # If there were lines to compare in this file group
            if lines > 0:
                file_count += 1
                total_exact_matches += exact_matches
                total_normalized_matches += normalized_matches
                total_lines += lines

                # Aggregate language-specific statistics
                for lang, stats in lang_stats.items():
                    global_lang_stats[lang]["matched_exact"] += stats["matched_exact"]
                    global_lang_stats[lang]["unmatched_exact"] += stats["unmatched_exact"]
                    global_lang_stats[lang]["matched_norm"] += stats["matched_norm"]
                    global_lang_stats[lang]["unmatched_norm"] += stats["unmatched_norm"]

    # 6) Output general results
    print("\n--- General Statistics ---")
    if total_lines > 0:
        print(f"Total processed file groups (all three files present): {file_count}")
        print(f"Total compared lines: {total_lines}\n")

        print(f"Number of exactly matching lines (EXACT): {total_exact_matches}")
        print(f"Exact match ratio (EXACT): {total_exact_matches / total_lines * 100:.2f}%\n")

        print(f"Number of normalized matching lines (max_diff={max_diff}): {total_normalized_matches}")
        print(f"Normalized match ratio: {total_normalized_matches / total_lines * 100:.2f}%")
    else:
        print("No lines to compare or no file groups with all three files found.")

    # 7) Compile language-specific statistics
    print("\n--- Language-specific Statistics ---")

    # Helper totals across languages
    # EXACT
    all_unmatched_exact = sum(s["unmatched_exact"] for s in global_lang_stats.values())
    all_matched_exact = sum(s["matched_exact"] for s in global_lang_stats.values())

    # NORMALIZED
    all_matched_norm = sum(s["matched_norm"] for s in global_lang_stats.values())

    # 7/a) Distribution of non-matching (EXACT) lines by language
    print("\nDistribution of non-matching (EXACT) lines by language:")
    if all_unmatched_exact > 0:
        for lang in sorted(global_lang_stats.keys()):
            unmatched = global_lang_stats[lang]["unmatched_exact"]
            perc = unmatched / all_unmatched_exact * 100 if all_unmatched_exact else 0
            print(f"{lang}: {unmatched} lines ({perc:.2f}%)")
    else:
        print("No non-matching lines (EXACT).")

    # 7/b) Distribution of matching (EXACT) lines by language
    print("\nDistribution of matching (EXACT) lines by language:")
    if all_matched_exact > 0:
        for lang in sorted(global_lang_stats.keys()):
            matched = global_lang_stats[lang]["matched_exact"]
            perc = matched / all_matched_exact * 100 if all_matched_exact else 0
            print(f"{lang}: {matched} lines ({perc:.2f}%)")
    else:
        print("No matching lines (EXACT).")

    # 7/c) Distribution of matching (normalized) lines by language
    print("\nDistribution of matching (normalized) lines by language:")
    if all_matched_norm > 0:
        for lang in sorted(global_lang_stats.keys()):
            matched_norm = global_lang_stats[lang]["matched_norm"]
            perc = matched_norm / all_matched_norm * 100 if all_matched_norm else 0
            print(f"{lang}: {matched_norm} lines ({perc:.2f}%)")
    else:
        print("No matching (normalized) lines.")

if __name__ == "__main__":
    main()
