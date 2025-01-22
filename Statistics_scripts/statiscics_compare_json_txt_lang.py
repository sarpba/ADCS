import os
import json
import argparse
import multiprocessing as mp
from collections import defaultdict
from tqdm import tqdm

def get_all_basenames(root_dir):
    """
    Végigiterál a megadott könyvtáron (és alkönyvtárain),
    és összegyűjti azoknak a fájloknak az alapkiterjesztés nélküli nevét (basename),
    amelyek mp3, txt vagy json kiterjesztéssel rendelkeznek.
    """
    basenames = set()
    for dirpath, dirnames, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename.endswith(('.mp3', '.txt', '.json')):
                basename = os.path.splitext(filename)[0]
                basenames.add(os.path.join(dirpath, basename))
    return basenames

def normalize_text(text):
    """
    A szöveg normalizálása:
    - Levágja a sor eleji és végi szóközöket
    - Kicseréli a több szóközt egyetlen szóközre
    - Kisbetűsít
    """
    return ' '.join(text.strip().split()).lower()

def levenshtein_distance(s1, s2):
    """
    Kiszámolja a Levenshtein-távolságot két string között.
    Ez a minimális szerkesztési lépések (beszúrás, törlés, helyettesítés) száma,
    amely ahhoz szükséges, hogy s1-et s2-vé alakítsuk.
    """
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)

    # Biztosítjuk, hogy s1 legyen a hosszabb string.
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1           # karakter beszúrása
            deletions = current_row[j] + 1                 # karakter törlése
            substitutions = previous_row[j] + (c1 != c2)   # helyettesítés (0 vagy 1)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    
    return previous_row[-1]

def compare_files(basename, max_diff):
    """
    Egy adott basename-hez tartozó .txt és .json fájlok sorait hasonlítja össze.
    
    Visszatérési érték:
    (exact_matches, normalized_matches, total_lines, lang_stats)

    - exact_matches: hány sor egyezik PONTOSAN (EXACT)
    - normalized_matches: hány sor egyezik NORMALIZÁLTAN (figyelembe véve max_diff betűeltérést)
    - total_lines: a ténylegesen összehasonlított sorok száma
    - lang_stats: { 
         language: {
            "matched_exact": ...,
            "unmatched_exact": ...,
            "matched_norm": ...,
            "unmatched_norm": ...
         }
      }
    """
    txt_path = basename + '.txt'
    json_path = basename + '.json'
    mp3_path = basename + '.mp3'

    # Csak akkor dolgozunk, ha mindhárom fájl létezik
    if not (os.path.exists(txt_path) and os.path.exists(json_path) and os.path.exists(mp3_path)):
        return 0, 0, 0, {}

    # TXT beolvasása
    try:
        with open(txt_path, 'r', encoding='utf-8') as f:
            txt_lines = [line.strip() for line in f.readlines()]
    except OSError:
        return 0, 0, 0, {}

    # JSON beolvasása
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            json_texts = [segment['text'].strip() for segment in data.get('segments', [])]
    except (OSError, json.JSONDecodeError):
        return 0, 0, 0, {}

    # Nyelv kiolvasása a JSON-ből
    language = data.get("language", "UNKNOWN")

    # Statisztikák
    exact_matches = 0
    normalized_matches = 0
    total = min(len(txt_lines), len(json_texts))

    # Nyelvi részletes számlálók
    # Pontos egyezés + nem egyezés, normalizált egyezés + nem egyezés
    lang_stats = {
        language: {
            "matched_exact": 0,
            "unmatched_exact": 0,
            "matched_norm": 0,
            "unmatched_norm": 0
        }
    }

    for i in range(total):
        txt_line = txt_lines[i]
        json_line = json_texts[i]

        # 1) PONTOS EGYEZÉS (EXACT)
        if txt_line == json_line:
            exact_matches += 1
            # Ha EXACT, akkor a normalizált is automatikusan egyező
            normalized_matches += 1

            lang_stats[language]["matched_exact"] += 1
            lang_stats[language]["matched_norm"] += 1
        else:
            # Nem egyezik pontosan
            lang_stats[language]["unmatched_exact"] += 1

            # 2) NORMALIZÁLT EGYEZÉS
            ntxt = normalize_text(txt_line)
            njson = normalize_text(json_line)

            if ntxt == njson:
                normalized_matches += 1
                lang_stats[language]["matched_norm"] += 1
            else:
                dist = levenshtein_distance(ntxt, njson)
                if dist <= max_diff:
                    normalized_matches += 1
                    lang_stats[language]["matched_norm"] += 1
                else:
                    # Normalizáltan sem egyezik
                    lang_stats[language]["unmatched_norm"] += 1

    return exact_matches, normalized_matches, total, lang_stats

def process_basename(args):
    """
    A multiprocessing Pool számára: csomagolja a compare_files meghívását.
    """
    basename, max_diff = args
    return compare_files(basename, max_diff)

