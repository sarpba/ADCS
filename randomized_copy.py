import os
import shutil
import argparse
import random
import string

def generate_random_string(length=20):
    """Véletlenszerű karakterlánc generálása."""
    characters = string.ascii_letters + string.digits
    return ''.join(random.choices(characters, k=length))

def is_audio_file(filename, audio_extensions):
    """Ellenőrzi, hogy a fájl egy audio fájl-e."""
    return os.path.splitext(filename)[1].lower() in audio_extensions

def main(input_dir, output_dir):
    # Definiáljuk az audio fájl kiterjesztéseket
    audio_extensions = {'.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma', '.m4a'}

    # Ellenőrizzük, hogy az input könyvtár létezik
    if not os.path.isdir(input_dir):
        print(f"Hiba: Az input könyvtár nem létezik: {input_dir}")
        return

    # Létrehozzuk az output könyvtárat, ha nem létezik
    os.makedirs(output_dir, exist_ok=True)

    # Végigmegyünk az input könyvtár összes fájlján és almappáján
    for root, dirs, files in os.walk(input_dir):
        for file in files:
            if is_audio_file(file, audio_extensions):
                audio_path = os.path.join(root, file)
                base_name, ext = os.path.splitext(file)

                # Generálunk egy egyedi véletlenszerű nevet
                while True:
                    random_name = generate_random_string()
                    new_audio_filename = random_name + ext
                    new_audio_path = os.path.join(output_dir, new_audio_filename)
                    if not os.path.exists(new_audio_path):
                        break

                # Másoljuk az audio fájlt az új névvel
                shutil.copy2(audio_path, new_audio_path)
                print(f"Másolás: {audio_path} -> {new_audio_path}")

                # Ellenőrizzük, hogy van-e hozzá tartozó .txt fájl
                txt_filename = base_name + '.txt'
                txt_path = os.path.join(root, txt_filename)
                if os.path.isfile(txt_path):
                    new_txt_filename = random_name + '.txt'
                    new_txt_path = os.path.join(output_dir, new_txt_filename)
                    shutil.copy2(txt_path, new_txt_path)
                    print(f"Másolás: {txt_path} -> {new_txt_path}")
                else:
                    print(f"Figyelem: Nem található a txt fájl: {txt_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Audio és kapcsolódó txt fájlok átmásolása és átnevezése.")
    parser.add_argument('-i', '--input', required=True, help="Input könyvtár elérési útja.")
    parser.add_argument('-o', '--output', required=True, help="Output könyvtár elérési útja.")

    args = parser.parse_args()

    main(args.input, args.output)

