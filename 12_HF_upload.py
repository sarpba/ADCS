import os
import json
import argparse
import datasets
from datasets import Dataset, Audio

# Argumentumok kezelése
def parse_args():
    parser = argparse.ArgumentParser(description="Upload MP3 and JSON data to Hugging Face dataset.")
    parser.add_argument("--data_dir", type=str, required=True, help="Path to the directory containing mp3 and json files.")
    parser.add_argument("--dataset_name", type=str, required=True, help="Name of the Hugging Face dataset (format: your_username/dataset_name).")
    return parser.parse_args()

# Fő funkció
def main(args):
    data_dir = args.data_dir
    dataset_name = args.dataset_name
    
    # Ellenőrizzük, hogy a megadott könyvtár létezik-e
    if not os.path.exists(data_dir):
        print(f"Error: Directory {data_dir} does not exist.")
        return
    
    json_files = [f for f in os.listdir(data_dir) if f.endswith('.json')]
    
    if not json_files:
        print(f"No JSON files found in {data_dir}")
        return

    # Lista az adatok gyűjtésére
    data_entries = []
    
    for json_file in json_files:
        json_path = os.path.join(data_dir, json_file)
        with open(json_path, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
            mp3_path = os.path.join(data_dir, json_data['path'])
            if os.path.exists(mp3_path):
                # JSON tartalom betöltése
                data_entries.append({
                    "path": mp3_path,
                    "sentence": json_data["sentence"],
                    "analysis": json_data["analysis"]
                })
    
    if not data_entries:
        print(f"No matching mp3 files found in {data_dir}")
        return

    # Hugging Face Dataset szerkezet létrehozása
    dataset = Dataset.from_dict({
        "audio": [entry["path"] for entry in data_entries],
        "sentence": [entry["sentence"] for entry in data_entries],
        "analysis": [entry["analysis"] for entry in data_entries]
    })
    
    # Audio oszlop beállítása
    dataset = dataset.cast_column("audio", Audio(sampling_rate=22050))
    
    # Feltöltés a Hugging Face felületre
    dataset.push_to_hub(dataset_name, private=True)
    print(f"Dataset {dataset_name} uploaded successfully.")

if __name__ == "__main__":
    args = parse_args()
    main(args)

