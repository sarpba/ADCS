import argparse
import json
import os
import shutil
from multiprocessing import Pool, cpu_count
from tqdm import tqdm

def process_json_file(args):
    file_path, input_dir, target_lang = args
    rel_path = os.path.relpath(os.path.dirname(file_path), input_dir)
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            file_lang = data.get('language', '')
            
            move = file_lang != target_lang
            return (rel_path, base_name, move, False)
    except Exception as e:
        print(f"\nError processing {file_path}: {str(e)}")
        return (rel_path, base_name, False, True)

def main():
    parser = argparse.ArgumentParser(description='Move files based on JSON language and file associations.')
    parser.add_argument('-i', required=True, help='Input directory')
    parser.add_argument('-o', required=True, help='Output directory')
    parser.add_argument('-lang', required=True, help='Target language code')
    args = parser.parse_args()

    input_dir = os.path.abspath(args.i)
    output_dir = os.path.abspath(args.o)
    target_lang = args.lang

    move_set = set()
    existing_json_pairs = set()
    error_files = set()

    # JSON fájlok gyűjtése
    json_files = []
    for root, dirs, files in os.walk(input_dir):
        for filename in files:
            if filename.lower().endswith('.json'):
                json_files.append((os.path.join(root, filename), input_dir, target_lang))

    # JSON fájlok párhuzamos feldolgozása
    with Pool(processes=cpu_count()) as pool:
        results = []
        with tqdm(total=len(json_files), desc="Processing JSON files") as pbar:
            for result in pool.imap(process_json_file, json_files):
                rel_path, base_name, move, error = result
                if error:
                    error_files.add((rel_path, base_name))
                else:
                    existing_json_pairs.add((rel_path, base_name))
                    if move:
                        move_set.add((rel_path, base_name))
                pbar.update()

    # Fájlok mozgatása
    all_files = []
    for root, dirs, files in os.walk(input_dir):
        for filename in files:
            all_files.append((root, filename))

    moved_count = 0
    with tqdm(total=len(all_files), desc="Moving files") as pbar:
        for root, filename in all_files:
            file_path = os.path.join(root, filename)
            rel_path = os.path.relpath(root, input_dir)
            base_name, ext = os.path.splitext(filename)
            ext = ext.lower()

            move_file = False

            if ext == '.json':
                if (rel_path, base_name) in move_set:
                    move_file = True
            else:
                if (rel_path, base_name) in move_set:
                    move_file = True
                elif (rel_path, base_name) not in existing_json_pairs:
                    move_file = True

            if move_file:
                dest_dir = os.path.join(output_dir, rel_path)
                os.makedirs(dest_dir, exist_ok=True)
                dest_path = os.path.join(dest_dir, filename)
                try:
                    shutil.move(file_path, dest_path)
                    moved_count += 1
                except Exception as e:
                    print(f"\nError moving {file_path}: {str(e)}")
                
            pbar.update()

    print(f"\nProcessing complete! Moved {moved_count} files.")
    if error_files:
        print(f"Encountered errors in {len(error_files)} files.")

if __name__ == '__main__':
    main()
