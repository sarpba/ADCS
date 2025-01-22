import os
import json
import re
import argparse
from pydub import AudioSegment
from concurrent.futures import ProcessPoolExecutor, as_completed
from tqdm import tqdm

def process_json_file(args):
    json_path, audio_dir, output_dir, relative_path = args
    base_name = os.path.splitext(os.path.basename(json_path))[0]
    
    audio_extensions = ['.wav', '.mp3', '.flac', '.m4a', '.ogg', '.aac', '.opus']

    audio_file = None
    original_extension = None
    for ext in audio_extensions:
        potential_audio_path = os.path.join(audio_dir, base_name + ext)
        if os.path.exists(potential_audio_path):
            audio_file = potential_audio_path
            original_extension = ext.lstrip('.').lower()
            break

    if not audio_file:
        return f"Audio fájl nem található: '{base_name}' számára. (JSON: '{json_path}')"

    try:
        # Speciális fájlformátumok kezelése
        if original_extension == 'opus':
            # Az .opus fájlokat 'ogg' formátumként kezeljük
            audio = AudioSegment.from_file(audio_file, format='ogg')
        elif original_extension == 'm4a':
            # Az .m4a fájlokat 'mp4' formátumként kezeljük
            audio = AudioSegment.from_file(audio_file, format='mp4')
        else:
            audio = AudioSegment.from_file(audio_file, format=original_extension)
    except Exception as e:
        return f"Hiba történt az audio fájl betöltése közben '{audio_file}': {e}"

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        return f"Hiba történt a JSON fájl betöltése közben '{json_path}': {e}"

    # Csak a 'word_segments' mezőt használjuk
    if 'word_segments' not in data:
        return f"A '{json_path}' fájl nem tartalmaz 'word_segments' mezőt."

    all_words = data.get('word_segments', [])

    sentence_words = []
    sentence_start_time = None
    sentence_counter = 0
    errors = []
    skipped_sentences_start_missing = 0
    skipped_sentences_end_missing = 0

    first_word = True  # Az első szó jelzője
    accumulated_words = []
    accumulated_start_time = None

    for idx, word in enumerate(all_words):
        word_text = word.get('word', '')
        word_start = word.get('start')
        word_end = word.get('end')
        word_clean = word_text.strip()

        # Ellenőrizzük, hogy a szó végén van-e mondatzáró írásjel
        previous_word_ends_sentence = False
        if sentence_words:
            prev_word_text = sentence_words[-1].get('word', '').strip()
            if re.search(r'[.!?]$', prev_word_text):
                previous_word_ends_sentence = True

        # Új mondat kezdete
        if first_word:
            if word_clean and word_clean[0].isupper():
                sentence_words.append(word)
                sentence_start_time = word_start
                first_word = False
        elif previous_word_ends_sentence and word_clean and word_clean[0].isupper():
            # Ha az előző szó végén mondatzáró írásjel volt és a jelenlegi szó nagybetűvel kezdődik
            # Feldolgozzuk az előző mondatot
            result, is_short = process_sentence(audio, sentence_words, sentence_start_time,
                                 output_dir, base_name, original_extension,
                                 relative_path, sentence_counter)
            if result == 'start_missing':
                skipped_sentences_start_missing += 1
            elif result == 'end_missing':
                skipped_sentences_end_missing += 1
            elif isinstance(result, str):
                if is_short:
                    # Ha a szakasz rövid volt, akkor felhalmozzuk
                    accumulated_words.extend(sentence_words)
                    if accumulated_start_time is None:
                        accumulated_start_time = sentence_start_time
                else:
                    errors.append(result)
            else:
                if accumulated_words:
                    # Ha van felhalmozott rövid szakasz, csatoljuk az aktuálishoz
                    sentence_words = accumulated_words + sentence_words
                    sentence_start_time = accumulated_start_time or sentence_start_time
                    accumulated_words = []
                    accumulated_start_time = None
                    # Újra feldolgozzuk az egyesített mondatot
                    result, is_short = process_sentence(audio, sentence_words, sentence_start_time,
                                         output_dir, base_name, original_extension,
                                         relative_path, sentence_counter)
                    if isinstance(result, str) and not is_short:
                        errors.append(result)
                sentence_counter += 1
            # Új mondat inicializálása
            sentence_words = [word]
            sentence_start_time = word_start
        else:
            # Folytatjuk a jelenlegi mondatot
            sentence_words.append(word)

    # Feldolgozzuk az utolsó mondatot
    if sentence_words:
        if accumulated_words:
            # Ha van felhalmozott rövid szakasz, csatoljuk az utolsó mondathoz
            sentence_words = accumulated_words + sentence_words
            sentence_start_time = accumulated_start_time or sentence_start_time
            accumulated_words = []
            accumulated_start_time = None
        result, is_short = process_sentence(audio, sentence_words, sentence_start_time,
                             output_dir, base_name, original_extension,
                             relative_path, sentence_counter)
        if result == 'start_missing':
            skipped_sentences_start_missing += 1
        elif result == 'end_missing':
            skipped_sentences_end_missing += 1
        elif isinstance(result, str) and not is_short:
            errors.append(result)
        sentence_counter += 1

    stats = f"Fájl: '{base_name}'\n" \
            f"Kihagyott mondatok hiányzó 'start' kulcs miatt: {skipped_sentences_start_missing}\n" \
            f"Kihagyott mondatok hiányzó 'end' kulcs miatt: {skipped_sentences_end_missing}"

    if errors:
        return f"{stats}\nHibák:\n" + "\n".join(errors)
    else:
        return f"{stats}\nFeldolgozás sikeresen befejezve."

