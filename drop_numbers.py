import os
import shutil
import argparse
import re

def contains_number(file_path):
    """Ellenőrzi, hogy a fájl tartalmaz-e számot."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                if re.search(r'\d', line):
                    return True
    except Exception as e:
        print(f"Hiba a fájl olvasása közben: {file_path}. Hiba: {e}")
    return False

def get_associated_files(base_path, base_name, audio_extensions):
    """Visszaadja az azonos alapnevemű .json és audio fájlokat."""
    associated = []
    json_file = os.path.join(base_path, f"{base_name}.json")
    if os.path.isfile(json_file):
        associated.append(json_file)
    for ext in audio_extensions:
        audio_file = os.path.join(base_path, f"{base_name}{ext}")
        if os.path.isfile(audio_file):
            associated.append(audio_file)
    return associated

def main(input_dir, output_dir):
    # Definiáljuk az audio fájl kiterjesztéseket
    audio_extensions = ['.mp3', '.wav', '.aac', '.flac', '.ogg', '.m4a']

    for root, dirs, files in os.walk(input_dir):
        for file in files:
            if file.lower().endswith('.txt'):
                txt_path = os.path.join(root, file)
                if contains_number(txt_path):
                    # Relatív útvonal meghatározása az input könyvtárhoz képest
                    rel_path = os.path.relpath(root, input_dir)
                    target_dir = os.path.join(output_dir, rel_path)

                    # Létrehozzuk a célkönyvtárat, ha nem létezik
                    os.makedirs(target_dir, exist_ok=True)

                    # Áthelyezzük a txt fájlt
                    shutil.move(txt_path, os.path.join(target_dir, file))
                    print(f"Áthelyezve: {txt_path} -> {os.path.join(target_dir, file)}")

                    # Áthelyezzük az associated fájlokat
                    base_name = os.path.splitext(file)[0]
                    associated_files = get_associated_files(root, base_name, audio_extensions)
                    for assoc_file in associated_files:
                        try:
                            shutil.move(assoc_file, os.path.join(target_dir, os.path.basename(assoc_file)))
                            print(f"Áthelyezve: {assoc_file} -> {os.path.join(target_dir, os.path.basename(assoc_file))}")
                        except Exception as e:
                            print(f"Hiba az áthelyezés során: {assoc_file}. Hiba: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Áthelyezi a számokat tartalmazó txt fájlokat és azokhoz tartozó json/audio fájlokat.")
    parser.add_argument('-i', '--input', required=True, help='Bemeno könyvtár')
    parser.add_argument('-o', '--output', required=True, help='Kimeneti könyvtár')
    args = parser.parse_args()

    input_directory = args.input
    output_directory = args.output

    if not os.path.isdir(input_directory):
        print(f"A megadott bemeno könyvtár nem létezik: {input_directory}")
        exit(1)

    os.makedirs(output_directory, exist_ok=True)

    main(input_directory, output_directory)

