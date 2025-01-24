import os
import json
import argparse
import multiprocessing as mp
from collections import defaultdict
from tqdm import tqdm
import shutil

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
    (exact_matches, normalized_matches, total_lines, lang_stats, basename)

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
    - basename: the basename being processed
    """
    txt_path = basename + '.txt'
    json_path = basename + '.json'
    mp3_path = basename + '.mp3'

    # Only proceed if all three files exist
    if not (os.path.exists(txt_path) and os.path.exists(json_path) and os.path.exists(mp3_path)):
        return 0, 0, 0, {}, basename

    # Read TXT file
    try:
        with open(txt_path, 'r', encoding='utf-8') as f:
            txt_lines = [line.strip() for line in f.readlines()]
    except OSError:
        return 0, 0, 0, {}, basename

    # Read JSON file
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            json_texts = [segment['text'].strip() for segment in data.get('segments', [])]
    except (OSError, json.JSONDecodeError):
        return 0, 0, 0, {}, basename

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

    return exact_matches, normalized_matches, total, lang_stats, basename

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
                        help='Path to the input directory')
    parser.add_argument('-d', '--max_diff', type=int, default=0, 
                        help='Maximum allowed character difference for normalized comparison (default: 0)')
    parser.add_argument('-o', '--output', required=True,
                        help='Path to the output directory where non-matching file groups will be moved')
    
    args = parser.parse_args()
    root_dir = args.input
    max_diff = args.max_diff
    output_dir = args.output

    if not os.path.isdir(root_dir):
        print(f"A megadott útvonal nem érvényes könyvtár: {root_dir}")
        return

    if not os.path.exists(output_dir):
        try:
            os.makedirs(output_dir)
            print(f"Létrehozva az output könyvtár: {output_dir}")
        except OSError as e:
            print(f"Nem sikerült létrehozni az output könyvtárat: {output_dir}\nHiba: {e}")
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
    global_lang_stats = defaultdict(lambda: {
        "matched_exact": 0,
        "unmatched_exact": 0,
        "matched_norm": 0,
        "unmatched_norm": 0
    })

    # Lista a mozgatandó basenames-hez
    basenames_to_move = []

    # 5) Parallel processing
    with mp.Pool() as pool:
        # Progress bar
        for result in tqdm(
            pool.imap_unordered(process_basename, tasks),
            total=len(tasks),
            desc="Feldolgozás"
        ):
            exact_matches, normalized_matches, lines, lang_stats, basename = result

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

                # Ha nincs egyezés a normalizált összehasonlítás után
                if normalized_matches == 0:
                    basenames_to_move.append(basename)

    # 6) Output general results
    print("\n--- Általános Statisztikák ---")
    if total_lines > 0:
        print(f"Összes feldolgozott fájlcsoport (mindhárom fájl jelen van): {file_count}")
        print(f"Összesített összehasonlított sorok száma: {total_lines}\n")

        print(f"Pontosan egyező sorok száma (EXACT): {total_exact_matches}")
        print(f"Pontosan egyezés aránya (EXACT): {total_exact_matches / total_lines * 100:.2f}%\n")

        print(f"Normalizáltan egyező sorok száma (max_diff={max_diff}): {total_normalized_matches}")
        print(f"Normalizált egyezés aránya: {total_normalized_matches / total_lines * 100:.2f}%")
    else:
        print("Nincsenek összehasonlítandó sorok vagy nem található három fájlból álló csoport.")

    # 7) Compile language-specific statistics
    print("\n--- Nyelvspecifikus Statisztikák ---")

    # Helper totals across languages
    # EXACT
    all_unmatched_exact = sum(s["unmatched_exact"] for s in global_lang_stats.values())
    all_matched_exact = sum(s["matched_exact"] for s in global_lang_stats.values())

    # NORMALIZED
    all_matched_norm = sum(s["matched_norm"] for s in global_lang_stats.values())

    # 7/a) Distribution of non-matching (EXACT) lines by language
    print("\nAz egyezést nem elért (EXACT) sorok eloszlása nyelvenként:")
    if all_unmatched_exact > 0:
        for lang in sorted(global_lang_stats.keys()):
            unmatched = global_lang_stats[lang]["unmatched_exact"]
            perc = unmatched / all_unmatched_exact * 100 if all_unmatched_exact else 0
            print(f"{lang}: {unmatched} sor ({perc:.2f}%)")
    else:
        print("Nincsenek egyezést nem elért sorok (EXACT).")

    # 7/b) Distribution of matching (EXACT) lines by language
    print("\nAz egyező (EXACT) sorok eloszlása nyelvenként:")
    if all_matched_exact > 0:
        for lang in sorted(global_lang_stats.keys()):
            matched = global_lang_stats[lang]["matched_exact"]
            perc = matched / all_matched_exact * 100 if all_matched_exact else 0
            print(f"{lang}: {matched} sor ({perc:.2f}%)")
    else:
        print("Nincsenek egyező sorok (EXACT).")

    # 7/c) Distribution of matching (normalized) lines by language
    print("\nA normalizáltan egyező sorok eloszlása nyelvenként:")
    if all_matched_norm > 0:
        for lang in sorted(global_lang_stats.keys()):
            matched_norm = global_lang_stats[lang]["matched_norm"]
            perc = matched_norm / all_matched_norm * 100 if all_matched_norm else 0
            print(f"{lang}: {matched_norm} sor ({perc:.2f}%)")
    else:
        print("Nincsenek normalizáltan egyező sorok.")

    # 8) Mozgatás az output könyvtárba
    if basenames_to_move:
        print(f"\nMozgatásra kerülő fájlhármasok száma: {len(basenames_to_move)}")
        for basename in tqdm(basenames_to_move, desc="Mozgatás"):
            # Eredeti fájlok
            txt_path = basename + '.txt'
            json_path = basename + '.json'
            mp3_path = basename + '.mp3'

            # Relatív útvonal meghatározása az input könyvtárhoz képest
            rel_path = os.path.relpath(basename, root_dir)
            rel_dir = os.path.dirname(rel_path)

            # Cél könyvtár
            dest_dir = os.path.join(output_dir, rel_dir)
            os.makedirs(dest_dir, exist_ok=True)

            # Cél fájlok útvonala
            dest_txt = os.path.join(dest_dir, os.path.basename(txt_path))
            dest_json = os.path.join(dest_dir, os.path.basename(json_path))
            dest_mp3 = os.path.join(dest_dir, os.path.basename(mp3_path))

            try:
                shutil.move(txt_path, dest_txt)
                shutil.move(json_path, dest_json)
                shutil.move(mp3_path, dest_mp3)
            except OSError as e:
                print(f"Hiba történt a fájlok mozgatása során: {basename}\nHiba: {e}")
    else:
        print("\nNincsenek olyan fájlhármasok, amelyeknél a normalizált összehasonlítás nem talált egyezést.")

if __name__ == "__main__":
    main()

