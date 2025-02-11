import os
import csv
import librosa
import numpy as np
import argparse
import concurrent.futures
from tqdm import tqdm
import warnings

# (Opcionálisan elnyomhatjuk a UserWarning típusú figyelmeztetéseket)
#warnings.filterwarnings("ignore", category=UserWarning)

def zajszint_szamitas(y, sr):
    """
    Az audio jel frame-ek RMS (Root Mean Square) értékeiből a 10. percentilist számolja,
    majd decibelben (dB) adja vissza – ez becsüli a háttérzaj szintjét.
    """
    rms = librosa.feature.rms(y=y)[0]
    zaj_rms = np.percentile(rms, 10)
    zaj_db = 20 * np.log10(zaj_rms + 1e-6)  # 1e-6 elkerüli a log(0) problémát
    return zaj_db

def process_file(file_path):
    """
    Egy audio file feldolgozása:
      - A file teljes hosszát meghatározza.
      - Ha a file kevesebb mint 1 sec, akkor kihagyja.
      - Ha a file hossza legfeljebb 30 sec, akkor az első (vagy teljes) rész alapján számítja a zajszintet.
      - Hosszabb file-oknál két, 30 másodperces mintát vesz:
            * az első 30 sec-et (offset=0)
            * a file utolsó 30 sec-ét (offset = total_duration - 30)
        És a kettő közül a rosszabb (magasabb dB, azaz több zaj) értéket választja.
    """
    try:
        # A teljes file hosszának meghatározása (a filename paraméter segítségével)
        total_duration = librosa.get_duration(filename=file_path)
        if total_duration < 1:
            print(f"Skip: {file_path} (teljes hossza: {total_duration:.2f} sec)")
            return None

        # Ha a file hossza 30 sec vagy rövidebb, csak egy mintát veszünk (a teljes tartományt vagy az első 30 sec-et)
        if total_duration <= 30:
            y, sr = librosa.load(file_path, sr=None, duration=30, offset=0)
            noise_db = zajszint_szamitas(y, sr)
            sample_info = "(1 minta: 0-30 sec)"
        else:
            # Két minta esetén:
            # 1. mintavétel: az első 30 másodperc (offset=0)
            y1, sr1 = librosa.load(file_path, sr=None, offset=0, duration=30)
            noise_db1 = zajszint_szamitas(y1, sr1)

            # 2. mintavétel: az utolsó 30 másodperc (offset = total_duration - 30)
            offset = total_duration - 30
            y2, sr2 = librosa.load(file_path, sr=None, offset=offset, duration=30)
            noise_db2 = zajszint_szamitas(y2, sr2)

            # A rosszabb érték kiválasztása: mivel magasabb (kevésbé negatív) dB érték több zajt jelez,
            # ezért a maximumot vesszük.
            if noise_db1 >= noise_db2:
                noise_db = noise_db1
                sample_info = f"(2 minta: 0-30 sec és {offset:.2f}-{total_duration:.2f} sec; választott: első)"
            else:
                noise_db = noise_db2
                sample_info = f"(2 minta: 0-30 sec és {offset:.2f}-{total_duration:.2f} sec; választott: második)"

        print(f"Feldolgozva: {file_path}, Zajszint: {noise_db:.2f} dB {sample_info}")
        return (file_path, noise_db)
    except Exception as e:
        print(f"Hiba a(z) {file_path} feldolgozásakor: {e}")
        return None

def get_audio_files(directory):
    """
    Rekurzívan kigyűjti a megadott mappában található audio file-ok teljes elérési útjait.
    Elfogadott kiterjesztések: .wav, .mp3, .flac, .ogg, .m4a
    """
    audio_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.lower().endswith(('.wav', '.mp3', '.flac', '.ogg', '.m4a', '.webm')):
                audio_files.append(os.path.join(root, file))
    return audio_files

def main(directory, csv_output):
    audio_files = get_audio_files(directory)
    if not audio_files:
        print("Nem található audio file a megadott mappában!")
        return

    results = []
    n_jobs = os.cpu_count() or 1
    print(f"Összesen {len(audio_files)} file feldolgozása {n_jobs} párhuzamos szállal...")

    with concurrent.futures.ProcessPoolExecutor(max_workers=n_jobs) as executor:
        futures = {executor.submit(process_file, file_path): file_path for file_path in audio_files}
        for future in tqdm(concurrent.futures.as_completed(futures), total=len(futures), desc="Feldolgozás"):
            res = future.result()
            if res is not None:
                results.append(res)

    # CSV fájlba írás
    with open(csv_output, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["file_path", "noise_level_db"])
        writer.writerows(results)
    print(f"Eredmények elmentve: {csv_output}")

    # Statisztikák kiszámítása és kiírása
    if results:
        num_files = len(results)
        noise_levels = [r[1] for r in results]
        avg_noise = sum(noise_levels) / num_files
        best_noise = min(noise_levels)  # alacsonyabb (inkább negatív) jobb
        worst_noise = max(noise_levels)  # magasabb (kevésbé negatív) rosszabb

        print("\n--- Statisztikák ---")
        print(f"Összes fájl feldolgozva: {num_files}")
        print(f"Átlagos zajszint: {avg_noise:.2f} dB")
        print(f"Legjobb zajszint: {best_noise:.2f} dB")
        print(f"Legrosszabb zajszint: {worst_noise:.2f} dB")

        # A legrosszabb 5 file (a legmagasabb zajszint alapján)
        worst_files = sorted(results, key=lambda x: x[1], reverse=True)[:5]
        print("\nLegrosszabb 5 file:")
        for file_path, noise in worst_files:
            print(f"{file_path}: {noise:.2f} dB")
    else:
        print("Nincs feldolgozott fájl.")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Audio file minőségellenőrzés - Két mintavétel hosszabb file-okból és statisztikák kiírása"
    )
    parser.add_argument("directory", help="Audio fileokat tartalmazó mappa elérési útja")
    parser.add_argument("csv_output", help="Kimeneti CSV file elérési útja")
    args = parser.parse_args()
    main(args.directory, args.csv_output)

