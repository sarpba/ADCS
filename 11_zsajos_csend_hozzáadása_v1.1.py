import argparse
import os
import random
import numpy as np
from pydub import AudioSegment
import shutil
from multiprocessing import Pool, cpu_count
from tqdm import tqdm

def generate_silence(duration_ms, sample_rate, channels):
    """Generál egy hangtalan AudioSegment-et a megadott időtartammal, samplerate-tel és csatornaszámmal."""
    return AudioSegment.silent(duration=duration_ms, frame_rate=sample_rate).set_channels(channels)

def generate_humming(duration_ms, frequency, volume_db, sample_rate, channels):
    """
    Generál egy halk sistergést (zúgást) alacsony frekvenciájú sine hullám segítségével,
    illeszkedve a bemeneti audio fájl samplerate-jéhez és csatornaszámához.

    :param duration_ms: A generált zúgás időtartama milliszekundumban.
    :param frequency: A sine hullám frekvenciája Hertz-ben.
    :param volume_db: A zúgás hangerőssége decibelben.
    :param sample_rate: A bemeneti audio fájl samplerate-je.
    :param channels: A bemeneti audio fájl csatornaszáma.
    :return: AudioSegment objektum a generált zúgással.
    """
    amplitude = 32767 * (10 ** (volume_db / 20))  # PCM amplitude
    t = np.linspace(0, duration_ms / 1000, int(sample_rate * duration_ms / 1000), False)
    sine_wave = amplitude * np.sin(2 * np.pi * frequency * t)
    sine_wave = sine_wave.astype(np.int16)
    
    # Ha a csatornaszám > 1, duplikáljuk a sine hullámot minden csatornára
    if channels > 1:
        sine_wave = np.tile(sine_wave, (channels, 1)).T.flatten()
    
    humming = AudioSegment(
        sine_wave.tobytes(),
        frame_rate=sample_rate,
        sample_width=2,  # int16 -> 2 bytes
        channels=channels
    )
    return humming

def generate_white_noise(duration_ms, volume_db, sample_rate, channels):
    """
    Generál fehér zajt a megadott időtartammal, hangerősséggel, samplerate-tel és csatornaszámmal.

    :param duration_ms: A generált fehér zaj időtartama milliszekundumban.
    :param volume_db: A fehér zaj hangerőssége decibelben.
    :param sample_rate: A bemeneti audio fájl samplerate-je.
    :param channels: A bemeneti audio fájl csatornaszáma.
    :return: AudioSegment objektum a generált fehér zajjal.
    """
    # Generáljunk véletlenszerű zajt [-1, 1] tartományban
    noise = np.random.uniform(low=-1.0, high=1.0, size=int(sample_rate * duration_ms / 1000) * channels)
    # Skálázzuk a zajt a hangerősséghez
    amplitude = 32767 * (10 ** (volume_db / 20))  # PCM amplitude
    noise = (noise * amplitude).astype(np.int16)
    
    # Ha több csatorna van, duplikáljuk a zajt minden csatornára
    if channels > 1:
        noise = noise.reshape(-1, channels).flatten()
    
    white_noise = AudioSegment(
        noise.tobytes(),
        frame_rate=sample_rate,
        sample_width=2,  # int16 -> 2 bytes
        channels=channels
    )
    return white_noise

