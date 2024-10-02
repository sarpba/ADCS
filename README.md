Each file has a separate small task, as follows:

0: 0_yt_playlist_downloader.py

Downolad the audio data from youtube playlists (playlists_example.txt), convert 22050 Hz mono mp3 after download

1: 1_mp3_convert_to_22050.py (optional)

If you have audio files from another source this script convert it same format (22050 Hz mono mp3)

2: 2_mp3_darabolo.py

Cut the audio files 10000 second (default) pices

3: 3_whisx_v1.2.py

Transcript the audio files with whisperx and create more accurate timestamps with hanguage specific Phoneme-Based ASR (wav2vec2.0) if possible. It use 2 GPU by deffault, and whisper-large-v3. You need to edit the file If you hav another setup.

4: 4_splitter_v4_json_v3.py

Cut the transcripted audio files to sentences. Create .txt files. The files lenght abaout 1-60 sec.

5: 5_audio_analize_v2.py

Analise the small splits with YAMNet. Create .json files.

6: 6_copy_and_rename.py

Copy all files (mp3, txt, json) from subdirecrorys into one directory. Rename all file to random filename. This messes up the order of the database files.

7.0: 7.0_move_duplicates.py

Move the duplicates out from database.

7.1 7.1_move_not_speach.py

Muve the not speach content from database. (with YAMNet stamps)

7: 7_hany_szo.py

It's a simple information. How many words you have in you database.

8: 8_move_json_and_txt.py

Move out all txt and json file from database into a temp directory.

9: 9_json_txt_merge.py

Merge the txt and json files from temp directory into the database directory.

10: 10_mondat_ellenorzes.py

Just check the sentences. Start with big character and and with ". ! ?"

11: 11_zsajos_csend_hozzáadása.py (optional)

This script put random 0-1000 ms silence the audio files start and end.

12: 12_HF_upload.py

Upload the database to huggingface (in paqulet format)
You need to login with your HF_Token befor use it.
```
huggingface-cli login
```

