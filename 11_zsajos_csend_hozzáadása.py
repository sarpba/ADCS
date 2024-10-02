import argparse
import os
import random
import numpy as np
from pydub import AudioSegment
from pydub.silence import detect_silence
import shutil
from multiprocessing import Pool, cpu_count
from tqdm import tqdm

def add_noise_segments(args):
    """
    Hozzáad háttérzaj szegmenseket véletlenszerű hosszúsággal (0-1 sec) az audio fájl elejéhez és végéhez.
    A zaj a fájl csendes részeiből kerül kiválasztásra, majd további hangerőcsökkentést alkalmaz.
    
    Emellett másolja az azonos nevű JSON fájlokat az audio fájlok mellé.
    
    :param args: Tuple containing all necessary arguments.
    """
    (input_path, output_path, json_output_path, min_silence_len, silence_thresh_adjust,
     noise_sample_min_duration, volume_reduction_db, additional_reduction_db) = args
    
    # Ellenőrizzük, hogy a kimeneti fájl már létezik-e
    if os.path.exists(output_path):
        return f"Skipped (exists): {output_path}"
    
    try:
        # Audio fájl betöltése
        original_audio = AudioSegment.from_file(input_path)
    except Exception as e:
        return f"Error loading {input_path}: {e}"
    
    # Véletlenszerű hosszúságok generálása (0-1000 ms) az elejére és végére
    start_noise_duration = random.uniform(0, 1000)  # ms
    end_noise_duration = random.uniform(0, 1000)    # ms
    
    # Csendes szakaszok detektálása
    silence_threshold = original_audio.dBFS + silence_thresh_adjust
    silent_ranges = detect_silence(
        original_audio,
        min_silence_len=min_silence_len,
        silence_thresh=silence_threshold
    )
    
    if silent_ranges:
        # Véletlenszerű csendes szakasz kiválasztása
        start_idx, end_idx = random.choice(silent_ranges)
        noise_sample = original_audio[start_idx:end_idx]
        # Ha a zajminta túl rövid, ismételjük meg, hogy elérjük a minimális hosszt
        if len(noise_sample) < noise_sample_min_duration:
            loops = int(np.ceil(noise_sample_min_duration / len(noise_sample)))
            noise_sample = noise_sample * loops
            noise_sample = noise_sample[:noise_sample_min_duration]
    else:
        # Ha nincs csendes szakasz, használjunk egy alacsony hangerővel rendelkező részt
        noise_sample = original_audio[:noise_sample_min_duration]
        noise_sample = noise_sample - volume_reduction_db
    
    # Zajszegmens létrehozása adott hosszúsággal
    def create_noise_segment(duration_ms):
        loops = int(np.ceil(duration_ms / len(noise_sample)))
        noise_segment = noise_sample * loops
        noise_segment = noise_segment[:int(duration_ms)]
        return noise_segment
    
    # Zajszegmensek létrehozása az elejére és végére, további hangerőcsökkentéssel
    start_noise = create_noise_segment(start_noise_duration) - additional_reduction_db
    end_noise = create_noise_segment(end_noise_duration) - additional_reduction_db
    
    # Összefűzés: kezdő zaj + eredeti audio + végső zaj
    final_audio = start_noise + original_audio + end_noise
    
    # Módosított audio mentése
    try:
        final_audio.export(output_path, format=os.path.splitext(output_path)[1][1:].lower())
    except Exception as e:
        return f"Error exporting {output_path}: {e}"
    
    # JSON fájl másolása, ha létezik
    json_input_path = os.path.splitext(input_path)[0] + '.json'
    if os.path.exists(json_input_path):
        try:
            shutil.copy(json_input_path, json_output_path)
        except Exception as e:
            return f"Error copying JSON for {input_path}: {e}"
    
    return f"Processed: {output_path}"