def main():
    parser = argparse.ArgumentParser(
        description='Statisztika készítése a könyvtárban található .mp3, .txt, .json fájlokról.'
    )
    parser.add_argument('-i', '--input', required=True, 
                        help='A könyvtár elérési útja')
    parser.add_argument('-d', '--max_diff', type=int, default=0, 
                        help='A megengedett maximális betűeltérés a normalizált összehasonlításnál (alapértelmezés: 0)')
    
    args = parser.parse_args()
    root_dir = args.input
    max_diff = args.max_diff

    if not os.path.isdir(root_dir):
        print(f"A megadott útvonal nem érvényes könyvtár: {root_dir}")
        return
    
    # 1) Összegyűjtjük az összes basename-t
    basenames = get_all_basenames(root_dir)

    # 2) Előkészítjük a feladatokat
    tasks = [(bn, max_diff) for bn in basenames]

    # 3) Összesített statisztikák
    total_exact_matches = 0
    total_normalized_matches = 0
    total_lines = 0
    file_count = 0

    # 4) Nyelvi statisztikák
    # Ebben tároljuk a nyelvenkénti összesítést:
    #   "matched_exact": összes EXACT egyezés
    #   "unmatched_exact": összes EXACT nem egyezés
    #   "matched_norm": összes NORMALIZÁLT egyezés
    #   "unmatched_norm": összes NORMALIZÁLT nem egyezés
    global_lang_stats = defaultdict(lambda: {
        "matched_exact": 0,
        "unmatched_exact": 0,
        "matched_norm": 0,
        "unmatched_norm": 0
    })

    # 5) Párhuzamos feldolgozás
    with mp.Pool() as pool:
        # Folyamatjelző (progress bar)
        for exact_matches, normalized_matches, lines, lang_stats in tqdm(
            pool.imap_unordered(process_basename, tasks),
            total=len(tasks),
            desc="Feldolgozás"
        ):
            # Ha ebben a fájlcsoportban tényleg volt mit összehasonlítani
            if lines > 0:
                file_count += 1
                total_exact_matches += exact_matches
                total_normalized_matches += normalized_matches
                total_lines += lines

                # Nyelvi statisztikák összesítése
                for lang, stats in lang_stats.items():
                    global_lang_stats[lang]["matched_exact"] += stats["matched_exact"]
                    global_lang_stats[lang]["unmatched_exact"] += stats["unmatched_exact"]
                    global_lang_stats[lang]["matched_norm"] += stats["matched_norm"]
                    global_lang_stats[lang]["unmatched_norm"] += stats["unmatched_norm"]

    # 6) Általános eredmények kiírása
    print("\n--- Általános statisztikák ---")
    if total_lines > 0:
        print(f"Összes feldolgozott fájlcsoport (mindhárom fájllal): {file_count}")
        print(f"Összes összehasonlított sor: {total_lines}\n")

        print(f"Pontos egyező sorok száma (EXACT): {total_exact_matches}")
        print(f"Pontos egyezés aránya (EXACT): {total_exact_matches / total_lines * 100:.2f}%\n")

        print(f"Normalizált egyező sorok száma (max_diff={max_diff}): {total_normalized_matches}")
        print(f"Normalizált egyezés aránya: {total_normalized_matches / total_lines * 100:.2f}%")
    else:
        print("Nincsenek összehasonlítandó sorok vagy nem találtunk háromfájlos csoportot.")

    # 7) Nyelvi statisztikák összeállítása
    print("\n--- Nyelvi statisztikák ---")

    # Segédösszegek a nyelvek között
    # EXACT
    all_unmatched_exact = sum(s["unmatched_exact"] for s in global_lang_stats.values())
    all_matched_exact = sum(s["matched_exact"] for s in global_lang_stats.values())

    # NORMALIZÁLT
    all_matched_norm = sum(s["matched_norm"] for s in global_lang_stats.values())

    # 7/a) Nem egyező (EXACT) sorok nyelvek szerinti megoszlása
    print("\nNem egyező (EXACT) sorok nyelvek szerinti megoszlása:")
    if all_unmatched_exact > 0:
        for lang in sorted(global_lang_stats.keys()):
            unmatched = global_lang_stats[lang]["unmatched_exact"]
            perc = unmatched / all_unmatched_exact * 100 if all_unmatched_exact else 0
            print(f"{lang}: {unmatched} sor ({perc:.2f}%)")
    else:
        print("Nincsenek nem egyező sorok (EXACT).")

    # 7/b) Egyező (EXACT) sorok nyelvek szerinti megoszlása
    print("\nEgyező (EXACT) sorok nyelvek szerinti megoszlása:")
    if all_matched_exact > 0:
        for lang in sorted(global_lang_stats.keys()):
            matched = global_lang_stats[lang]["matched_exact"]
            perc = matched / all_matched_exact * 100 if all_matched_exact else 0
            print(f"{lang}: {matched} sor ({perc:.2f}%)")
    else:
        print("Nincsenek egyező sorok (EXACT).")

    # 7/c) Egyező (normalizált) sorok nyelvek szerinti megoszlása
    print("\nEgyező (normalizált) sorok nyelvek szerinti megoszlása:")
    if all_matched_norm > 0:
        for lang in sorted(global_lang_stats.keys()):
            matched_norm = global_lang_stats[lang]["matched_norm"]
            perc = matched_norm / all_matched_norm * 100 if all_matched_norm else 0
            print(f"{lang}: {matched_norm} sor ({perc:.2f}%)")
    else:
        print("Nincsenek egyező (normalizált) sorok.")

if __name__ == "__main__":
    main()

