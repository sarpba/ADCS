import os
import shutil
import argparse
from collections import defaultdict

def find_duplicate_txt_files(library_path):
    content_map = defaultdict(list)

    for root, dirs, files in os.walk(library_path):
        for file in files:
            if file.lower().endswith('.txt'):
                txt_path = os.path.join(root, file)
                try:
                    with open(txt_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    content_map[content].append(txt_path)
                except Exception as e:
                    print(f"Hiba a fájl olvasása közben: {txt_path}. Hiba: {e}")

    # Kiválasztjuk azokat a tartalmakat, amelyek több fájlhoz tartoznak
    duplicates = {content: paths for content, paths in content_map.items() if len(paths) > 1}
    return duplicates

def move_file_group(file_path, library_path, target_path):
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    extensions = ['.txt', '.json', '.mp3']

    for ext in extensions:
        src_file = os.path.join(os.path.dirname(file_path), base_name + ext)
        if os.path.exists(src_file):
            # Kiszámoljuk a relatív utat a könyvtárhoz képest
            rel_path = os.path.relpath(os.path.dirname(src_file), library_path)
            # Célmappa útvonalának létrehozása
            dest_dir = os.path.join(target_path, rel_path)
            os.makedirs(dest_dir, exist_ok=True)
            dest_file = os.path.join(dest_dir, base_name + ext)
            try:
                shutil.move(src_file, dest_file)
                print(f"Áthelyezve: {src_file} -> {dest_file}")
            except Exception as e:
                print(f"Hiba az áthelyezés során: {src_file} -> {dest_file}. Hiba: {e}")

def process_duplicates(duplicates, library_path, target_path):
    for content, paths in duplicates.items():
        # Az első fájlt megtartjuk, a többit áthelyezzük
        for duplicate_path in paths[1:]:
            move_file_group(duplicate_path, library_path, target_path)

def main():
    parser = argparse.ArgumentParser(description='Duplikált fájlok kezelése egy könyvtárban.')
    parser.add_argument('source', metavar='FORRÁS_MAPPÁ', type=str,
                        help='Az átvizsgált könyvtár útvonala')
    parser.add_argument('target', metavar='CÉLMAPPÁ', type=str,
                        help='A célmappa útvonala, ahová a duplikált fájlok kerülnek')

    args = parser.parse_args()
    library_path = args.source
    target_path = args.target

    if not os.path.isdir(library_path):
        print(f"A megadott könyvtár nem létezik: {library_path}")
        return

    if not os.path.exists(target_path):
        try:
            os.makedirs(target_path)
            print(f"Célmappa létrehozva: {target_path}")
        except Exception as e:
            print(f"Hiba a célmappa létrehozásakor: {e}")
            return

    duplicates = find_duplicate_txt_files(library_path)
    if not duplicates:
        print("Nincsenek duplikált `.txt` fájlok.")
        return

    process_duplicates(duplicates, library_path, target_path)
    print("Feldolgozás befejezve.")

if __name__ == "__main__":
    main()

