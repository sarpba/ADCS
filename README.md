Each file has a separate small task, as follows:

0: 0_yt_playlist_downloader.py

Downolad the audio data from youtube playlists (playlists_example.txt), convert 22050 Hz mono mp3 after download
```
$ python 0_yt_playlist_downloader.py -h
usage: 0_yt_playlist_downloader.py [-h] --download_dir DOWNLOAD_DIR [--yt_dlp_path YT_DLP_PATH] --playlists_file PLAYLISTS_FILE

YouTube lejátszási listák letöltése mp3 formátumban.

options:
  -h, --help            show this help message and exit
  --download_dir DOWNLOAD_DIR
                        Letöltési könyvtár az audio fájlokhoz (pl. /content/SMB/yt_audio)
  --yt_dlp_path YT_DLP_PATH
                        Útvonal az yt-dlp binárishoz (alapértelmezett: ./yt-dlp_linux)
  --playlists_file PLAYLISTS_FILE
                        Szövegfájl, amely a lejátszási lista URL-eket tartalmazza, egy sorban egy URL (pl. playlists.txt)
```

1: 1_mp3_convert_to_22050.py (optional)

If you have audio files from another source this script convert it same format (22050 Hz mono mp3)

```
$ python 1_mp3_convert_to_22050.py -h
usage: 1_mp3_convert_to_22050.py [-h] --input_dir INPUT_DIR --output_dir OUTPUT_DIR [--workers WORKERS]

Párhuzamos MP3 átkódoló script 44100 Hz-ről 22050 Hz-re

options:
  -h, --help            show this help message and exit
  --input_dir INPUT_DIR
                        Az input könyvtár útvonala
  --output_dir OUTPUT_DIR
                        Az output könyvtár útvonala
  --workers WORKERS     Párhuzamos munkavégzéshez használt processzek száma (alapértelmezés: CPU magok száma)
```

2: 2_mp3_darabolo.py

Cut the audio files 10000 second (default) pieces

```
$ python 2_mp3_darabolo.py -h
usage: 2_mp3_darabolo.py [-h] [--max_duration MAX_DURATION] input_dir output_dir archive_dir

MP3 fájlok darabolása és rendezése.

positional arguments:
  input_dir             Bemeneti könyvtár elérési útja
  output_dir            Kimeneti könyvtár elérési útja
  archive_dir           Archív könyvtár elérési útja a feldarabolt eredeti fájloknak

options:
  -h, --help            show this help message and exit
  --max_duration MAX_DURATION
                        Maximális darab hossz másodpercben (alapértelmezett: 10000 másodperc)
```

3: 3_whisx_v1.2.py

Transcript the audio files with whisperx and create more accurate timestamps with language specific Phoneme-Based ASR (wav2vec2.0) if possible. It use 2 GPU by deffault, and whisper-large-v3. You need to edit the file If you have another setup.

```
$ python 3_whisx_v1.2.py -h
usage: 3_whisx_v1.2.py [-h] directory

Transcribe audio files in a directory and its subdirectories using WhisperX with multiple GPUs.

positional arguments:
  directory   A könyvtár, amely tartalmazza az audio fájlokat.

options:
  -h, --help  show this help message and exit
```

4: 4_splitter_v4_json_v3.py

Cut the transcripted audio files to sentences. Create .txt files. The files lenght abaout 1-60 sec. (95% between 1-30 sec)

```
$ python 4_splitter_v4_json_v3.py -h
usage: 4_splitter_v4_json_v3.py [-h] --input_dir INPUT_DIR --output_dir OUTPUT_DIR

JSON és audio fájlok feldolgozása mondatokra bontáshoz és audio szakaszok kivágásához.

options:
  -h, --help            show this help message and exit
  --input_dir INPUT_DIR, -i INPUT_DIR
                        A bemeneti könyvtár útvonala, ahol a JSON és audio fájlok találhatók.
  --output_dir OUTPUT_DIR, -o OUTPUT_DIR
                        A kimeneti könyvtár útvonala, ahol a feldolgozott audio és szövegfájlok mentésre kerülnek.

Példa használat:
  python splitter_v4_json.py --input_dir ./bemenet --output_dir ./kimenet
```