def gather_audio_files(input_directory, output_directory, file_extension):
    """
    Gyűjti össze az összes feldolgozandó audio fájl elérési útját.
    
    :param input_directory: Bemeneti könyvtár elérési útja.
    :param output_directory: Kimeneti könyvtár elérési útja.
    :param file_extension: Feldolgozandó fájlok kiterjesztése.
    :return: Lista tuple-ökből, amik tartalmazzák az input és output fájlok elérési útját, valamint a JSON kimeneti útvonalat.
    """
    tasks = []
    for root, dirs, files in os.walk(input_directory):
        for filename in files:
            if filename.lower().endswith(file_extension):
                input_file = os.path.join(root, filename)
                # Relatív útvonal meghatározása a mappaszerkezet megtartásához
                relative_path = os.path.relpath(root, input_directory)
                output_subdir = os.path.join(output_directory, relative_path)
                os.makedirs(output_subdir, exist_ok=True)
                output_file = os.path.join(output_subdir, filename)
                json_output_file = os.path.splitext(output_file)[0] + '.json'
                tasks.append((
                    input_file,
                    output_file,
                    json_output_file
                ))
    return tasks

def main():
    parser = argparse.ArgumentParser(description="Adj hozzá zajszegmenseket az audió fájlok elejéhez és végéhez, megtartva a mappaszerkezetet.")
    parser.add_argument('input_directory', type=str, help='Bemeneti könyvtár elérési útja, ahol az audió fájlok találhatók.')
    parser.add_argument('output_directory', type=str, help='Kimeneti könyvtár elérési útja, ahol a módosított audió fájlokat menteni szeretnéd.')
    parser.add_argument('--min_silence_len', type=int, default=500, help='A csendes szakasz minimális hossza milliszekundumban (alapértelmezett: 500).')
    parser.add_argument('--silence_thresh_adjust', type=int, default=-16, help='Csendes küszöbérték beállítása az átlagos dBFS-hez képest (alapértelmezett: -16).')
    parser.add_argument('--noise_sample_min_duration', type=int, default=500, help='A zajminta minimális hossza milliszekundumban (alapértelmezett: 500).')
    parser.add_argument('--volume_reduction_db', type=int, default=20, help='Hangerő csökkentése decibelben a zajminta esetén (alapértelmezett: 20).')
    parser.add_argument('--additional_reduction_db', type=int, default=5, help='További hangerő csökkentése decibelben a hozzáadott zajszegmenseknél (alapértelmezett: 5).')
    parser.add_argument('--file_extension', type=str, default='.mp3', help='A feldolgozandó fájlok kiterjesztése (alapértelmezett: .wav).')
    
    args = parser.parse_args()
    
    input_directory = args.input_directory
    output_directory = args.output_directory
    min_silence_len = args.min_silence_len
    silence_thresh_adjust = args.silence_thresh_adjust
    noise_sample_min_duration = args.noise_sample_min_duration
    volume_reduction_db = args.volume_reduction_db
    additional_reduction_db = args.additional_reduction_db
    file_extension = args.file_extension.lower()
    
    # Bemeneti könyvtár ellenőrzése
    if not os.path.isdir(input_directory):
        print(f"Hiba: A bemeneti könyvtár nem található: {input_directory}")
        return
    
    # Kimeneti könyvtár létrehozása, ha nem létezik
    os.makedirs(output_directory, exist_ok=True)
    
    # Minden fájl gyűjtése a feldolgozáshoz
    tasks = gather_audio_files(input_directory, output_directory, file_extension)
    total_files = len(tasks)
    
    if total_files == 0:
        print("Nincs feldolgozandó fájl a megadott könyvtárban.")
        return
    
    # Paraméterek összeállítása a worker függvény számára
    processed_tasks = []
    for task in tasks:
        processed_tasks.append((
            task[0],
            task[1],
            task[2],
            min_silence_len,
            silence_thresh_adjust,
            noise_sample_min_duration,
            volume_reduction_db,
            additional_reduction_db
        ))
    
    # Párhuzamos feldolgozás
    with Pool(processes=cpu_count()) as pool:
        # A tqdm segítségével jelenítjük meg a progress bar-t
        results = list(tqdm(pool.imap_unordered(add_noise_segments, processed_tasks),
                            total=total_files,
                            desc="Processing",
                            unit="files"))
    
    # Eredmények kiírása (opcionális)
    for result in results:
        print(result)

if __name__ == "__main__":
    main()

