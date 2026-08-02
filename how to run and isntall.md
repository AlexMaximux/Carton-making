You can install and run this repo on Ubuntu by cloning it, installing Python dependencies, installing ffmpeg, then running `python main.py` with the appropriate arguments. [github](https://github.com/AlexMaximux/Carton-making)

Below is a step‑by‑step guide tailored for Ubuntu.

## 1. Install system prerequisites

Open a terminal and run:

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip ffmpeg
```
This ensures you have Python 3.8+ and ffmpeg/ffprobe installed, which the project requires. [github](https://github.com/AlexMaximux/Carton-making)

You can verify ffmpeg:

```bash
ffmpeg -version
```

## 2. Clone the repository

In the directory where you want the project:

```bash
git clone https://github.com/AlexMaximux/Carton-making.git
cd Carton-making
```
This downloads the code exactly as in the GitHub repository. [github](https://github.com/AlexMaximux/Carton-making)

If `git` is missing:

```bash
sudo apt install git
```

## 3. (Recommended) Create and activate a virtualenv

To isolate dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
```
Your shell prompt should now show `(.venv)` indicating the virtual environment is active.

To deactivate later:

```bash
deactivate
```

## 4. Install Python dependencies

Inside the repo (and the venv, if you created one):

```bash
pip install -r requirements.txt
```
This installs all the Python packages listed in `requirements.txt` that the tool needs. [github](https://github.com/AlexMaximux/Carton-making)

If you plan to use OpenAI Whisper via the separate package (optional prerequisite mentioned):

```bash
pip install openai-whisper
```
Whisper is used for automatic audio transcription when you pass `--transcribe-audio`. [github](https://github.com/AlexMaximux/Carton-making)

## 5. Prepare your assets (images, audio, transcript)

The project is a “Modular Slideshow Video Generator & Whisper Transcriber” that works with:

- A folder of numerically named images like `1.jpg`, `2.png`, `10.jpeg`. [github](https://github.com/AlexMaximux/Carton-making)
- An audio file for narration (e.g. `./v/voiceover01.mp3`). [github](https://github.com/AlexMaximux/Carton-making)
- Either:
  - A transcript it generates from audio (`--transcribe-audio`), or  
  - A manual timestamped transcript file `[mm:ss] text...`. [github](https://github.com/AlexMaximux/Carton-making)

Example layout:

```bash
Carton-making/
  main.py
  v/
    1.jpg
    2.jpg
    3.jpg
    voiceover01.mp3
```

## 6. Run basic usage examples

All commands below assume you are in the repo root directory.

### a) Transcribe audio only

This produces `output_transcript.txt` and `output_words.json` in the audio directory. [github](https://github.com/AlexMaximux/Carton-making)

```bash
python main.py --transcribe-audio ./v/voiceover01.mp3
```

To set model and custom output paths:

```bash
python main.py \
  --transcribe-audio ./v/voiceover01.mp3 \
  --whisper-model medium \
  --save-transcript ./v/custom_transcript.txt \
  --save-word-timestamps ./v/custom_words.json
```
The CLI supports `tiny`, `base`, `small`, `medium`, `large` for `--whisper-model`, defaulting to `small`. [github](https://github.com/AlexMaximux/Carton-making)

### b) Fully automated: images + audio → video

This transcribes the audio and generates a complete slideshow video. [github](https://github.com/AlexMaximux/Carton-making)

```bash
python main.py \
  --images-dir ./v/ \
  --transcribe-audio ./v/voiceover01.mp3 \
  --audio ./v/voiceover01.mp3 \
  --output final.mp4
```

### c) Manual transcript mode

If you create your own transcript file like `transcript.txt` with timestamps and text, you can run:

```bash
python main.py \
  --images-dir ./images \
  --transcript ./transcript.txt \
  --audio ./voiceover.mp3 \
  --output output.mp4
```
This uses your timestamps to schedule slides and mux in audio. [github](https://github.com/AlexMaximux/Carton-making)

### d) Adjust audio offset

Delay audio by 2.5 seconds:

```bash
python main.py \
  -i ./images \
  -t ./transcript.txt \
  -a ./voiceover.mp3 \
  --audio-offset 2.5 \
  -o output.mp4
```

Start audio 1.5 seconds earlier (trim start):

```bash
python main.py \
  -i ./images \
  -t ./transcript.txt \
  -a ./voiceover.mp3 \
  --audio-offset -1.5 \
  -o output.mp4
```
Audio offset controls sync between audio and video; positive delays, negative trims. [github](https://github.com/AlexMaximux/Carton-making)

## 7. Useful CLI arguments (quick reference)

Some key flags supported by `main.py`: [github](https://github.com/AlexMaximux/Carton-making)

- `--images-dir` / `-i`: Folder with images.  
- `--transcribe-audio`: Audio file to transcribe via Whisper (exclusive with `--transcript`).  
- `--transcript` / `-t`: Manual transcript file path.  
- `--audio` / `-a`: Audio file to mux into final video.  
- `--output` / `-o`: Output video file path (default `output.mp4`).  
- `--resolution` / `-r`: Resolution like `1920x1080` (must be even numbers).  
- `--fps`: Output framerate (default 30).  
- `--on-mismatch`: `ask`, `truncate`, or `error` if image count differs from timestamp count.  

All of these are documented in the README’s CLI table. [github](https://github.com/AlexMaximux/Carton-making)

## 8. Run tests (optional)

To validate the setup:

```bash
pip install pytest
pytest
```
This runs the unit tests in the `tests/` directory. [github](https://github.com/AlexMaximux/Carton-making)

***

Would you prefer a small bash script or Makefile to automate the install and a typical “images + audio → video” run on your Ubuntu machine?


cd /opt/Carton-making
nano run_carton.sh
#!/usr/bin/env bash
set -e

cd /opt/Carton-making
source .venv/bin/activate
uvicorn api:app --host 0.0.0.0 --port 9000 --reload


# 1. بستن پروسه اشغال‌کننده پورت 8000
sudo fuser -k 8000/tcp
# مشاهده پروسه رو پورت 8000
sudo lsof -i :8000

# کشتن تمام نمونه‌های uvicorn
pkill -f uvicorn



pm2 list
pm2 carton-maker port 9000



curl http://localhost:9000/health
curl http://localhost:9000/health
curl -X POST "http://localhost:9000/transcribe" \
  -F "audio_file=@/path/to/voiceover.mp3" \
  -F "whisper_model=small"


curl -X POST "http://localhost:8000/generate-video" \
  -F "images_mode=zip" \
  -F "zip_file=@/path/to/images.zip" \
  -F "audio_file=@/path/to/voiceover.mp3" \
  -F "resolution=1920x1080" \
  -F "fps=30"


curl -o final.mp4 http://localhost:8000/download/{job_id}/video




python main.py \
  --images-dir ./images \
  --transcript ./transcript.txt \
  --audio ./voiceover.mp3 \
  --add-captions \
  --output output.mp4


