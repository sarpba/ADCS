import os
import json
import argparse

def update_json_files(input_directory, output_directory):
    """Frissíti a json fájlokat az input könyvtárból és elmenti azokat az output könyvtárba."""
    for filename in os.listdir(input_directory):
        if filename.endswith(".json"):
            json_file_path = os.path.join(input_directory, filename)
            txt_file_path = os.path.join(input_directory, filename.replace(".json", ".txt"))
            
            # Betölti a json fájlt
            with open(json_file_path, "r", encoding="utf-8") as json_file:
                data = json.load(json_file)
            
            # Betölti a txt fájlt
            if os.path.exists(txt_file_path):
                with open(txt_file_path, "r", encoding="utf-8") as txt_file:
                    sentence_content = txt_file.read().strip()  # A txt tartalom beolvasása és whitespace eltávolítása
                
                # 'file' törlése (ha van)
                if 'file' in data:
                    del data['file']
                
                # Az új JSON struktúra elkészítése az eredeti 'analysis' megtartásával
                file_base_name = os.path.splitext(filename)[0]  # Fájlnév kiterjesztés nélkül
                updated_data = {
                    'path': f"{file_base_name}.mp3",  # 'path' mező
                    'sentence': sentence_content,     # 'sentence' mező
                    'analysis': data.get('analysis', [])  # Eredeti 'analysis' megtartása
                }
                
                # Az output könyvtárba menti az új json fájlt
                output_file_path = os.path.join(output_directory, filename)
                with open(output_file_path, "w", encoding="utf-8") as output_file:
                    json.dump(updated_data, output_file, indent=4, ensure_ascii=False)
                
                print(f"Módosítva és elmentve: {output_file_path}")
            else:
                print(f"TXT fájl nem található ehhez: {filename}")

if __name__ == "__main__":
    # Argumentumok kezelése
    parser = argparse.ArgumentParser(description="JSON és TXT fájlokat kezelő script.")
    parser.add_argument("input_directory", help="Az input könyvtár, amely tartalmazza a JSON és TXT fájlokat.")
    parser.add_argument("output_directory", help="Az output könyvtár, ahová az új JSON fájlok kerülnek.")
    
    args = parser.parse_args()
    
    input_directory = args.input_directory
    output_directory = args.output_directory
    
    # Létrehozza az output könyvtárat, ha nem létezik
    if not os.path.exists(output_directory):
        os.makedirs(output_directory)

    # JSON fájlok frissítése és mentése
    update_json_files(input_directory, output_directory)

