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
    Egyszerű, "visszadobós" megoldás egy truncált Gauss-érték (float) sorsolására.
    Addig sorsol random.gauss(mean, std)-t, amíg az [lower, upper] intervallumba nem esik.
    """
    while True:
        val = random.gauss(mean, std)
        if lower <= val <= upper:
            return val

def build_sentences(word_segments):
    """
    A 'word_segments' listát felbontja mondatszerű egységekre a mondatzáró
    írásjelek és a következő szó nagybetűs kezdése alapján.
    Visszatér egy listával, melyben minden elem:
        {
            'start': (ms),
            'end': (ms),
            'text': (str),
            'words': (eredeti word lista)
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
            # Ha nincs start vagy end, átugorjuk ezt a szót
            continue
        
        # Ha új mondatot kezdünk, eltároljuk a kezdési időt
        if new_sentence:
            sentence_start_time = int(start_t * 1000)
            new_sentence = False
        
        current_words.append(w)
        
        # Ellenőrizzük, hogy van-e mondatzáró írásjel (., !, ?)
        sentence_boundary = False
        if re.search(r'[.!?]$', word_text.strip()):
            sentence_boundary = True
        
        # Nézzük a következő szót, ha van
        if idx < len(word_segments) - 1:
            next_word = word_segments[idx + 1].get('word', '')
            # Ha az előző végén mondatzáró jel van, és a következő nagybetűvel indul
            if sentence_boundary and next_word and next_word[0].isupper():
                sentence_boundary = True
        else:
            # Utolsó szó esetén mindenképp mondatvége
            sentence_boundary = True
        
        if sentence_boundary:
            # Mondat vége
            sentence_end_time = int(end_t * 1000)
            text = ' '.join(word['word'].strip() for word in current_words)
            text = re.sub(r'\s+([,.!?])', r'\1', text)  # Space-ek eltüntetése írásjelek előtt
            sentences.append({
                'start': sentence_start_time,
                'end': sentence_end_time,
                'text': text.strip(),
                'words': current_words
            })
            # Új mondat kezdődik
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
    A mondatok listáját véletlenszerű darabokra bontja.
    - Ha use_uniform=False (alapértelmezés), a chunk célhosszát Gauss-eloszlásból (mean=mean_sec, std=std_sec) sorsoljuk,
      a [min_sec, max_sec] tartományban "visszadobós" truncált módon.
    - Ha use_uniform=True, a chunk célhosszát random.uniform(min_sec, max_sec) értékből kapjuk.

    A chunk létrehozásánál sosem lépjük túl a max_sec-et, és próbáljuk elérni/legalább
    a min_sec-et is.
    """
    chunks = []
    i = 0
    n = len(sentences)

    while i < n:
        if use_uniform:
            # Egyenletes (uniform) eloszlás
            target = random.uniform(min_sec, max_sec)
        else:
            # Gauss (normál) eloszlás
            target = truncated_gauss(mean_sec, std_sec, min_sec, max_sec)
        
        chunk_start = sentences[i]['start']
        chunk_end = chunk_start
        chunk_texts = []
        
        while i < n:
            sent_start = sentences[i]['start']
            sent_end = sentences[i]['end']
            sent_text = sentences[i]['text']
            
            # Ha ez az első mondat a chunkban
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
                    # Túlcsúszna a max_sec-en, lezárjuk a chunkot
                    break
            
            current_dur = (chunk_end - chunk_start) / 1000.0
            # Ha elérjük/meghaladjuk a targetet, és már legalább min_sec hosszú,
            # lezárhatjuk a chunk-ot
            if current_dur >= target and current_dur >= min_sec:
                break

        # Ha a chunk még mindig kisebb, mint min_sec, próbáljuk növelni,
        # amíg van még mondat és nem lépjük túl a max_sec-et.
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
    Kivágja a 'chunk' által megadott időintervallumot (ms-ben)
    az audio-ból, és kimenti a megfelelő formátumban (eredeti vagy mp4),
    majd a szöveget is txt fájlba.
    """
    new_start_ms = chunk['start']
    new_end_ms = min(chunk['end'], len(audio))

    if new_start_ms >= new_end_ms:
        return f"Érvénytelen vágási pontok: start={new_start_ms}, end={new_end_ms}", False

    # Kivágás
    audio_segment = audio[new_start_ms:new_end_ms]
    duration_ms = len(audio_segment)

    # Ha a hang nagyon rövid, nem érdemes menteni
    if duration_ms < 200:  # 0.2s alatt
        return None, True  # True jelzi, hogy túl rövid
    
    output_audio_path = os.path.join(output_dir, f"{base_name}_chunk_{chunk_index}.{original_extension}")
    try:
        # Ha az eredeti fájl .m4a volt, akkor 'mp4' formátumban exportáljuk
        if original_extension == 'm4a':
            audio_segment.export(output_audio_path, format='mp4')
        elif original_extension == 'opus':
            # Dönthetünk, hogy ogg-ként vagy opus-ként mentjük; itt opus marad:
            audio_segment.export(output_audio_path, format='opus')
        else:
            audio_segment.export(output_audio_path, format=original_extension)
    except Exception as e:
        return f"Hang exportálási hiba: '{output_audio_path}': {e}", False

    # Szöveg mentése
    output_text_path = os.path.join(output_dir, f"{base_name}_chunk_{chunk_index}.txt")
    try:
        with open(output_text_path, 'w', encoding='utf-8') as txt_file:
            txt_file.write(chunk['text'].strip() + "\n")
    except Exception as e:
        return f"Szövegfájl írási hiba: '{output_text_path}': {e}", False

    return None, False


def process_json_file(args):
    """
    Egy JSON állomány (és a hozzá tartozó audio) feldolgozása.
    Visszaad egy összefoglaló stringet (hibaüzenettel vagy sikerrel).
    """
    (json_path,
     audio_dir,
     output_dir,
     relative_path,
     min_sec,
     max_sec,
     mean_sec,
     std_sec,
     use_uniform) = args
    
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
        return f"Audio fájl nem található: '{base_name}' (JSON: '{json_path}')."

    # Audio betöltése
    try:
        if original_extension == 'opus':
            # Az .opus fájlt 'ogg'-ként olvassuk be
            audio = AudioSegment.from_file(audio_file, format='ogg')
        elif original_extension == 'm4a':
            # Az .m4a fájlt 'mp4'-ként olvassuk be
            audio = AudioSegment.from_file(audio_file, format='mp4')
        else:
            audio = AudioSegment.from_file(audio_file, format=original_extension)
    except Exception as e:
        return f"Hiba az audio fájl betöltésekor '{audio_file}': {e}"

    # JSON betöltése
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        return f"Hiba a JSON fájl betöltésekor '{json_path}': {e}"

    # Ellenőrzés
    if 'word_segments' not in data:
        return f"A '{json_path}' fájl nem tartalmaz 'word_segments' mezőt."

    word_segments = data['word_segments']
    if not word_segments:
        return f"A '{json_path}' word_segments listája üres."

    # 1) Mondatok létrehozása
    sentences = build_sentences(word_segments)

    # 2) Véletlenszerű darabolás (Gauss v. Uniform) – lásd kapcsoló
    final_chunks = chunk_sentences_random(
        sentences,
        min_sec=min_sec,
        max_sec=max_sec,
        mean_sec=mean_sec,
        std_sec=std_sec,
        use_uniform=use_uniform
    )

    # Kimeneti mappa létrehozása
    output_subdir = os.path.join(output_dir, os.path.dirname(relative_path))
    os.makedirs(output_subdir, exist_ok=True)

    # 3) Chunkok exportálása
    errors = []
    too_short_skipped = 0
    for i, chunk in enumerate(final_chunks):
        result, is_short = export_chunk_audio_and_text(
            audio, chunk, output_subdir, base_name, original_extension, i
        )
        if result:  # Hibát jelent
            errors.append(result)
        if is_short:
            too_short_skipped += 1

    # Statisztika
    stats = (
        f"Fájl: '{base_name}'\n"
        f"Összesen létrehozott chunkok száma: {len(final_chunks)}\n"
        f"Kihagyott túl rövid chunkok: {too_short_skipped}"
    )

    if errors:
        return f"{stats}\nHibák:\n" + "\n".join(errors)
    else:
        return f"{stats}\nFeldolgozás sikeresen befejezve."

def process_directory(input_dir, output_dir,
                      min_sec, max_sec, mean_sec, std_sec,
                      use_uniform, num_workers):
    """
    Végigmegy az input_dir-en, kikeresi az összes .json-t, és feldolgozza azokat.
    """
    json_files = []
    for root, dirs, files in os.walk(input_dir):
        for file in files:
            if file.endswith('.json'):
                json_path = os.path.join(root, file)
                audio_dir = root
                relative_path = os.path.relpath(json_path, input_dir)
                # Paramétereket is átadjuk a process_json_file-hez
                args = (json_path, 
                        audio_dir, 
                        output_dir, 
                        relative_path,
                        min_sec, 
                        max_sec, 
                        mean_sec, 
                        std_sec,
                        use_uniform)
                json_files.append(args)

    total_files = len(json_files)
    if total_files == 0:
        print("Nincs feldolgozandó JSON fájl a megadott bemeneti könyvtárban.")
        return

    # Párhuzamos feldolgozás
    with ProcessPoolExecutor(max_workers=num_workers) as executor:
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
        description="JSON és audio fájlok véletlenszerű darabolása 1–30s között (alapértelmezésben 15±5 Gauss). "
                    "A --uniform_dist kapcsolóval egyenletes (uniform) eloszlás is választható.",
        epilog="""
Példa:
  python splitter_gauss.py \\
    --input_dir ./bemenet \\
    --output_dir ./kimenet \\
    --min_sec 5 --max_sec 30 --mean_sec 15 --std_sec 5 \\
    --num_workers 4
  # Ha uniform eloszlást akarunk,:
  python splitter_gauss.py \\
    --input_dir ./bemenet \\
    --output_dir ./kimenet \\
    --min_sec 1 --max_sec 30 \\
    --uniform_dist
        """,
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
        help='A kimeneti könyvtár útvonala, ahová a feldolgozott audio és szövegfájlok mentésre kerülnek.'
    )
    
    parser.add_argument(
        '--min_sec',
        type=float,
        default=1.0,
        help='A keletkező chunkok minimális hossza (másodpercben). Alapértelmezés: 1.'
    )

    parser.add_argument(
        '--max_sec',
        type=float,
        default=30.0,
        help='A keletkező chunkok maximális hossza (másodpercben). Alapértelmezés: 30.'
    )

    parser.add_argument(
        '--mean_sec',
        type=float,
        default=15.0,
        help='A Gauss-eloszlás középértéke a chunkok kívánt hossza számára. Alapértelmezés: 15. '
             '(Ez csak akkor számít, ha nincs --uniform_dist.)'
    )

    parser.add_argument(
        '--std_sec',
        type=float,
        default=5.0,
        help='A Gauss-eloszlás szórása a chunkok kívánt hossza számára. Alapértelmezés: 5. '
             '(Ez csak akkor számít, ha nincs --uniform_dist.)'
    )

    parser.add_argument(
        '--uniform_dist',
        action='store_true',
        default=False,
        help='Ha megadjuk, akkor Gauss helyett egyenletes (uniform) eloszlást használunk, '
             'azaz random.uniform(min_sec, max_sec) alapján választjuk a chunk célhosszát.'
    )

    parser.add_argument(
        '--num_workers',
        type=int,
        default=(os.cpu_count() or 1),
        help='Párhuzamos folyamatok (process) száma. Alapértelmezés: a gép CPU magjainak száma.'
    )
    
    args = parser.parse_args()
    
    # Kimeneti könyvtár létrehozása, ha nem létezik
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Tetszőleges seed beállítható (opcionális)
    # random.seed(42)
    
    process_directory(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        min_sec=args.min_sec,
        max_sec=args.max_sec,
        mean_sec=args.mean_sec,
        std_sec=args.std_sec,
        use_uniform=args.uniform_dist,
        num_workers=args.num_workers
    )

if __name__ == "__main__":
    main()

