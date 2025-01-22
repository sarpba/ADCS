import os
import shutil
import json
import argparse

def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Áthelyezi az azonos nevű mp3, json és txt fájlokat, ha a JSON fájlban a 'Speech' score értéke kisebb, mint a megadott küszöbérték, vagy ha a 'Speech' címke hiányzik."
    )
    
    parser.add_argument(
        "-s", "--source_dir",
        type=str,
        required=True,
        help="A forráskönyvtár elérési útvonala, amit át szeretnél vizsgálni."
    )
    
    parser.add_argument(
        "-d", "--destination_dir",
        type=str,
        required=True,
        help="A célkönyvtár elérési útvonala, ahová az alacsony score-val vagy hiányzó 'Speech' címkével rendelkező fájlokat szeretnéd áthelyezni."
    )
    
    parser.add_argument(
        "-t", "--threshold",
        type=float,
        default=0.95,
        help="A score küszöbértéke. Alapértelmezett érték: 0.95"
    )
    
    return parser.parse_args()

def move_files(base_path, base_name, extensions, destination):
    for ext in extensions:
        file_path = os.path.join(base_path, f"{base_name}.{ext}")
        if os.path.exists(file_path):
            try:
                shutil.move(file_path, os.path.join(destination, f"{base_name}.{ext}"))
                print(f"Áthelyezve: {file_path} -> {destination}")
            except Exception as e:
                print(f"Hiba történt a fájl áthelyezésekor: {file_path}. Hiba: {e}")
        else:
            print(f"Hiányzó fájl: {file_path}")

def main():
    args = parse_arguments()
    source_dir = args.source_dir
    destination_dir = args.destination_dir
    score_threshold = args.threshold

    # Ellenőrizzük, hogy a forráskönyvtár létezik-e
    if not os.path.exists(source_dir):
        print(f"Hiba: A forráskönyvtár nem létezik: {source_dir}")
        return

    # Ellenőrizzük, hogy a célkönyvtár létezik-e, ha nem, létrehozzuk
    if not os.path.exists(destination_dir):
        try:
            os.makedirs(destination_dir)
            print(f"Létrehozva a célkönyvtár: {destination_dir}")
        except Exception as e:
            print(f"Hiba történt a célkönyvtár létrehozásakor: {e}")
            return

    # Könyvtár bejárása rekurzívan
    for root, dirs, files in os.walk(source_dir):
        for file in files:
            if file.endswith(".json"):
                json_path = os.path.join(root, file)
                try:
                    with open(json_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    # Keresés a 'Speech' címkére
                    speech_score = None
                    for item in data.get("analysis", []):
                        if item.get("label") == "Speech":
                            speech_score = item.get("score")
                            break
                    
                    # Logika a fájlok áthelyezésére
                    # Áthelyezünk, ha a 'Speech' score kisebb a küszöbértéknél, vagy nincs 'Speech' címke
                    if speech_score is None:
                        print(f"'Speech' címke hiányzik a fájlban: {json_path}. Áthelyezés.")
                        base_name = os.path.splitext(file)[0]
                        move_files(root, base_name, ['mp3', 'json', 'txt'], destination_dir)
                    elif speech_score < score_threshold:
                        print(f"'Speech' score ({speech_score}) kisebb a küszöbértéknél ({score_threshold}) a fájlban: {json_path}. Áthelyezés.")
                        base_name = os.path.splitext(file)[0]
                        move_files(root, base_name, ['mp3', 'json', 'txt'], destination_dir)
                    else:
                        print(f"'Speech' score ({speech_score}) elegendő a fájlban: {json_path}. Nem kerül áthelyezésre.")
                
                except json.JSONDecodeError:
                    print(f"Hibás JSON formátum: {json_path}")
                except Exception as e:
                    print(f"Hiba történt a {json_path} feldolgozása közben: {e}")

    print("Fájlok áthelyezése befejeződött.")

if __name__ == "__main__":
    main()

