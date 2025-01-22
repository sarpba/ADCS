#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import argparse
import gc
import time
import datetime
import sys
from multiprocessing import Process, Queue, current_process, Manager
import subprocess
import json
import queue  # a queue.Empty kivételéhez szükséges

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

def worker(gpu_id, task_queue, progress_queue, last_activity):
    """
    A GPU-khoz rendelt folyamatokat kezelő függvény (csak transzkripció, nincs alignálás).
    Jelzés a main folyamatnak progress_queue használatával: minden sikeres fájl-feldolgozásnál
    küldünk egy üzenetet {'status': 'done', 'file': audio_file, 'processing_time': ... }.

    last_activity[gpu_id] = time.time() segítségével jelezzük, hogy a GPU mikor volt utoljára aktív.
    """
    # Beállítjuk a CUDA_VISIBLE_DEVICES környezeti változót, hogy csak az adott GPU látható legyen
    os.environ["CUDA_VISIBLE_DEVICES"] = str(gpu_id)
    device = "cuda"  # 'cuda' mostantól az adott GPU-t jelenti

    model = None  # Inicializáljuk a model változót

    try:
        import torch
        import whisperx

        print(f"Folyamat {current_process().name} beállítva a GPU-{gpu_id} eszközre.")
        print(f"GPU-{gpu_id}: WhisperX modell betöltése...")
        model = whisperx.load_model("large-v3-turbo", device=device, compute_type="float16") #large-v3-turbo
        print(f"GPU-{gpu_id}: Modell betöltve.")

        no_task_count = 0
        max_no_task_tries = 3

        while True:
            try:
                # Rögtön megpróbálunk feladatot kivenni a sorból
                task = task_queue.get_nowait()
                # Ha kaptunk feladatot, frissítjük az utolsó aktivitást
                last_activity[gpu_id] = time.time()
            except queue.Empty:
                # Ha nincs feladat a sorban, várjunk 1 mp-et
                if no_task_count < max_no_task_tries:
                    no_task_count += 1
                    time.sleep(1)
                    continue
                else:
                    # Ha háromszor is üres maradt, kilépünk a worker-ből
                    print(f"GPU-{gpu_id}: Nincs több feladat, 3 próbálkozás után kilépés.")
                    break
            except Exception as e:
                # Ha valami más hiba merült fel a task lekérésekor
                print(f"GPU-{gpu_id}: Hiba a feladat lekérésekor: {e}")
                break

            # Ha feladatot kaptunk, lenullázzuk a számlálót
            no_task_count = 0

            audio_file, retries = task
            json_file = os.path.splitext(audio_file)[0] + ".json"

            # Ha már létezik a json, kihagyjuk
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

                # Munkavégzés után is frissítjük az aktivitást
                last_activity[gpu_id] = time.time()

                # Eredmények mentése JSON-be
                with open(json_file, "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False, indent=4)

                end_time = time.time()
                end_datetime = datetime.datetime.now()
                processing_time = end_time - start_time

                audio_duration = get_audio_duration(audio_file)
                ratio = audio_duration / processing_time if processing_time > 0 else 0

                print(f"Sikeresen feldolgozva GPU-{gpu_id} által:")
                print(f"Feldolgozott fájl: {audio_file}")
                print(f"Audio hossza: {audio_duration:.2f} s")
                print(f"Feldolgozási idő: {processing_time:.2f} s")
                print(f"Arány: {ratio:.2f}")
                print(f"Kezdés időpontja: {start_datetime.strftime('%Y.%m.%d %H:%M')}")
                print(f"Befejezés időpontja: {end_datetime.strftime('%Y.%m.%d %H:%M')}\n")

                # Küldünk egy üzenetet a progress_queue-ba, hogy egy feladat elkészült
                progress_queue.put({
                    "status": "done",
                    "file": audio_file,
                    "processing_time": processing_time
                })

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
        # A worker befejezésekor szabadítjuk fel a GPU memóriát (csak egyszer, a folyamat végén)
        if model is not None:
            try:
                print(f"GPU-{gpu_id}: GPU memória felszabadítása...")
                del model
                gc.collect()
                import torch
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
    Folyamatokat indító és feladatlistát kezelő függvény (csak transzkripció).
    Kiegészítve a feldolgozás előrehaladás jelzésével és a várható befejezési idő számításával
    az eltelt idő (főfolyamat indulásától számítva) alapján.

    Továbbá, ha több GPU van, és bármelyik GPU 10 mp-ig nem kap feladatot,
    minden folyamatot leállít, és újraindítja a scriptet.
    """
    audio_files = get_audio_files(directory)
    task_queue = Queue()
    tasks_added = 0

    # Összes file, amelynek nincs még .json kimenete
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

    print(f"Összesen {tasks_added} fájlt kell feldolgozni.")

    # A progress_queue-t a workers-nek adjuk át, hogy jelezhessék, ha egy feladat elkészült
    manager = Manager()
    progress_queue = manager.Queue()

    # --- Megosztott dict, amelybe a worker-ek írják a GPU-k utolsó aktivitását ---
    last_activity = manager.dict()
    for gpu_id in gpu_ids:
        last_activity[gpu_id] = time.time()  # induláskor az aktuális idő

    # Elindítjuk a worker folyamatokat
    processes = []
    for gpu_id in gpu_ids:
        p = Process(
            target=worker,
            args=(gpu_id, task_queue, progress_queue, last_activity),
            name=f"GPU-{gpu_id}-Process"
        )
        processes.append(p)
        p.start()
        print(f"Folyamat indítva: {p.name} a GPU-{gpu_id}-n.")

    tasks_done = 0
    start_time = time.time()

    # A főfolyamat követi nyomon a kész fájlokat, saccolja a befejezési időt
    # és figyeli, hogy nincs-e inaktív GPU (ha több GPU van).
    while tasks_done < tasks_added:
        try:
            # Várjuk, hogy a worker jelezze a feldolgozás befejezését
            message = progress_queue.get(timeout=1.0)
            if message["status"] == "done":
                tasks_done += 1
                elapsed_time = time.time() - start_time  # eddig eltelt idő

                remaining = tasks_added - tasks_done
                if tasks_done > 0:
                    avg_time_per_file = elapsed_time / tasks_done
                else:
                    avg_time_per_file = 0

                est_remaining_time = avg_time_per_file * remaining
                finish_time_est = datetime.datetime.now() + datetime.timedelta(seconds=est_remaining_time)
                progress_percent = (tasks_done / tasks_added) * 100

                print(
                    f"[{tasks_done}/{tasks_added} - {progress_percent:.1f}%] "
                    f"Kész: {message['file']} | "
                    f"Becsült befejezés: {finish_time_est.strftime('%Y-%m-%d %H:%M:%S')}"
                )

        except:
            # Ha 1 mp-en belül nem érkezett új üzenet, egyszerűen továbbmegyünk
            pass

        # --- Ha több GPU van, figyeljük a 10 mp-es inaktivitást ---
        if len(gpu_ids) > 1:
            now = time.time()
            for g in gpu_ids:
                if (now - last_activity[g]) > 10:
                    print(f"FIGYELEM: A(z) {g} GPU több mint 10 másodperce nem kapott feladatot.")
                    print("Minden folyamat leállítása és a script újraindítása...")
                    # Leállítjuk az összes folyamatot
                    for proc in processes:
                        if proc.is_alive():
                            proc.terminate()

                    # Újraindítjuk a scriptet
                    python = sys.executable
                    os.execl(python, python, *sys.argv)
                    # Az os.execl() hívás innentől nem tér vissza.

    # Végül (ha minden feladat elkészült) várjuk, hogy minden worker folyamat leálljon
    for p in processes:
        p.join()
        print(f"Folyamat befejezve: {p.name}")

    total_time = time.time() - start_time
    print(f"Minden feladat elkészült. Összes feldolgozási idő: {total_time:.2f} mp")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Audio fájlok átírása (WhisperX segítségével) több GPU-val. Alignálás NINCS."
    )
    parser.add_argument("directory", type=str, help="A könyvtár, amely tartalmazza az audio fájlokat.")
    parser.add_argument('--gpus', type=str, default=None,
                        help="Használni kívánt GPU indexek, vesszővel elválasztva (pl. '0,2,3')")

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

    # Átírás indítása a meghatározott GPU-kkal
    transcribe_directory(args.directory, gpu_ids)

