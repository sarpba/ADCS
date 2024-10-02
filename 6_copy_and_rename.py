import os
import shutil
import random
import string
import argparse
import sys

# Fájl kiterjesztések, amiket feldolgozunk
FILE_EXTENSIONS = ['.mp3', '.txt', '.json']
RANDOM_NAME_LENGTH = 25  # Véletlenszerű név hossza

def generate_random_name(length=RANDOM_NAME_LENGTH):
    """Generál egy véletlenszerű nevet angol betűkből és számokból."""
    chars = string.ascii_letters + string.digits
    return ''.join(random.choices(chars, k=length))

def get_existing_base_names(target_dir):
    """Visszaadja a célkönyvtárban már létező alapneveket."""
    existing = set()
    try:
        for filename in os.listdir(target_dir):
            base, ext = os.path.splitext(filename)
            if ext.lower() in FILE_EXTENSIONS:
                existing.add(base)
    except FileNotFoundError:
        pass  # Ha a célkönyvtár nem létezik, üres halmazt adunk vissza
    return existing

def collect_files(source_dir):
    """Gyűjti a releváns fájlokat, csoportosítva az alapnevek szerint."""
    files_dict = {}
    for root, dirs, files in os.walk(source_dir):
        for file in files:
            base, ext = os.path.splitext(file)
            if ext.lower() in FILE_EXTENSIONS:
                if base not in files_dict:
                    files_dict[base] = []
                files_dict[base].append(os.path.join(root, file))
    return files_dict

def parse_arguments():
    """Parszolja a parancssori argumentumokat."""
    parser = argparse.ArgumentParser(description='Fájlok másolása és átnevezése véletlenszerű névre.')
    parser.add_argument('source', metavar='FORRÁS_KÖNYVTÁR', type=str,
                        help='A forráskönyvtár elérési útja.')
    parser.add_argument('target', metavar='CÉL_KÖNYVTÁR', type=str,
                        help='A célkönyvtár elérési útja.')
    return parser.parse_args()

def main():
    args = parse_arguments()
    SOURCE_DIR = args.source
    TARGET_DIR = args.target

    # Ellenőrizzük, hogy a forráskönyvtár létezik-e
    if not os.path.isdir(SOURCE_DIR):
        print(f"Hiba: A forráskönyvtár nem található vagy nem egy könyvtár: {SOURCE_DIR}")
        sys.exit(1)

    # Ellenőrizzük, hogy a célkönyvtár létezik-e, ha nem, létrehozzuk
    if not os.path.exists(TARGET_DIR):
        try:
            os.makedirs(TARGET_DIR)
            print(f"A célkönyvtár létrehozva: {TARGET_DIR}")
        except Exception as e:
            print(f"Hiba a célkönyvtár létrehozásakor: {e}")
            sys.exit(1)

    # Lekérjük a célkönyvtárban már létező alapneveket
    existing_names = get_existing_base_names(TARGET_DIR)

    # Gyűjtsük össze a fájlokat a forráskönyvtárból
    files_dict = collect_files(SOURCE_DIR)

    if not files_dict:
        print("Nincsenek feldolgozandó fájlok a megadott forráskönyvtárban.")
        sys.exit(0)

    # Feldolgozzuk minden alapnevet
    for original_base, file_paths in files_dict.items():
        # Generáljunk egyedi véletlenszerű nevet
        attempts = 0
        while True:
            new_base = generate_random_name()
            if new_base not in existing_names:
                existing_names.add(new_base)
                break
            attempts += 1
            if attempts > 100:
                print("Hiba: Nem sikerült egyedi nevet generálni 100 próbálkozás után.")
                sys.exit(1)
        # Másoljuk át a fájlokat az új névvel
        for file_path in file_paths:
            _, ext = os.path.splitext(file_path)
            new_filename = new_base + ext.lower()
            destination_path = os.path.join(TARGET_DIR, new_filename)
            try:
                shutil.copy2(file_path, destination_path)
                print(f"Másolva: {file_path} -> {destination_path}")
            except Exception as e:
                print(f"Hiba a másolás során {file_path} -> {destination_path}: {e}")

    print("Fájlok sikeresen átmásolva és átnevezve.")

if __name__ == "__main__":
    main()

