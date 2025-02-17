import os
import json
import argparse
import subprocess
import random
import librosa
import numpy as np
import urllib.request
import shutil

# Új hum_ranges beállítások:
hum_ranges = [
    {"label": "speech", "low": 85, "high": 600},
]

def get_duration(file_path):
    """Az ffprobe segítségével lekéri az audió file hosszát (másodpercben)."""
    cmd = [
        'ffprobe', '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        file_path
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        duration = float(result.stdout.strip())
    except Exception as e:
        print(f"Hiba a duration lekérésénél: {e}")
        duration = 0
    return duration

def extract_random_segment(file_path, segment_length=30):
    """
    Kivág egy véletlenszerű, 30 másodperces részletet az audióból az ffmpeg segítségével.
    A kimeneti fájl neve: (basename)_30.wav.
    """
    duration = get_duration(file_path)
    if duration < segment_length:
        print(f"Fájl {file_path} hossza kisebb, mint {segment_length} s. Átugrom.")
        return None
    start_time = random.uniform(0, duration - segment_length)
    base = os.path.splitext(os.path.basename(file_path))[0]
    output_path = os.path.join(os.path.dirname(file_path), f"{base}_30.wav")
    cmd = [
        'ffmpeg', '-y',
        '-ss', str(start_time),
        '-t', str(segment_length),
        '-i', file_path,
        '-acodec', 'pcm_s16le',  # PCM 16-bit WAV
        output_path
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return output_path

def apply_noise_reduction(input_path, model_path='sh.rnnn'):
    """
    Alkalmazza az ffmpeg arnndn filterét a megadott audió file-ra,
    és elmenti a zajszűrt változatot (basename)_filtered.wav néven.
    """
    base = os.path.splitext(os.path.basename(input_path))[0]
    output_path = os.path.join(os.path.dirname(input_path), f"{base}_filtered.wav")
    cmd = [
        'ffmpeg', '-y',
        '-i', input_path,
        '-af', f'arnndn=m={model_path}',
        output_path
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return output_path

def analyze_audio(file_path):
    """
    Az audió file spektrumának számítása librosa segítségével,
    majd az előre meghatározott frekvenciatartományban (hum_ranges) számolja ki
    az energia és az arány értékét.
    """
    try:
        y, sr = librosa.load(file_path, sr=None)
    except Exception as e:
        print(f"Hiba a {file_path} betöltésekor: {e}")
        return None

    duration = librosa.get_duration(y=y, sr=sr)
    n_fft = 2048
    hop_length = 512
    D = librosa.stft(y, n_fft=n_fft, hop_length=hop_length)
    S, _ = librosa.magphase(D)
    total_energy = np.sum(S**2)
    freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)
    
    hum_results = {}
    for hr in hum_ranges:
        mask = (freqs >= hr["low"]) & (freqs <= hr["high"])
        energy = np.sum(S[mask, :]**2)
        ratio = energy / total_energy if total_energy > 0 else 0
        hum_results[hr["label"]] = {
            "low_frequency": hr["low"],
            "high_frequency": hr["high"],
            "energy": float(energy),
            "ratio": float(ratio)
        }
    result = {
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
        for f in files:
            if f.lower().endswith(valid_extensions):
                audio_files.append(os.path.join(root, f))
    return audio_files

def main():
    parser = argparse.ArgumentParser(
        description="Audiófájlok feldolgozása: kivág egy véletlenszerű 30 mp részt, "
                    "arnndn zajszűrést alkalmaz, majd elvégzi a spektrum analízist. "
                    "Ha a számolt speech_energy_ratio nagyobb, mint a --value paraméter, "
                    "áthelyezi az eredeti fájlt (illetve azonos basenevű .txt és .json fájlokat) "
                    "az output könyvtárba, megtartva a könyvtárstruktúrát."
    )
    parser.add_argument("-i", "--input", required=True, help="Vizsgálandó könyvtár (rekurzív bejárással).")
    parser.add_argument("-o", "--output", required=True,
                        help="Kimeneti könyvtár a fájlok áthelyezéséhez és az eredmények JSON fájl mentéséhez.")
    parser.add_argument("--value", type=float, default=1.1,
                        help="speech_energy_ratio threshold értéke (alapértelmezetten 1.1).")
    parser.add_argument("--model", default="sh.rnnn",
                        help="Az arnndn filter által használt modell elérési útja (alapértelmezetten sh.rnnn).")
    args = parser.parse_args()

    if not os.path.isdir(args.input):
        print(f"Hiba: {args.input} nem egy érvényes könyvtár.")
        return

    # Ha az output könyvtár nem létezik, hozzuk létre
    os.makedirs(args.output, exist_ok=True)

    # Ha a modell nem található, töltsük le a GitHub raw URL-jéről
    if not os.path.exists(args.model):
        model_url = "https://raw.githubusercontent.com/GregorR/rnnoise-models/master/somnolent-hogwash-2018-09-01/sh.rnnn"
        print(f"A modell '{args.model}' nem található, letöltés innen: {model_url}")
        try:
            urllib.request.urlretrieve(model_url, args.model)
            print("Modell sikeresen letöltve.")
        except Exception as e:
            print(f"Hiba a modell letöltésekor: {e}")
            return

    audio_files = get_audio_files(args.input)
    if not audio_files:
        print(f"Nincsenek hangfájlok a megadott könyvtárban: {args.input}")
        return

    results = []
    for file in audio_files:
        print(f"Feldolgozás alatt: {file}")
        seg_path = extract_random_segment(file, segment_length=30)
        if seg_path is None:
            continue
        filtered_path = apply_noise_reduction(seg_path, model_path=args.model)
        analysis_unfiltered = analyze_audio(seg_path)
        analysis_filtered = analyze_audio(filtered_path)
        if analysis_unfiltered is None or analysis_filtered is None:
            continue
        
        # A "speech" tartomány energiájának hányadosa:
        speech_energy_unfiltered = analysis_unfiltered["hum_analysis"]["speech"]["energy"]
        speech_energy_filtered = analysis_filtered["hum_analysis"]["speech"]["energy"]
        if speech_energy_filtered > 0:
            speech_energy_ratio = speech_energy_unfiltered / speech_energy_filtered
        else:
            speech_energy_ratio = None
        
        result = {
            "original_file": os.path.abspath(file),
            "speech_energy_ratio": speech_energy_ratio
        }
        results.append(result)
        
        # Ha a speech_energy_ratio nagyobb, mint a megadott threshold, akkor áthelyezzük az eredeti fájlt
        if speech_energy_ratio is not None and speech_energy_ratio > args.value:
            base_name = os.path.splitext(os.path.basename(file))[0]
            # Áthelyezzük az eredeti audiófájlt, valamint (ha létezik) az azonos basenevű .txt és .json fájlokat is
            for ext in ["", ".txt", ".json"]:
                if ext == "":
                    src_path = file
                else:
                    src_path = os.path.join(os.path.dirname(file), base_name + ext)
                if os.path.exists(src_path):
                    rel_path = os.path.relpath(src_path, args.input)
                    dst_path = os.path.join(args.output, rel_path)
                    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
                    print(f"Áthelyezés: {src_path} -> {dst_path}")
                    shutil.move(src_path, dst_path)
        
        # Opcióként töröljük a _30 és _30_filtered fileokat, ha nem kell őket megőrizni
        try:
            os.remove(seg_path)
            os.remove(filtered_path)
        except Exception as e:
            print(f"Hiba a temp fájlok törlésekor: {e}")

    # Az eredmények JSON mentése az output könyvtárba
    result_json_path = os.path.join(args.output, "audio_analysis_results.json")
    try:
        with open(result_json_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=4)
        print(f"\nAz összes eredmény elmentve: {result_json_path}")
    except Exception as e:
        print(f"Hiba az eredmények mentésekor: {e}")

if __name__ == "__main__":
    main()