def process_sentence(audio, sentence_words, sentence_start_time,
                     output_dir, base_name, original_extension,
                     relative_path, sentence_counter):
    # Ellenőrizzük a 'start' és 'end' kulcsokat
    if sentence_words[0].get('start') is None:
        return 'start_missing', False
    if sentence_words[-1].get('end') is None:
        return 'end_missing', False

    sentence_text = ' '.join(w.get('word', '').strip() for w in sentence_words)
    sentence_text = re.sub(r'\s([,.!?])', r'\1', sentence_text)

    original_start_ms = int(sentence_words[0]['start'] * 1000)
    original_end_ms = int(sentence_words[-1]['end'] * 1000)

    # Vágási pontok pontos meghatározása az első szó 'start' és az utolsó szó 'end' címkéje alapján
    new_start_ms = original_start_ms  # Pontosan az első szó kezdeténél vágunk
    new_end_ms = min(original_end_ms, len(audio))   # Pontosan az utolsó szó végénél vágunk

    if new_start_ms >= new_end_ms:
        return f"Nem érvényes vágási pontok a '{base_name}' fájl '{sentence_counter}'. mondatánál.", False

    # Mappastruktúra létrehozása a relatív útvonal alapján
    output_subdir = os.path.join(output_dir, os.path.dirname(relative_path))

    os.makedirs(output_subdir, exist_ok=True)

    audio_segment = audio[new_start_ms:new_end_ms]

    if len(audio_segment) < 500:
        # A rövid szakaszt nem mentjük, jelezzük, hogy rövid
        return None, True  # A None jelzi, hogy nincs hiba, a True pedig, hogy rövid a szakasz

    output_audio_path = os.path.join(output_subdir, f"{base_name}_sentence_{sentence_counter}.{original_extension}")
    try:
        # Ha az eredeti fájl .m4a volt, akkor 'mp4' formátumban exportáljuk
        if original_extension == 'm4a':
            audio_segment.export(output_audio_path, format='mp4')
        else:
            audio_segment.export(output_audio_path, format=original_extension)
    except Exception as e:
        error_msg = f"Hiba történt az audio szakasz exportálása közben '{output_audio_path}': {e}"
        return error_msg, False

    output_text_path = os.path.join(output_subdir, f"{base_name}_sentence_{sentence_counter}.txt")
    try:
        with open(output_text_path, 'w', encoding='utf-8') as txt_file:
            txt_file.write(sentence_text.strip())
    except Exception as e:
        error_msg = f"Hiba történt a szövegfájl írása közben '{output_text_path}': {e}"
        return error_msg, False

    return None, False  # Nincs hiba, nem rövid a szakasz

def process_directory(input_dir, output_dir):
    json_files = []
    for root, dirs, files in os.walk(input_dir):
        for file in files:
            if file.endswith('.json'):
                json_path = os.path.join(root, file)
                audio_dir = root
                relative_path = os.path.relpath(json_path, input_dir)
                json_files.append((json_path, audio_dir, output_dir, relative_path))

    total_files = len(json_files)
    if total_files == 0:
        print("Nincs feldolgozandó JSON fájl a megadott bemeneti könyvtárban.")
        return

    with ProcessPoolExecutor() as executor:
        future_to_file = {executor.submit(process_json_file, args): args[0] for args in json_files}
        for future in tqdm(as_completed(future_to_file), total=total_files, desc="Feldolgozás"):
            json_path = future_to_file[future]
            try:
                result = future.result()
                if result:
                    print(result)
            except Exception as exc:
                print(f"Hiba történt a '{json_path}' fájl feldolgozása közben: {exc}")

def main():
    parser = argparse.ArgumentParser(
        description="JSON és audio fájlok feldolgozása mondatokra bontáshoz és audio szakaszok kivágásához.",
        epilog="Példa használat:\n  python splitter_v4_json.py --input_dir ./bemenet --output_dir ./kimenet",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--input_dir', '-i',
        type=str,
        required=True,
        help='A bemeneti könyvtár útvonala, ahol a JSON és audio fájlok találhatók.'
    )
    
    parser.add_argument(
        '--output_dir', '-o',
        type=str,
        required=True,
        help='A kimeneti könyvtár útvonala, ahol a feldolgozott audio és szövegfájlok mentésre kerülnek.'
    )
    
    args = parser.parse_args()
    
    os.makedirs(args.output_dir, exist_ok=True)
    
    process_directory(args.input_dir, args.output_dir)

if __name__ == "__main__":
    main()

