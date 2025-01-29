import os
import shutil
import argparse

def move_files(source_dir, target_dir):
    # Ellenőrizzük, hogy létezik-e a célkönyvtár, ha nem, létrehozzuk
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)

    # Végigmegyünk a forrás könyvtár fájljain
    for root, dirs, files in os.walk(source_dir):
        for file in files:
            if file.endswith('.txt') or file.endswith('.json'):
                # Fájl elérési útvonalak
                source_file = os.path.join(root, file)
                target_file = os.path.join(target_dir, file)
                
                # Áthelyezzük a fájlokat
                shutil.move(source_file, target_file)
                print(f"Áthelyezve: {source_file} -> {target_file}")

if __name__ == "__main__":
    # Argumentumok kezelése
    parser = argparse.ArgumentParser(description="TXT és JSON fájlok áthelyezése")
    parser.add_argument('-i', '--input', required=True, help="Forrás könyvtár")
    parser.add_argument('-o', '--output', required=True, help="Cél könyvtár")

    args = parser.parse_args()

    # Fájlok áthelyezése
    move_files(args.input, args.output)

