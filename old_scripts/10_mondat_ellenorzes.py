import os
import json
import argparse

def check_sentence_rules(sentence):
    """
    Ellenőrzi, hogy a mondat nagybetűvel kezdődik és írásjellel végződik.
    Visszatér egy listával, amely tartalmazza a megsértett szabályokat.
    """
    violations = []
    if not sentence:
        violations.append("Üres mondat.")
        return violations

    # Ellenőrzi a kezdő nagybetűt
    if not sentence[0].isupper():
        violations.append("Nem nagybetűvel kezdődik.")

    # Ellenőrzi a végén lévő írásjelet
    if sentence[-1] not in '.!?':
        violations.append("Nem írásjellel végződik (.?!).")

    return violations

def check_json_files(directory):
    """
    Végigmegy a megadott könyvtárban lévő összes JSON fájlon,
    és ellenőrzi a 'sentence' mezőt.
    """
    invalid_files = []

    # Ellenőrzi, hogy a megadott könyvtár létezik-e
    if not os.path.isdir(directory):
        print(f"Hiba: A megadott könyvtár nem létezik: {directory}")
        return

    # Lista az összes fájlról a könyvtárban
    for filename in os.listdir(directory):
        if filename.lower().endswith('.json'):
            filepath = os.path.join(directory, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as file:
                    data = json.load(file)
                    
                    sentence = data.get('sentence', '')
                    violations = check_sentence_rules(sentence)
                    
                    if violations:
                        invalid_files.append((filename, sentence, violations))
            except json.JSONDecodeError as e:
                print(f"Hiba a JSON fájl olvasásakor: {filename} - {e}")
            except Exception as e:
                print(f"Ismeretlen hiba történt: {filename} - {e}")

    if invalid_files:
        print("\nA következő JSON fájlokban a 'sentence' mező nem felel meg a szabályoknak:")
        for fname, sent, issues in invalid_files:
            print(f"\n- Fájl: {fname}")
            print(f"  Sentence: {sent}")
            print("  Hibák:")
            for issue in issues:
                print(f"    - {issue}")
    else:
        print("Minden JSON fájlban a 'sentence' mező érvényes.")

def main():
    parser = argparse.ArgumentParser(description="JSON fájlok 'sentence' mezőjének ellenőrzése.")
    parser.add_argument(
        'directory',
        type=str,
        help='A könyvtár elérési útja, amelyben a JSON fájlok találhatók.'
    )
    args = parser.parse_args()
    check_json_files(args.directory)

if __name__ == "__main__":
    main()

