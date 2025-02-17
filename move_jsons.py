#!/usr/bin/env python3
import os
import shutil
import argparse

def main():
    parser = argparse.ArgumentParser(
        description='JSON fájlok áthelyezése a megadott könyvtárstruktúra megtartásával.'
    )
    parser.add_argument(
        '-i', '--input',
        required=True,
        help='Bemeneti könyvtár, ahol a JSON fájlokat keressük és áthelyezzük.'
    )
    parser.add_argument(
        '-o', '--output',
        required=True,
        help='Kimeneti könyvtár, ahová a JSON fájlokat áthelyezzük.'
    )
    args = parser.parse_args()

    # A megadott könyvtárak abszolút elérési útjainak meghatározása
    input_dir = os.path.abspath(args.input)
    output_dir = os.path.abspath(args.output)

    # Végigmegyünk a bemeneti könyvtár összes alkönyvtárán
    for root, dirs, files in os.walk(input_dir):
        for file in files:
            # Csak a .json kiterjesztésű fájlokkal dolgozunk
            if file.lower().endswith('.json'):
                source_file = os.path.join(root, file)
                # Relatív útvonal meghatározása a bemeneti könyvtárhoz képest
                rel_path = os.path.relpath(root, input_dir)
                # A célkönyvtár elérési útjának felépítése
                dest_dir = os.path.join(output_dir, rel_path)
                # Célkönyvtár létrehozása, ha még nem létezik
                os.makedirs(dest_dir, exist_ok=True)
                dest_file = os.path.join(dest_dir, file)
                print(f'Mozgatás: {source_file} -> {dest_file}')
                # Fájl áthelyezése
                shutil.move(source_file, dest_file)

if __name__ == '__main__':
    main()

