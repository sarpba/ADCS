import argparse
import os
from pydub import AudioSegment
from multiprocessing import Pool, cpu_count
from functools import partial
from tqdm import tqdm

def parse_arguments():
    parser = argparse.ArgumentParser(description='MP3 konvertálása WAV formátumba.')
    parser.add_argument('-i', '--input', required=True, help='Bemeneti könyvtár, ahol az MP3 fájlok találhatók.')
    parser.add_argument('-o', '--output', required=True, help='Kimeneti könyvtár, ahova a WAV fájlok kerülnek.')
    return parser.parse_args()

def convert_mp3_to_wav(input_file, output_dir):
    try:
        # Betöltjük az MP3 fájlt
        audio = AudioSegment.from_mp3(input_file)
        # Átalakítjuk a kívánt paraméterekre
        audio = audio.set_frame_rate(24000).set_channels(1).set_sample_width(2)  # 16 bit = 2 byte
        # Kimeneti fájl neve és elérési út
        base_name = os.path.splitext(os.path.basename(input_file))[0]
        output_file = os.path.join(output_dir, f"{base_name}.wav")
        # Exportáljuk WAV formátumba
        audio.export(output_file, format="wav")
        return True, input_file
    except Exception as e:
        return False, input_file, str(e)

def get_all_mp3_files(input_dir):
    mp3_files = []
    for root, dirs, files in os.walk(input_dir):
        for file in files:
            if file.lower().endswith('.mp3'):
                mp3_files.append(os.path.join(root, file))
    return mp3_files

def main():
    args = parse_arguments()
    input_dir = args.input
    output_dir = args.output

    # Ellenőrizzük, hogy a bemeneti könyvtár létezik
    if not os.path.isdir(input_dir):
        print(f"Hiba: A bemeneti könyvtár nem létezik: {input_dir}")
        return

    # Létrehozzuk a kimeneti könyvtárat, ha nem létezik
    os.makedirs(output_dir, exist_ok=True)

    # Összegyűjtjük az összes MP3 fájlt
    mp3_files = get_all_mp3_files(input_dir)
    total_files = len(mp3_files)

    if total_files == 0:
        print("Nincsenek MP3 fájlok a megadott bemeneti könyvtárban.")
        return

    print(f"Talált {total_files} MP3 fájlt a konvertáláshoz.")

    # Definiáljuk a részleges függvényt a multiprocessing Pool számára
    convert_func = partial(convert_mp3_to_wav, output_dir=output_dir)

    # Használjunk több processzormagot
    pool_size = cpu_count()
    with Pool(pool_size) as pool:
        # Tqdm folyamatjelző a Pool imap wrapperével
        results = []
        for result in tqdm(pool.imap_unordered(convert_func, mp3_files), total=total_files, desc="Konvertálás progressz"):
            results.append(result)

    # Összegzés
    success_count = sum(1 for r in results if r[0])
    failure_count = total_files - success_count

    print(f"Konvertálás befejezve: {success_count} sikeres, {failure_count} sikertelen.")

    if failure_count > 0:
        print("Sikertelen konvertálások részletei:")
        for r in results:
            if not r[0]:
                print(f"Fájl: {r[1]}, Hiba: {r[2]}")

if __name__ == "__main__":
    main()

