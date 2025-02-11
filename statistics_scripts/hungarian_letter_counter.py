#!/usr/bin/env python3
import argparse
import os
import re

# A magyar ábécé betűi (kisbetűs formában), a több karakterből álló betűket
# érdemes előre venni a keresés során, hogy ne legyen átfedés.
HUNGARIAN_ALPHABET = [
    "dzs", "dz",  # először a három- majd a kétbetűs speciálisak
    "cs", "gy", "ly", "ny", "sz", "ty", "zs",
    "a", "á", "b", "c", "d", "e", "é", "f", "g",
    "h", "i", "í", "j", "k", "l", "m", "n",
    "o", "ó", "ö", "ő", "p", "q", "r", "s",
    "t", "u", "ú", "ü", "ű", "v", "w", "x",
    "y", "z"
]

def count_hungarian_letters(text, count_dict):
    """
    Bemenet: text (str), és egy count_dict (dict), ahol a kulcsok a HUNGARIAN_ALPHABET betűi,
    az értékek pedig az előfordulások száma.
    
    A függvény végigmegy a szövegen, és ha talál egy 3 betűs elemet (dzs),
    akkor azt számolja, majd 2 betűs elemeket (dz, cs, gy, stb.), végül a
    1 betűs elemeket (a, á, b, c, stb.).
    """
    # alakítsuk kisbetűssé
    text = text.lower()
    i = 0
    length = len(text)
    while i < length:
        # Először próbáljunk 3 karakteres egyezést keresni (pl. 'dzs')
        if i + 2 < length:
            tri = text[i:i+3]
            if tri in count_dict:
                count_dict[tri] += 1
                i += 3
                continue
        
        # Ha nem talált 3 karaktereset, próbáljunk 2 karaktereset
        if i + 1 < length:
            duo = text[i:i+2]
            if duo in count_dict:
                count_dict[duo] += 1
                i += 2
                continue
        
        # Ha az előzőek nem illeszkedtek, akkor megnézzük az 1 karaktereset
        single = text[i]
        if single in count_dict:
            count_dict[single] += 1
        
        i += 1


def collect_text_files_in_directory(directory):
    """
    Visszaadja az adott könyvtárban (rekurzívan) található összes .txt fájl
    tartalmának egyesített szövegét.
    """
    collected_text = []
    for root, dirs, files in os.walk(directory):
        for file_name in files:
            if file_name.lower().endswith(".txt"):
                file_path = os.path.join(root, file_name)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        collected_text.append(f.read())
                except Exception as e:
                    # Ha hiba van a fájl olvasásakor (pl. kódolási hiba),
                    # akkor átugorjuk vagy kezeljük tetszés szerint.
                    print(f"Nem sikerült beolvasni: {file_path} ({e})")
    return "\n".join(collected_text)


def main():
    parser = argparse.ArgumentParser(
        description="Magyar ábécé betűi gyakoriságának megállapítása és szó-statisztika."
    )
    parser.add_argument("-i", "--input_dir", required=True,
                        help="A könyvtár, amelyben a .txt fájlokat keressük.")
    
    args = parser.parse_args()
    input_directory = args.input_dir
    
    # Ellenőrizzük, hogy létezik-e a könyvtár
    if not os.path.isdir(input_directory):
        print(f"Hiba: A megadott könyvtár nem létezik: {input_directory}")
        return
    
    # 1. Gyűjtsük össze a .txt fájlok tartalmát
    text = collect_text_files_in_directory(input_directory)
    
    # 2. Hozzunk létre egy szótárat a magyar betűk számlálásához
    count_dict = {letter: 0 for letter in HUNGARIAN_ALPHABET}
    
    # 3. Számoljuk meg a betűk gyakoriságát
    count_hungarian_letters(text, count_dict)
    
    # 4. Készítsünk statisztikát a szavakról
    # A szavakat egyszerűen split-tel (vagy regex-szel) választjuk szét.
    # Példa: regex-szel kiszűrjük a "szószerű" tokeneket:
    words = re.findall(r"\w+", text.lower())
    total_words = len(words)
    unique_words = len(set(words))
    
    # 5. Eredmények kiírása
    print("=== Magyar ábécé betűinek gyakorisága ===")
    for letter in HUNGARIAN_ALPHABET:
        print(f"{letter}: {count_dict[letter]}")
    
    print("\n=== Szavak statisztikája ===")
    print(f"Összes szó: {total_words}")
    print(f"Egyedi szavak: {unique_words}")


if __name__ == "__main__":
    main()
