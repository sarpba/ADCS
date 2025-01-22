import os
import argparse
import gc
import time
import datetime
import sys
from multiprocessing import Process, Queue, current_process
import subprocess
import json

# Maximális próbálkozások egy fájl feldolgozására
MAX_RETRIES = 3
# Időtúllépés másodpercben (nem implementált a jelenlegi szkriptben)
TIMEOUT = 600  # 10 perc

def get_available_gpus():
    """
    Lekérdezi a rendelkezésre álló GPU indexeket az nvidia-smi segítségével.
    """
    try:
        command = ["nvidia-smi", "--query-gpu=index", "--format=csv,noheader"]
        result = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        gpu_indices = result.stdout.decode().strip().split('\n')
        gpu_ids = [int(idx) for idx in gpu_indices if idx.strip().isdigit()]
        return gpu_ids
    except Exception as e:
        print(f"Hiba a GPU-k lekérdezése során: {e}")
        return []

def get_audio_duration(audio_file):
    """
    Visszaadja az audio fájl hosszát másodpercben.
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
        print(f"Nem sikerült meghatározni az audio hosszát a következő fájlhoz: {audio_file} - {e}")
        return 0

def worker(gpu_id, task_queue):
    """
    A GPU-khoz rendelt folyamatokat kezelő függvény.
    """
    # Beállítjuk a CUDA_VISIBLE_DEVICES környezeti változót, hogy csak az adott GPU látható legyen
    os.environ["CUDA_VISIBLE_DEVICES"] = str(gpu_id)
    device = "cuda"  # 'cuda' mostantól az adott GPU-t jelenti

    model = None  # Inicializáljuk a model változót

    try:
        # Importáljuk a CUDA-t használó könyvtárakat a worker függvényen belül
        import torch
        import whisperx

        print(f"Folyamat {current_process().name} beállítva a GPU-{gpu_id} eszközre.")

        # WhisperX modell betöltése
        print(f"GPU-{gpu_id}: WhisperX modell betöltése...")
        model = whisperx.load_model("large-v3", device=device, compute_type="float16")
        print(f"GPU-{gpu_id}: Modell betöltve.")

        while True:
            try:
                task = task_queue.get_nowait()
            except:
                # Nincs több feladat
                break

            audio_file, retries = task
            json_file = os.path.splitext(audio_file)[0] + ".json"

            if os.path.exists(json_file):
                print(f"Már létezik: {json_file}, kihagyás a feldolgozásból...")
                continue

            try:
                print(f"GPU-{gpu_id} használatával feldolgozás: {audio_file}")
                start_time = time.time()
                start_datetime = datetime.datetime.now()

                # Audio betöltése és átírás
                audio = whisperx.load_audio(audio_file)
                result = model.transcribe(audio, batch_size=16)
                print(f"Átírás befejezve: {audio_file}")

                # Alignálás a transzkripció után
                align_language_code = result["language"]  # Használja a detektált nyelvet
                print(f"GPU-{gpu_id}: Alignálási modell betöltése a következő nyelvhez: {align_language_code}")
                model_a, metadata = whisperx.load_align_model(language_code=align_language_code, device=device)
                result_aligned = whisperx.align(result["segments"], model_a, metadata, audio, device, return_char_alignments=False)
                print(f"Alignálás befejezve: {audio_file}")

                # Eredmények mentése
                with open(json_file, "w", encoding="utf-8") as f:
                    json.dump(result_aligned, f, ensure_ascii=False, indent=4)

                end_time = time.time()
                end_datetime = datetime.datetime.now()
                processing_time = end_time - start_time

                audio_duration = get_audio_duration(audio_file)
                ratio = audio_duration / processing_time if processing_time > 0 else 0

                print(f"Sikeresen feldolgozva GPU-{gpu_id} által:")
                print(f"Feldolgozott fájl: {audio_file},")
                print(f"Audio hossza: {audio_duration:.2f} s,")
                print(f"Feldolgozási idő: {processing_time:.2f} s,")
                print(f"Arány: {ratio:.2f}")
                print(f"Kezdés időpontja: {start_datetime.strftime('%Y.%m.%d %H:%M')}")
                print(f"Befejezés időpontja: {end_datetime.strftime('%Y.%m.%d %H:%M')}\n")

            except Exception as e:
                print(f"Hiba a következő fájl feldolgozása során GPU-{gpu_id}-n: {audio_file} - {e}")
                if retries < MAX_RETRIES:
                    print(f"Újrapróbálkozás {retries + 1}/{MAX_RETRIES}...\n")
                    task_queue.put((audio_file, retries + 1))
                else:
                    print(f"Maximális próbálkozások elérve: {audio_file} feldolgozása sikertelen.\n")

    except Exception as main_e:
        print(f"Fő hiba a GPU-{gpu_id} folyamatban: {main_e}")

    finally:
        # GPU memória felszabadítása a munkafolyamat végén, ha a modell betöltődött
        if model is not None:
            try:
                print(f"GPU-{gpu_id}: GPU memória felszabadítása...")
                del model
                gc.collect()
                torch.cuda.empty_cache()
                print(f"GPU-{gpu_id}: GPU memória felszabadítva.")
            except Exception as cleanup_e:
                print(f"Hiba a GPU-{gpu_id} memória felszabadítása során: {cleanup_e}")
        else:
            print(f"GPU-{gpu_id}: Modell nem lett betöltve, memória felszabadítása nem szükséges.")

def get_audio_files(directory):
    """
    Az adott könyvtárban és almappáiban található összes audio fájl gyűjtése.
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
    Folyamatokat indító és feladatlistát kezelő függvény.
    """
    audio_files = get_audio_files(directory)
    task_queue = Queue()
    tasks_added = 0

    for audio_file in audio_files:
        json_file = os.path.splitext(audio_file)[0] + ".json"
        if not os.path.exists(json_file):
            task_queue.put((audio_file, 0))
            tasks_added += 1
        else:
            print(f"Már létezik: {json_file}, kihagyás a feladatlistában...")

    if tasks_added == 0:
        print("Nincs feldolgozandó fájl.")
        return

    processes = []
    for gpu_id in gpu_ids:
        p = Process(target=worker, args=(gpu_id, task_queue), name=f"GPU-{gpu_id}-Process")
        processes.append(p)
        p.start()
        print(f"Folyamat indítva: {p.name} a GPU-{gpu_id}-n.")

    for p in processes:
        p.join()
        print(f"Folyamat befejezve: {p.name}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Audio fájlok átírása és alignálása egy könyvtárban és almappáiban WhisperX segítségével több GPU-val.")
    parser.add_argument("directory", type=str, help="A könyvtár, amely tartalmazza az audio fájlokat.")
    parser.add_argument('--gpus', type=str, default=None, help="Használni kívánt GPU indexek, vesszővel elválasztva (pl. '0,2,3')")

    args = parser.parse_args()

    if not os.path.isdir(args.directory):
        print(f"Hiba: A megadott könyvtár nem létezik: {args.directory}")
        sys.exit(1)

    # Meghatározza a használni kívánt GPU-kat
    if args.gpus:
        try:
            specified_gpus = [int(x.strip()) for x in args.gpus.split(',')]
        except ValueError:
            print("Hiba: A --gpus argumentumnak egész számok vesszővel elválasztott listájának kell lennie.")
            sys.exit(1)
        available_gpus = get_available_gpus()
        if not available_gpus:
            print("Hiba: Nincsenek elérhető GPU-k.")
            sys.exit(1)
        invalid_gpus = [gpu for gpu in specified_gpus if gpu not in available_gpus]
        if invalid_gpus:
            print(f"Hiba: A megadott GPU-k nem érhetők el: {invalid_gpus}")
            sys.exit(1)
        gpu_ids = specified_gpus
    else:
        gpu_ids = get_available_gpus()
        if not gpu_ids:
            print("Hiba: Nincsenek elérhető GPU-k.")
            sys.exit(1)

    print(f"Használt GPU-k: {gpu_ids}")

    # Átírás és alignálás indítása a meghatározott GPU-kkal
    transcribe_directory(args.directory, gpu_ids)