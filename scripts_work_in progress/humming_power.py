import os
import json
import argparse
import numpy as np
import librosa
import matplotlib.pyplot as plt
import librosa.display

# Példa: két frekvenciatartomány, ahol a zaj energiáját vizsgáljuk:
# - low_hum: klasszikus alacsony frekvenciás zaj (45-55 Hz)
# - speech_band_hum: a beszédhang sávjában jelentkező esetleges zaj (300-3400 Hz)
hum_ranges = [
    {"label": "low_hum", "low": 0, "high": 85},
    {"label": "speech", "low": 85, "high": 600},    
    {"label": "high_hum", "low": 600, "high": 44100}
]

def analyze_audio(file_path, hum_ranges, display_spec=False):
    """
    Audió elemzése: spektrum és spektrogram számítása, majd a megadott frekvenciatartományokban (hum_ranges)
    lévő energia kiszámítása.
    
    Paraméterek:
      - file_path: a hangfájl elérési útja.
      - hum_ranges: lista, melynek elemei dict-ek {"label": <név>, "low": <alsó határ>, "high": <felső határ>}.
      - display_spec: ha True, a spektrogram megjelenik.
      
    Visszatérési érték:
      Egy dict, amely tartalmazza a fájl abszolút elérési útját, nevét, időtartamát, mintavételi frekvenciáját,
      a teljes energiát, valamint az egyes tartományokra számított energia és arány értékeket.
    """
    try:
        # Audió betöltése (mono)
        y, sr = librosa.load(file_path, sr=None)
    except Exception as e:
        print(f"Hiba a '{file_path}' betöltésekor: {e}")
        return None

    duration = librosa.get_duration(y=y, sr=sr)
    
    # STFT számítása
    n_fft = 2048
    hop_length = 512
    D = librosa.stft(y, n_fft=n_fft, hop_length=hop_length)
    S, _ = librosa.magphase(D)  # csak az amplitúdó spektrum
    
    # Frekvencia tengely meghatározása
    freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)
    
    # Spektrogram megjelenítése, ha kértük (opcionális)
    if display_spec:
        plt.figure(figsize=(10, 4))
        librosa.display.specshow(librosa.amplitude_to_db(S, ref=np.max),
                                 sr=sr, hop_length=hop_length, x_axis='time', y_axis='log')
        plt.colorbar(format='%+2.0f dB')
        plt.title(f'Spektrogram: {os.path.basename(file_path)}')
        plt.tight_layout()
        plt.show()
    
    # Teljes energia számítása az egész spektrumban (minden időablak)
    total_energy = np.sum(S**2)
    
    hum_results = {}
    # Az egyes frekvenciatartományok energiájának és arányának kiszámítása
    for hum_range in hum_ranges:
        low_f = hum_range["low"]
        high_f = hum_range["high"]
        label = hum_range["label"]
        # Maszk a kiválasztott frekvenciákhoz
        mask = (freqs >= low_f) & (freqs <= high_f)
        # Energia összegzés a kiválasztott frekvenciasávban
        hum_energy = np.sum(S[mask, :]**2)
        hum_ratio = hum_energy / total_energy if total_energy > 0 else 0
        # A numpy típusokat natív típussá konvertáljuk
        hum_results[label] = {
            "low_frequency": low_f,
            "high_frequency": high_f,
            "energy": float(hum_energy),
            "ratio": float(hum_ratio)
        }
    
    result = {
        "file_path": os.path.abspath(file_path),
        "file_name": os.path.basename(file_path),
        "duration_sec": float(duration),
        "sampling_rate": int(sr),
        "total_energy": float(total_energy),
        "hum_analysis": hum_results
    }
    
    return result

def get_audio_files(root_directory):
    """
    Rekurzívan bejárja a megadott könyvtárat, és listázza az összes hangfájlt.
    Elfogadott kiterjesztések: .wav, .mp3, .flac, .ogg
    """
    valid_extensions = ('.wav', '.mp3', '.flac', '.ogg')
    audio_files = []
    for root, _, files in os.walk(root_directory):
        for file in files:
            if file.lower().endswith(valid_extensions):
                audio_files.append(os.path.join(root, file))
    return audio_files

def main():
    parser = argparse.ArgumentParser(description="Audiófájlok spektrum- és spektrogram analízise a háttérzaj (sistergés) felismerésére.")
    parser.add_argument("-i", "--input", required=True, help="A vizsgálandó könyvtár elérési útja (rekurzív bejárással).")
    parser.add_argument("--display", action="store_true", help="Ha megadva, a spektrogram megjelenítésre kerül.")
    parser.add_argument("-o", "--output", default="audio_analysis_results.json", help="Az eredményeket tartalmazó JSON fájl neve.")
    args = parser.parse_args()
    
    input_dir = args.input
    output_json = args.output
    
    if not os.path.isdir(input_dir):
        print(f"Hiba: A megadott útvonal nem könyvtár: {input_dir}")
        return
    
    audio_files = get_audio_files(input_dir)
    if not audio_files:
        print(f"Nincsenek hangfájlok a megadott könyvtárban: {input_dir}")
        return
    
    results = []
    for file_path in audio_files:
        print(f"Feldolgozás alatt: {file_path}")
        result = analyze_audio(file_path, hum_ranges, display_spec=args.display)
        if result is not None:
            # Kiíratás a konzolra
            print(f"  Fájl: {result['file_name']}")
            print(f"  Elérési út: {result['file_path']}")
            print(f"  Időtartam: {result['duration_sec']} s, Mintavételi frekvencia: {result['sampling_rate']} Hz")
            for label, data in result["hum_analysis"].items():
                print(f"    - {label}: {data['energy']:.2f} energia, arány: {data['ratio']:.4f}")
            results.append(result)
    
    # Eredmények mentése JSON fájlba
    try:
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=4)
        print(f"\nAz összes eredmény elmentve: {output_json}")
    except Exception as e:
        print(f"Hiba az eredmények mentésekor: {e}")

if __name__ == "__main__":
    main()
