import os
from pydub import AudioSegment
import argparse
import concurrent.futures
from tqdm import tqdm

def convert_mp3(file_info):
    """
    Átkódolja az MP3 fájlt 22050 Hz-re és elmenti az output könyvtárba.

    Args:
        file_info (tuple): Egy tuple, amely az input fájl elérési útját és az output fájl elérési útját tartalmazza.

    Returns:
        str: A sikeresen átkódolt fájl elérési útja, vagy hibaüzenet.
    """
    input_file, output_file = file_info
    try:
        # Audió betöltése
        audio = AudioSegment.from_mp3(input_file)
        
        # Átkódolás 22050 Hz-re
        audio_22050 = audio.set_frame_rate(22050)
        
        # Az output könyvtár létrehozása, ha nem létezik
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        # Fájl exportálása az output könyvtárba
        audio_22050.export(output_file, format="mp3")
        
        return f"Siker: {input_file} -> {output_file}"
    except Exception as e:
        return f"Hiba: {input_file} -> {e}"

def get_all_mp3_files(input_dir, output_dir):
    """
    Gyűjti az összes MP3 fájl elérési útját az input könyvtárból és alkönyvtáraiból.

    Args:
        input_dir (str): Az input könyvtár útvonala.
        output_dir (str): Az output könyvtár útvonala.

    Returns:
        list: Listája a tuple-öknek, amelyek az input és output fájl elérési útjait tartalmazzák.
    """
    file_pairs = []
    for root, dirs, files in os.walk(input_dir):
        for file in files:
            if file.lower().endswith(".mp3"):
                input_file = os.path.join(root, file)
                output_file = os.path.join(output_dir, file)
                file_pairs.append((input_file, output_file))
    return file_pairs

def main(input_dir, output_dir, num_workers):
    # Gyűjtsük össze az összes MP3 fájl párosítását
    file_pairs = get_all_mp3_files(input_dir, output_dir)
    
    if not file_pairs:
        print("Nincs MP3 fájl az input könyvtárban.")
        return
    
    # Párhuzamos feldolgozás
    with concurrent.futures.ProcessPoolExecutor(max_workers=num_workers) as executor:
        # TQDM progress bar használata
        results = list(tqdm(executor.map(convert_mp3, file_pairs), total=len(file_pairs), desc="Átkódolás folyamatban", unit="fájl"))
    
    # Eredmények kiírása
    success_count = 0
    failure_count = 0
    for result in results:
        if result.startswith("Siker"):
            success_count += 1
        else:
            failure_count += 1
            print(result)
    
    print(f"\nÁtkódolva: {success_count} fájl")
    if failure_count > 0:
        print(f"Sikertelen: {failure_count} fájl")

if __name__ == "__main__":
    # Argumentumok kezelése
    parser = argparse.ArgumentParser(description="Párhuzamos MP3 átkódoló script 44100 Hz-ről 22050 Hz-re")
    parser.add_argument('--input_dir', type=str, required=True, help='Az input könyvtár útvonala')
    parser.add_argument('--output_dir', type=str, required=True, help='Az output könyvtár útvonala')
    parser.add_argument('--workers', type=int, default=os.cpu_count(), help='Párhuzamos munkavégzéshez használt processzek száma (alapértelmezés: CPU magok száma)')
    
    args = parser.parse_args()
    
    main(args.input_dir, args.output_dir, args.workers)

