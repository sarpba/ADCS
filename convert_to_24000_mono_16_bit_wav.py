import argparse
import os
import shutil  # Fájlok másolásához
from pydub import AudioSegment
from multiprocessing import Pool, cpu_count
from functools import partial
from tqdm import tqdm

def parse_arguments():
    parser = argparse.ArgumentParser(description='Audio fájlok konvertálása WAV formátumba és TXT fájlok másolása.')
    parser.add_argument('-i', '--input', required=True, help='Bemeneti könyvtár, ahol az audio és TXT fájlok találhatók.')
    parser.add_argument('-o', '--output', required=True, help='Kimeneti könyvtár, ahova a WAV és TXT fájlok kerülnek.')
    return parser.parse_args()

def convert_audio_to_wav(input_file, output_dir, input_base_dir):
    try:
        # Meghatározzuk a relatív elérési utat a bemeneti könyvtárhoz képest
        relative_path = os.path.relpath(input_file, start=input_base_dir)
        # Útvonalból csak a könyvtárrészt vesszük
        relative_dir = os.path.dirname(relative_path)
        # Teljes kimeneti könyvtár elérési út
        full_output_dir = os.path.join(output_dir, relative_dir)
        # Kimeneti almappák létrehozása, ha nem léteznek
        os.makedirs(full_output_dir, exist_ok=True)
        # Kimeneti fájl neve és elérési útja
        base_name = os.path.splitext(os.path.basename(input_file))[0]
        output_file = os.path.join(full_output_dir, f"{base_name}.wav")
        
        # Ellenőrizzük, hogy a kimeneti fájl már létezik-e
        if os.path.exists(output_file):
            return 'skipped', input_file, "Már létezik a kimeneti WAV fájl."
        
        # Audio betöltése (a pydub automatikusan felismeri a formátumot)
        audio = AudioSegment.from_file(input_file)
        
        # Átalakítjuk a kívánt paraméterekre (24 kHz, mono, 16 bit)
        audio = audio.set_frame_rate(24000).set_channels(1).set_sample_width(2)  # 16 bit = 2 byte
        
        # Exportáljuk WAV formátumba
        audio.export(output_file, format="wav")
        return 'success', input_file
    except Exception as e:
        return 'failed', input_file, str(e)

def get_all_audio_files(input_dir):
    # Támogatott kiterjesztések
    audio_extensions = ('.mp3', '.wav', '.flac', '.m4a', '.opus', '.ogg', '.wma', '.aac', '.webm', '.weba')
    audio_files = []
    for root, dirs, files in os.walk(input_dir):
        for file in files:
            if file.lower().endswith(audio_extensions):
                audio_files.append(os.path.join(root, file))
    return audio_files

def get_all_txt_files(input_dir):
    txt_files = []
    for root, dirs, files in os.walk(input_dir):
        for file in files:
            if file.lower().endswith('.txt'):
                txt_files.append(os.path.join(root, file))
    return txt_files

def copy_txt_files(input_dir, output_dir):
    txt_files = get_all_txt_files(input_dir)
    total_txt = len(txt_files)
    if total_txt == 0:
        print("Nincsenek TXT fájlok a másoláshoz.")
        return
    
    print(f"Talált {total_txt} TXT fájlt a másoláshoz.")
    
    skipped_txt = 0
    copied_txt = 0
    failed_txt = 0
    
    for txt_file in tqdm(txt_files, desc="TXT fájlok másolása", unit="fájl"):
        try:
            # Relatív elérési út a bemeneti könyvtárhoz képest
            rel_path = os.path.relpath(txt_file, start=input_dir)
            # Cél elérési út
            dest_path = os.path.join(output_dir, rel_path)
            # Cél könyvtár létrehozása, ha nem létezik
            dest_dir = os.path.dirname(dest_path)
            os.makedirs(dest_dir, exist_ok=True)
            
            # Ellenőrizzük, hogy a célfájl már létezik-e
            if os.path.exists(dest_path):
                skipped_txt += 1
                continue
            
            # Fájl másolása
            shutil.copy2(txt_file, dest_path)
            copied_txt += 1
        except Exception as e:
            print(f"Hiba a {txt_file} másolásakor: {e}")
            failed_txt += 1
    
    print(f"TXT fájlok másolása befejezve: {copied_txt} sikeresen másolva, {skipped_txt} átugorva, {failed_txt} sikertelen.")

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

    # Összegyűjtjük az összes támogatott audio fájlt
    audio_files = get_all_audio_files(input_dir)
    total_files = len(audio_files)

    if total_files == 0:
        print("Nincsenek támogatott audio fájlok a megadott bemeneti könyvtárban.")
        return

    print(f"Talált {total_files} audio fájlt a konvertáláshoz.")

    # Definiáljuk a részleges függvényt a multiprocessing Pool számára
    convert_func = partial(convert_audio_to_wav, output_dir=output_dir, input_base_dir=input_dir)

    # Használjunk több processzormagot
    pool_size = cpu_count()
    with Pool(pool_size) as pool:
        # Tqdm folyamatjelző a Pool imap wrapperével
        results = []
        for result in tqdm(pool.imap_unordered(convert_func, audio_files), total=total_files, desc="Konvertálás progressz"):
            results.append(result)

    # Összegzés
    success_count = sum(1 for r in results if r[0] == 'success')
    skipped_count = sum(1 for r in results if r[0] == 'skipped')
    failure_count = sum(1 for r in results if r[0] == 'failed')

    print(f"Konvertálás befejezve: {success_count} sikeres, {skipped_count} átugorva, {failure_count} sikertelen.")

    if failure_count > 0:
        print("Sikertelen konvertálások részletei:")
        for r in results:
            if r[0] == 'failed':
                print(f"Fájl: {r[1]}, Hiba: {r[2]}")

    # TXT fájlok másolása a konvertálás után
    copy_txt_files(input_dir, output_dir)

    print("Minden művelet befejezve.")

if __name__ == "__main__":
    main()
