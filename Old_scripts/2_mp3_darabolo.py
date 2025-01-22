import os
import subprocess
import argparse
import shutil

def get_mp3_duration(file_path):
    cmd = [
        'ffprobe', '-i', file_path,
        '-show_entries', 'format=duration',
        '-v', 'quiet', '-of', 'csv=p=0'
    ]
    try:
        output = subprocess.check_output(cmd).decode().strip()
        return float(output)
    except Exception as e:
        print(f"Hiba a(z) {file_path} hosszának lekérdezésekor: {e}")
        return None

def split_mp3(file_path, output_dir, max_duration):
    base_name = os.path.basename(file_path)
    name, ext = os.path.splitext(base_name)
    output_pattern = os.path.join(output_dir, f'{name}_part%d{ext}')
    cmd = [
        'ffmpeg', '-i', file_path,
        '-f', 'segment',
        '-segment_time', str(max_duration),
        '-c', 'copy',
        '-reset_timestamps', '1',
        '-map', '0',
        '-segment_start_number', '1',
        output_pattern
    ]
    try:
        subprocess.run(cmd, check=True)
        print(f"Feldarabolva: {file_path}")
    except subprocess.CalledProcessError as e:
        print(f"Hiba a darabolás során: {e}")

def main():
    parser = argparse.ArgumentParser(description='MP3 fájlok darabolása és rendezése.')
    parser.add_argument('input_dir', help='Bemeneti könyvtár elérési útja')
    parser.add_argument('output_dir', help='Kimeneti könyvtár elérési útja')
    parser.add_argument('archive_dir', help='Archív könyvtár elérési útja a feldarabolt eredeti fájloknak')
    parser.add_argument('--max_duration', type=int, default=10000,
                        help='Maximális darab hossz másodpercben (alapértelmezett: 10000 másodperc)')
    args = parser.parse_args()

    INPUT_DIR = args.input_dir
    OUTPUT_DIR = args.output_dir
    ARCHIVE_DIR = args.archive_dir
    MAX_DURATION = args.max_duration

    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    if not os.path.exists(ARCHIVE_DIR):
        os.makedirs(ARCHIVE_DIR)

    for file in os.listdir(INPUT_DIR):
        if file.lower().endswith('.mp3'):
            mp3_path = os.path.join(INPUT_DIR, file)
            base_name, _ = os.path.splitext(file)
            json_file = os.path.join(INPUT_DIR, base_name + '.json')
            if os.path.exists(json_file):
                print(f"JSON fájl létezik a(z) {mp3_path} fájlhoz, kihagyás.")
                continue
            duration = get_mp3_duration(mp3_path)
            if duration and duration > MAX_DURATION:
                print(f"{mp3_path} hosszabb mint {MAX_DURATION/3600} óra, darabolás.")
                split_mp3(mp3_path, OUTPUT_DIR, MAX_DURATION)
                # Eredeti fájl áthelyezése az archív könyvtárba
                archive_path = os.path.join(ARCHIVE_DIR, file)
                shutil.move(mp3_path, archive_path)
                print(f"Eredeti fájl áthelyezve az archív könyvtárba: {archive_path}")
            else:
                print(f"{mp3_path} rövidebb vagy egyenlő mint {MAX_DURATION/3600} óra, kihagyás.")
                # Nem történik másolás vagy feldolgozás

if __name__ == '__main__':
    main()

