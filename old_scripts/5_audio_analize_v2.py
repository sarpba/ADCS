import os
import tensorflow as tf
import tensorflow_hub as hub
import numpy as np
from pydub import AudioSegment
import csv
import urllib.request
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

# YAMNet betöltése
print("YAMNet modell betöltése...")
model = hub.load('https://tfhub.dev/google/yamnet/1')
print("YAMNet modell betöltve.")

# AudioSet osztályok betöltése
class_map_url = 'https://raw.githubusercontent.com/tensorflow/models/master/research/audioset/yamnet/yamnet_class_map.csv'

class_map = {}
try:
    print("class_map.csv letöltése...")
    with urllib.request.urlopen(class_map_url) as f:
        reader = csv.reader(line.decode('utf-8') for line in f)
        next(reader)  # Fejléc átugrása, ha van
        for row in reader:
            if len(row) >= 3:
                index = row[0]
                display_name = row[2]
                class_map[index] = display_name
    print("class_map.csv sikeresen betöltve.")
except Exception as e:
    print(f"Hiba a class_map.csv letöltésekor vagy feldolgozásakor: {e}")
    exit(1)

def analyze_and_save(file_path):
    """
    Elemzi az MP3 fájlt YAMNet segítségével és elmenti az eredményt JSON fájlba.
    """
    try:
        # MP3 konvertálása WAV formátumba
        audio = AudioSegment.from_mp3(file_path)
        audio = audio.set_channels(1).set_frame_rate(16000)
        wav_data = np.array(audio.get_array_of_samples()).astype(np.float32) / 32768.0
    except Exception as e:
        return (file_path, False, f"Hiba az MP3 konvertálásakor: {e}")

    try:
        # YAMNet elemzés
        scores, embeddings, spectrogram = model(wav_data)
        scores = scores.numpy()
        mean_scores = np.mean(scores, axis=0)
        top5_indices = mean_scores.argsort()[-5:][::-1]
        top5_classes = []
        for idx in top5_indices:
            class_id = str(idx)
            label = class_map.get(class_id, "Ismeretlen")
            score = float(mean_scores[idx])  # JSON serializálható típus
            top5_classes.append({"label": label, "score": score})
    except Exception as e:
        return (file_path, False, f"Hiba az elemzés során: {e}")

    try:
        # Fájlnév módosítása: kiterjesztés nélkül + '.json'
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        json_file = os.path.join(os.path.dirname(file_path), f"{base_name}.json")

        # JSON struktúra létrehozása
        output_data = {
            "file": os.path.basename(file_path),
            "analysis": top5_classes
        }

        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=4)

        return (file_path, True, f"Eredmény mentve: {json_file}")
    except Exception as e:
        return (file_path, False, f"Hiba a JSON fájl mentésekor: {e}")

def get_all_mp3_files(directory):
    """
    Gyűjti össze az összes MP3 fájlt a megadott könyvtárban és alkönyvtáraiban, amelyhez még nem létezik JSON fájl.
    """
    mp3_files = []
    skipped_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.lower().endswith('.mp3'):
                base_name = os.path.splitext(file)[0]
                json_file = os.path.join(root, f"{base_name}.json")
                if not os.path.exists(json_file):
                    mp3_files.append(os.path.join(root, file))
                else:
                    skipped_files.append(os.path.join(root, file))
    total_files = len(mp3_files) + len(skipped_files)
    print(f"Összes MP3 fájl megtalálva: {total_files}")
    print(f"Feldolgozásra váró MP3 fájlok: {len(mp3_files)}")
    print(f"Átugrott fájlok (JSON már létezik): {len(skipped_files)}")
    return mp3_files

def process_directory(directory, max_workers=4):
    """
    Feldolgozza a megadott könyvtárban található MP3 fájlokat többszálú feldolgozással és folyamatkijelzéssel.
    """
    mp3_files = get_all_mp3_files(directory)
    total_files = len(mp3_files)
    if total_files == 0:
        print("Nincsenek MP3 fájlok feldolgozásra a megadott könyvtárban.")
        return

    print(f"Feldolgozás elkezdődött {total_files} fájl számára.")

    # ThreadPoolExecutor létrehozása
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Futures létrehozása
        futures = {executor.submit(analyze_and_save, file_path): file_path for file_path in mp3_files}

        # Tqdm progress bar beállítása
        with tqdm(total=total_files, desc="Feldolgozás", unit="fájl") as pbar:
            for future in as_completed(futures):
                file_path = futures[future]
                try:
                    result_file, success, message = future.result()
                    if not success:
                        print(f"\n{result_file}: {message}")
                except Exception as e:
                    print(f"\n{file_path}: Kivétel történt: {e}")
                finally:
                    pbar.update(1)

    print("Feldolgozás befejezve.")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="YAMNet MP3 elemzés JSON kimenettel több szálon, meglévő JSON-ok átugrásával")
    parser.add_argument('directory', type=str, help='Az elemzendő könyvtár elérési útja')
    parser.add_argument('--workers', type=int, default=12, help='A használni kívánt szálak száma (alapértelmezett: 12)')
    args = parser.parse_args()

    process_directory(args.directory, max_workers=args.workers)

