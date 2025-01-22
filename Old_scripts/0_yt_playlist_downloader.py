#!/usr/bin/env python3
import os
import subprocess
import argparse
import sys

def run_command(command, shell=False):
    """Futtat egy parancsot és ellenőrzi a hibákat."""
    try:
        print(f"Futtatás: {' '.join(command) if isinstance(command, list) else command}")
        subprocess.run(command, check=True, shell=shell)
    except subprocess.CalledProcessError as e:
        print(f"Hiba a következő parancs futtatásakor: {' '.join(command) if isinstance(command, list) else command}")
        sys.exit(e.returncode)

def download_yt_dlp(yt_dlp_path):
    """Letölti a yt-dlp binárist, ha még nem létezik."""
    if not os.path.exists(yt_dlp_path):
        print("Letöltés: yt-dlp bináris...")
        run_command(['wget', 'https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp', '-O', yt_dlp_path])
        # Futtathatóvá tesszük
        run_command(['chmod', '+x', yt_dlp_path])
    else:
        print(f"Az yt-dlp már létezik a következő helyen: {yt_dlp_path}")

def install_ffmpeg():
    """Telepíti az ffmpeg-et, ha még nincs telepítve."""
    print("Ellenőrzés: ffmpeg telepítve van-e...")
    try:
        subprocess.run(['ffmpeg', '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        print("Az ffmpeg már telepítve van.")
    except subprocess.CalledProcessError:
        print("Telepítés: ffmpeg...")
        run_command(['apt-get', 'update'])
        run_command(['apt-get', 'install', '-y', 'ffmpeg'])

def install_python_packages(packages):
    """Telepíti a szükséges Python csomagokat."""
    print(f"Telepítés: Python csomagok: {' '.join(packages)}")
    run_command([sys.executable, '-m', 'pip', 'install'] + packages)

def create_directory(path):
    """Létrehozza a megadott könyvtárat, ha nem létezik."""
    os.makedirs(path, exist_ok=True)
    print(f"Könyvtár létrehozva vagy már létezik: {path}")

def read_playlists_from_file(playlists_file):
    """Beolvassa a lejátszási listákat egy szövegfájlból."""
    if not os.path.isfile(playlists_file):
        print(f"Hiba: A lejátszási listák fájlja nem található: {playlists_file}")
        sys.exit(1)
    
    with open(playlists_file, 'r', encoding='utf-8') as file:
        lines = file.readlines()
    
    # Szűrjük ki az üres sorokat és a megjegyzéseket
    playlists = [line.strip() for line in lines if line.strip() and not line.strip().startswith('#')]
    
    if not playlists:
        print(f"Hiba: A lejátszási listák fájlja üres vagy csak megjegyzéseket tartalmaz: {playlists_file}")
        sys.exit(1)
    
    return playlists

def download_playlists(yt_dlp_path, playlist_urls, download_archive_path, download_dir):
    """Letölti a megadott YouTube lejátszási listákat."""
    for url in playlist_urls:
        print(f"Letöltés elkezdve a következő lejátszási listához: {url}")
        output_template = os.path.join(download_dir, '%(playlist_title)s', '%(title)s.%(ext)s')
        cmd = [
            yt_dlp_path,
            '-x',
            '--audio-format', 'mp3',
            '--audio-quality', '0',
            '--no-overwrites',
            '--restrict-filenames',
            url,
            '-o', output_template,
            '--postprocessor-args', '-ar 22050 -ac 1',
            '--download-archive', download_archive_path
        ]
        run_command(cmd)
        print(f"Letöltés befejezve a következő lejátszási listához: {url}")

def main():
    parser = argparse.ArgumentParser(description="YouTube lejátszási listák letöltése mp3 formátumban.")
    parser.add_argument('--download_dir', type=str, required=True, help='Letöltési könyvtár az audio fájlokhoz (pl. /content/SMB/yt_audio)')
    parser.add_argument('--yt_dlp_path', type=str, default='./yt-dlp_linux', help='Útvonal az yt-dlp binárishoz (alapértelmezett: ./yt-dlp_linux)')
    parser.add_argument('--playlists_file', type=str, required=True, help='Szövegfájl, amely a lejátszási lista URL-eket tartalmazza, egy sorban egy URL (pl. playlists.txt)')
    
    args = parser.parse_args()

    # Könyvtárak létrehozása
    create_directory(args.download_dir)

    # Download archive fájl elérési útjának beállítása a download_dir-ben
    download_archive_path = os.path.join(args.download_dir, 'downloaded.txt')

    # Letöltjük az yt-dlp binárist
    download_yt_dlp(args.yt_dlp_path)

    # Telepítjük az ffmpeg-et
    install_ffmpeg()

    # Telepítjük a szükséges Python könyvtárakat
    required_packages = ['noisereduce', 'librosa', 'pydub', 'soundfile']
    install_python_packages(required_packages)

    # Beolvassuk a lejátszási listákat a fájlból
    playlist_urls = read_playlists_from_file(args.playlists_file)

    # Letöltjük a lejátszási listákat
    download_playlists(args.yt_dlp_path, playlist_urls, download_archive_path, args.download_dir)

    print("Minden lejátszási lista letöltése és konvertálása befejeződött.")

if __name__ == "__main__":
        main()

