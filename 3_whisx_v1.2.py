import os
import argparse
import subprocess
import time
import datetime  # Időbélyegekhez szükséges
from multiprocessing import Process, Queue

# Maximális próbálkozások száma egy fájl feldolgozására
MAX_RETRIES = 3
# Timeout idő másodpercben
TIMEOUT = 600  # 10 perc

# Ez a függvény visszaadja az audio fájl hosszát másodpercben.
def get_audio_duration(audio_file):
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
        print(f"Nem sikerült meghatározni az audio hosszát {audio_file} esetében: {e}")
        return 0

# Ez a függvény kezeli az egyes GPU-khoz rendelt folyamatokat.
def worker(gpu_id, task_queue):
    while True:
        try:
            # Megpróbálunk egy új audio fájlt kivenni a feladatlistából.
            task = task_queue.get_nowait()
            audio_file, retries = task
        except Exception:
            # Ha a feladatlista üres, kilépünk a ciklusból.
            break

        # A kimeneti JSON fájl elérési útjának meghatározása.
        json_file = os.path.splitext(audio_file)[0] + ".json"

        # Biztonsági ellenőrzés, bár elvileg már nem lehet ilyen fájl.
        if os.path.exists(json_file):
            print(f"Már létezik: {json_file}, átugrás a workerben...")
            continue

        # Az audio fájl könyvtárát használjuk az output könyvtárnak.
        output_dir = os.path.dirname(audio_file)

        # A WhisperX parancs összeállítása a megfelelő paraméterekkel.
        command = [
            "whisperx",
            audio_file,
            "--model", "large-v3",
            "--output_format", "json",
            "--language", "hu",
            "--task", "transcribe",
            "--beam_size", "5",
            "--fp16", "False",
            "--verbose", "True",
            "--device", "cuda",
            "--device_index", str(gpu_id),
            # "--batch_size", "12",
            "--output_dir", output_dir
        ]

        try:
            print(f"GPU-{gpu_id} feldolgozás alatt: {audio_file}")
            # Feldolgozás időmérésének kezdete
            start_time = time.time()
            start_datetime = datetime.datetime.now()

            # A parancs futtatása és a kimenet kezelése időkorláttal.
            result = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=TIMEOUT)

            # Feldolgozás időmérésének vége
            end_time = time.time()
            end_datetime = datetime.datetime.now()
            processing_time = end_time - start_time

            # Az audio hosszának meghatározása
            audio_duration = get_audio_duration(audio_file)
            # Arányszám kiszámítása
            ratio = audio_duration / processing_time if processing_time > 0 else 0

            # Kiírás a kért formátumban
            print(f"Sikeres feldolgozás GPU-{gpu_id}-n:")
            print(f"Feldolgozott file: {audio_file},")
            print(f"Audio hossza: {audio_duration:.2f} s,")
            print(f"Feldolgozási idő: {processing_time:.2f} s,")
            print(f"Arány: {ratio:.2f}")
            print(f"Kezdés ideje: {start_datetime.strftime('%Y.%m.%d %H:%M')}")
            print(f"Befejezés ideje: {end_datetime.strftime('%Y.%m.%d %H:%M')}\n")
        except subprocess.TimeoutExpired:
            print(f"Timeout: {audio_file} feldolgozása GPU-{gpu_id}-n túllépte a {TIMEOUT} másodperces időkorlátot.")
            if retries < MAX_RETRIES:
                print(f"Újrapróbálkozás {retries + 1}/{MAX_RETRIES}...")
                task_queue.put((audio_file, retries + 1))
            else:
                print(f"Maximális próbálkozások elérve: {audio_file} feldolgozása sikertelen.\n")
        except subprocess.CalledProcessError as e:
            print(f"Hiba történt {audio_file} feldolgozása során GPU-{gpu_id}-n: {e.stderr.decode()}")
            if retries < MAX_RETRIES:
                print(f"Újrapróbálkozás {retries + 1}/{MAX_RETRIES}...")
                task_queue.put((audio_file, retries + 1))
            else:
                print(f"Maximális próbálkozások elérve: {audio_file} feldolgozása sikertelen.\n")

# Ez a függvény összegyűjti az összes audio fájlt a megadott könyvtárban és alkönyvtáraiban.
def get_audio_files(directory):
    # Az audio fájlok támogatott kiterjesztései.
    audio_extensions = (".mp3", ".wav", ".flac", ".m4a", ".opus")
    audio_files = []

    # Végigjárjuk a könyvtárakat és alkönyvtárakat.
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.lower().endswith(audio_extensions):
                audio_files.append(os.path.join(root, file))

    return audio_files

# Ez a függvény elindítja a GPU-khoz rendelt folyamatokat és kezeli a feladatlistát.
def transcribe_directory(directory):
    # Az összes audio fájl összegyűjtése.
    audio_files = get_audio_files(directory)

    # Feladatlista létrehozása, tartalmazza a próbálkozások számát is.
    task_queue = Queue()

    # Csak azok az audio fájlok kerülnek a feladatlistába, amelyeknek nincs JSON párjuk.
    tasks_added = 0
    for audio_file in audio_files:
        json_file = os.path.splitext(audio_file)[0] + ".json"
        if not os.path.exists(json_file):
            task_queue.put((audio_file, 0))  # (fájl, próbálkozások száma)
            tasks_added += 1
        else:
            print(f"Már létezik: {json_file}, átugrás a feladatlistában...")

    # Ha nincs feldolgozandó fájl, értesítjük a felhasználót és kilépünk.
    if tasks_added == 0:
        print("Nincs feldolgozandó fájl.")
        return

    # A rendelkezésre álló GPU-k listája.
    gpu_ids = [0, 1]  # Ezt módosíthatod a rendszerednek megfelelően.

    # Folyamatok listája.
    processes = []

    # Minden GPU-hoz létrehozunk egy folyamatot.
    for gpu_id in gpu_ids:
        p = Process(target=worker, args=(gpu_id, task_queue))
        processes.append(p)
        p.start()

    # Várakozás, amíg az összes folyamat be nem fejeződik.
    for p in processes:
        p.join()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Transcribe audio files in a directory and its subdirectories using WhisperX with multiple GPUs.")
    parser.add_argument("directory", type=str, help="A könyvtár, amely tartalmazza az audio fájlokat.")

    args = parser.parse_args()

    if not os.path.isdir(args.directory):
        print(f"Hiba: A megadott könyvtár nem létezik: {args.directory}")
    else:
        transcribe_directory(args.directory)