5: 5_audio_analize_v2.py

Analise the small pieces with YAMNet. Create .json files.

```
usage: 5_audio_analize_v2.py [-h] [--workers WORKERS] directory

YAMNet MP3 elemzés JSON kimenettel több szálon, meglévő JSON-ok átugrásával

positional arguments:
  directory          Az elemzendő könyvtár elérési útja

options:
  -h, --help         show this help message and exit
  --workers WORKERS  A használni kívánt szálak száma (alapértelmezett: 12)

```
6: 6_copy_and_rename.py

Copy all files (mp3, txt, json) from subdirecrorys into one directory. Rename all file to random filename. This messes up the order of the database files.

```
$ python 6_copy_and_rename.py -h
usage: 6_copy_and_rename.py [-h] FORRÁS_KÖNYVTÁR CÉL_KÖNYVTÁR

Fájlok másolása és átnevezése véletlenszerű névre.

positional arguments:
  FORRÁS_KÖNYVTÁR  A forráskönyvtár elérési útja.
  CÉL_KÖNYVTÁR     A célkönyvtár elérési útja.

options:
  -h, --help       show this help message and exit
```

7.0: 7.0_move_duplicates.py

Move the duplicates out from database.

```
$ python 7.0_move_duplicates.py -h
usage: 7.0_move_duplicates.py [-h] FORRÁS_MAPPÁ CÉLMAPPÁ

Duplikált fájlok kezelése egy könyvtárban.

positional arguments:
  FORRÁS_MAPPÁ  Az átvizsgált könyvtár útvonala
  CÉLMAPPÁ      A célmappa útvonala, ahová a duplikált fájlok kerülnek

options:
  -h, --help    show this help message and exit
```

7.1 7.1_move_not_speach.py

Move the not speach content from database. (with YAMNet stamps)

```
$ python 7.1_move_not_speach.py -h
usage: 7.1_move_not_speach.py [-h] -s SOURCE_DIR -d DESTINATION_DIR [-t THRESHOLD]

Áthelyezi az azonos nevű mp3, json és txt fájlokat, ha a JSON fájlban a 'Speech' score
értéke kisebb, mint a megadott küszöbérték, vagy ha a 'Speech' címke hiányzik.

options:
  -h, --help            show this help message and exit
  -s SOURCE_DIR, --source_dir SOURCE_DIR
                        A forráskönyvtár elérési útvonala, amit át szeretnél vizsgálni.
  -d DESTINATION_DIR, --destination_dir DESTINATION_DIR
                        A célkönyvtár elérési útvonala, ahová az alacsony score-val vagy
                        hiányzó 'Speech' címkével rendelkező fájlokat szeretnéd
                        áthelyezni.
  -t THRESHOLD, --threshold THRESHOLD
                        A score küszöbértéke. Alapértelmezett érték: 0.95
```

7: 7_hany_szo.py

It's a simple information. How many words you have in you database.

```
python 7_hany_szo.py /examed/directory/
```

8: 8_move_json_and_txt.py

Move out all txt and json file from database into a temp directory.

```
```

9: 9_json_txt_merge.py

Merge the txt and json files from temp directory into the database directory.

```
```

10: 10_mondat_ellenorzes.py

Just check the sentences. Start with big character and and with ". ! ?"

```
```

11: 11_zsajos_csend_hozzáadása_v1.1.py (optional)

This script put random lenght (0-1000 ms) silence the audio files start and end.
example command:
```python 11_zsajos_csend_hozzáadása_v1.1.py /home/sarpba/audio_database/ /home/sarpba/audio_database_silence/

```
```
```

12: 12_HF_upload.py

Upload the database to huggingface (in parquet format)

```
```

You need to login with your HF_Token befor use it.
```
huggingface-cli login
```

