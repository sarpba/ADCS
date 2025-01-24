import argparse
import os
import csv
from multiprocessing import Pool, cpu_count
from functools import partial
from tqdm import tqdm

def parse_arguments():
    parser = argparse.ArgumentParser(description='TXT fájlok tartalmának összegyűjtése és metadata.csv létrehozása.')
    parser.add_argument('-i', '--input', required=True, help='Bemeneti könyvtár, ahol a TXT fájlok találhatók.')
    parser.add_argument('-o', '--output', required=True, help='Kimeneti könyvtár, ahova a metadata.csv kerül.')
    return parser.parse_args()

def process_txt_file(input_file, output_dir):
    try:
        # Fájl neve kiterjesztés nélkül
        base_name = os.path.splitext(os.path.basename(input_file))[0]
        dir_name = os.path.dirname(input_file)
        
        # Lehetséges audio fájl kiterjesztések
        audio_extensions = ['.mp3', '.wav']
        audio_file = None

        # Megkeressük az első létező audio fájlt a megadott kiterjesztések közül
        for ext in audio_extensions:
            potential_file = os.path.join(dir_name, base_name + ext)
            if os.path.exists(potential_file):
                audio_file = os.path.abspath(potential_file)  # Teljes elérési út
                break

        if audio_file is None:
            raise FileNotFoundError(f"Corresponding audio file (.mp3 vagy .wav) not found for: {input_file}")

        # Fájl tartalmának olvasása
        with open(input_file, 'r', encoding='utf-8') as f:
            content = f.read().replace('\n', ' ').strip()
        
        # Teljes elérési út használata
        return (audio_file, content, True, "")
    except Exception as e:
        # A bemeneti fájl teljes elérési útja
        input_full_path = os.path.abspath(input_file)
        return (input_full_path, "", False, str(e))

def get_all_txt_files(input_dir):
    txt_files = []
    for root, dirs, files in os.walk(input_dir):
        for file in files:
            if file.lower().endswith('.txt'):
                txt_files.append(os.path.join(root, file))
    return txt_files

def main():
    args = parse_arguments()
    input_dir = os.path.abspath(args.input)
    output_dir = os.path.abspath(args.output)

    # Ellenőrizzük, hogy a bemeneti könyvtár létezik
    if not os.path.isdir(input_dir):
        print(f"Hiba: A bemeneti könyvtár nem létezik: {input_dir}")
        return

    # Létrehozzuk a kimeneti könyvtárat, ha nem létezik
    os.makedirs(output_dir, exist_ok=True)

    # Összegyűjtjük az összes TXT fájlt
    txt_files = get_all_txt_files(input_dir)
    total_files = len(txt_files)

    if total_files == 0:
        print("Nincsenek TXT fájlok a megadott bemeneti könyvtárban.")
        return

    print(f"Talált {total_files} TXT fájlt a metadata.csv létrehozásához.")

    # Definiáljuk a részleges függvényt a multiprocessing Pool számára
    pool_size = cpu_count()
    with Pool(pool_size) as pool:
        # A partial segítségével átadjuk az output_dir-t a process_txt_file függvénynek
        func = partial(process_txt_file, output_dir=output_dir)
        results = []
        for result in tqdm(pool.imap_unordered(func, txt_files), total=total_files, desc="Fájlok feldolgozása"):
            results.append(result)

    # Írjuk a metadata.csv fájlt a kimeneti könyvtárba
    output_file = os.path.join(output_dir, 'metadata.csv')
    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile, delimiter='|', quoting=csv.QUOTE_MINIMAL)
        for res in results:
            if res[2]:  # Sikeres feldolgozás
                writer.writerow([res[0], res[1]])

    # Összegzés
    success_count = sum(1 for r in results if r[2])
    failure_count = total_files - success_count

    print(f"\nmetadata.csv létrehozva a következő helyre: {output_file}")
    print(f"Sikeres feldolgozások: {success_count}, Sikertelen feldolgozások: {failure_count}")

    if failure_count > 0:
        print("Sikertelen feldolgozások részletei:")
        for r in results:
            if not r[2]:
                print(f"Fájl: {r[0]}, Hiba: {r[3]}")

if __name__ == "__main__":
    main()