def add_noise_segments(args):
    """
    Hozzáad háttérzaj szegmenseket véletlenszerű hosszúsággal (0-max_duration_ms) az audio fájl elejéhez és végéhez.
    A zaj szegmensek sima csenddel, halk zúgással vagy fehér zajjal kerülnek létrehozásra,
    illeszkedve a bemeneti audio fájlok tulajdonságaihoz.

    Emellett másolja az azonos nevű JSON fájlokat az audio fájlok mellé.

    :param args: Tuple containing all necessary arguments.
    """
    (input_path, output_path, json_output_path, min_silence_len, silence_thresh_adjust,
     max_noise_duration_ms, noise_volume_db, noise_type) = args
    
    # Ellenőrizzük, hogy a kimeneti fájl már létezik-e
    if os.path.exists(output_path):
        return f"Skipped (exists): {output_path}"
    
    try:
        # Audio fájl betöltése
        original_audio = AudioSegment.from_file(input_path)
    except Exception as e:
        return f"Error loading {input_path}: {e}"
    
    # Bemeneti audio tulajdonságok
    sample_rate = original_audio.frame_rate
    channels = original_audio.channels

    # Véletlenszerű hosszúságok generálása (0-max_noise_duration_ms) az elejére és végére
    start_noise_duration = random.uniform(0, max_noise_duration_ms)  # ms
    end_noise_duration = random.uniform(0, max_noise_duration_ms)    # ms
    
    # Zajszegmens létrehozása a választott típus szerint
    if noise_type == 'silence':
        start_noise = generate_silence(start_noise_duration, sample_rate, channels)
        end_noise = generate_silence(end_noise_duration, sample_rate, channels)
    elif noise_type == 'humming':
        start_noise = generate_humming(start_noise_duration, frequency=100, volume_db=noise_volume_db, sample_rate=sample_rate, channels=channels)
        end_noise = generate_humming(end_noise_duration, frequency=100, volume_db=noise_volume_db, sample_rate=sample_rate, channels=channels)
    elif noise_type == 'white_noise':
        start_noise = generate_white_noise(start_noise_duration, volume_db=noise_volume_db, sample_rate=sample_rate, channels=channels)
        end_noise = generate_white_noise(end_noise_duration, volume_db=noise_volume_db, sample_rate=sample_rate, channels=channels)
    else:
        # Alapértelmezés szerint sima csend
        start_noise = generate_silence(start_noise_duration, sample_rate, channels)
        end_noise = generate_silence(end_noise_duration, sample_rate, channels)
    
    # Zajszegmensek hangerősségének csökkentése, ha szükséges
    if noise_type in ['humming', 'white_noise']:
        start_noise = start_noise - 5  # További hangerőcsökkentés 5 dB-rel
        end_noise = end_noise - 5
    
    # Összefűzés: kezdő zaj + eredeti audio + végső zaj
    final_audio = start_noise + original_audio + end_noise
    
    # Módosított audio mentése ugyanabban a formátumban, mint a bemeneti fájl
    try:
        # Meghatározzuk a formátumot a kimeneti fájl kiterjesztéséből
        export_format = os.path.splitext(output_path)[1][1:].lower()
        # Ha a bemeneti fájl többcsatornás, beállítjuk a kimeneti audio csatornáit is
        final_audio = final_audio.set_frame_rate(sample_rate).set_channels(channels)
        final_audio.export(output_path, format=export_format)
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
    parser.add_argument('--min_silence_len', type=int, default=300, help='A csendes szakasz minimális hossza milliszekundumban (alapértelmezett: 300).')
    parser.add_argument('--silence_thresh_adjust', type=int, default=-16, help='Csendes küszöbérték beállítása az átlagos dBFS-hez képest (alapértelmezett: -16).')
    parser.add_argument('--max_noise_duration_ms', type=int, default=1200, help='A hozzáadott zaj szegmensek maximális hossza milliszekundumban (alapértelmezett: 1200).')
    parser.add_argument('--noise_volume_db', type=int, default=-60, help='Hangerő csökkentése decibelben a generált zajnál (alapértelmezett: -60).')
    parser.add_argument('--file_extension', type=str, default='.mp3', help='A feldolgozandó fájlok kiterjesztése (alapértelmezett: .mp3).')
    parser.add_argument('--noise_type', type=str, choices=['silence', 'humming', 'white_noise'], default='white_noise', help='A hozzáadott zaj típusának kiválasztása: "silence", "humming" vagy "white_noise" (alapértelmezett: "white_noise").')
    
    args = parser.parse_args()
    
    input_directory = args.input_directory
    output_directory = args.output_directory
    min_silence_len = args.min_silence_len
    silence_thresh_adjust = args.silence_thresh_adjust
    max_noise_duration_ms = args.max_noise_duration_ms
    noise_volume_db = args.noise_volume_db
    file_extension = args.file_extension.lower()
    noise_type = args.noise_type
    
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
            max_noise_duration_ms,
            noise_volume_db,
            noise_type
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

