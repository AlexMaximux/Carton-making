# Voice-to-Video Slideshow Generator with Transcription and Captions

A modular Python CLI and FastAPI application for building narrated slideshow videos from audio, transcript timing, and generated images.

The workflow has **two stages involving this app**:

1. Use the app first to convert voice/audio into a timed transcript.
2. Use that transcript outside the app with AI to generate matching images.
3. Put the generated images into a folder.
4. Use the app again to combine the images, transcript, and audio into a final synchronized video.
5. Optionally add captions to the output video.

***

## Main Idea

This app is built for a workflow where the **voice comes first**.

You first give the app an audio file. It converts that audio into a timed transcript. Then that transcript is used outside the app to generate images with another AI system or script. After the images are ready, this app is used again to assemble the final video using:

- the generated images,
- the transcript timestamps,
- and the original audio.

So the full pipeline is:

**voice -> timed transcript -> external AI image generation -> image folder -> final video**

***

## Workflow

### Step 1: Convert Voice to Timed Transcript
First, use the app to transcribe the voiceover audio.

This step produces:

- A timed transcript file such as `transcript.txt`
- Optionally a `words.json` file for word-level timing

Example:

```bash
python main.py --transcribe-audio ./voiceover.mp3
```

This transcript becomes the instruction/timing source for the next step.

### Step 2: Generate Images Outside the App
Use the timed transcript with an external AI image generator, script, or workflow to create pictures that match the spoken content.

This part happens **outside** this app.

After the images are generated, place them in a folder such as:

```text
./images/
```

Example filenames:

```text
1.jpg
2.jpg
3.jpg
10.jpg
```

### Step 3: Create the Final Video
After the transcript and images are ready, use the app again to generate the video.

```bash
python main.py \
  --images-dir ./images \
  --transcript ./transcript.txt \
  --audio ./voiceover.mp3 \
  --add-captions \
  --output output.mp4
```

The app will:

- Sort the images numerically.
- Parse transcript timestamps.
- Calculate how long each image should be shown.
- Render the slideshow video.
- Merge the original audio.
- Optionally burn captions into the final output.

***

## What This App Does

This application is responsible for **two important parts** of the pipeline:

### 1. Voice to timed transcript
It can convert audio into a transcript with timestamps.

### 2. Images + transcript + audio to final video
It can assemble a final slideshow video by using transcript timing to control image durations.

### 3. Optional caption generation
It can add subtitles or word-highlighted captions to the output video.

***

## What This App Does Not Do

This app does **not** generate images by itself.

Image generation happens between the two app stages, using another AI model, image generation tool, or custom script based on the transcript created in Step 1.

***

## Features

- **Audio transcription** using Whisper.
- **Timed transcript generation** from voice input.
- **Optional word-level timestamps** via `words.json`.
- **Transcript-driven image timing** for video generation.
- **Numeric image sorting** using filenames like `1.jpg`, `2.jpg`, `10.jpg`.
- **Flexible transcript timestamp parsing**.
- **FFmpeg-based slideshow rendering**.
- **Audio muxing** to sync the final video with the original voiceover.
- **Optional caption burn-in**.
- **CLI support**.
- **FastAPI REST API support**.
- **Modular pipeline architecture**.

***

## Typical End-to-End Flow

1. Record or prepare `voiceover.mp3`.
2. Use this app to transcribe the audio into `transcript.txt`.
3. Send that transcript to an external AI workflow to generate images.
4. Save the generated images into `./images`.
5. Use this app again with `--images-dir`, `--transcript`, and `--audio` to render the final video.
6. Optionally add captions during video generation.

***

## Prerequisites

1. **Python 3.8+**
2. **FFmpeg** and **ffprobe** installed and available in system PATH.
3. *(Optional but recommended for transcription)* **OpenAI Whisper**

Install dependencies:

```bash
pip install -r requirements.txt
```

Install Whisper if needed:

```bash
pip install openai-whisper
```

***

## Installation

1. Clone or download the repository.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

***

## CLI Usage

### 1. Transcribe Audio

```bash
python main.py --transcribe-audio ./voiceover.mp3
```

### 2. Generate Final Video

```bash
python main.py \
  --images-dir ./images \
  --transcript ./transcript.txt \
  --audio ./voiceover.mp3 \
  --output output.mp4
```

### 3. Generate Final Video with Captions

```bash
python main.py \
  --images-dir ./images \
  --transcript ./transcript.txt \
  --audio ./voiceover.mp3 \
  --add-captions \
  --output output.mp4
```

### Caption Options

- `--add-captions`: Enable subtitle burn-in.
- `--words-json`: Path to a word-level timestamps JSON file.
- `--caption-highlight-color`: Highlight color for the active word.
- `--caption-text-color`: Normal caption text color.
- `--caption-outline-color`: Caption outline color.
- `--caption-font-size`: Caption font size.
- `--caption-position`: `bottom`, `middle`, or `top`.
- `--caption-margin-bottom`: Bottom margin for captions.
- `--caption-max-words-per-line`: Maximum words per line.
- `--caption-font-name`: Caption font family.

***

## REST API Usage

### Start the Server

```bash
uvicorn api:app --host 0.0.0.0 --port 8000 --reload
```

Swagger UI is available at:

`http://localhost:8000/docs`

### Main API Capabilities

- Submit transcription jobs.
- Download transcript outputs.
- Submit final video generation jobs.
- Upload images, transcript, and audio.
- Download the generated video.

***

## Example Pipeline

### Stage A: Inside This App

Input:

- `voiceover.mp3`

Output:

- `transcript.txt`
- optional `words.json`

### Stage B: Outside This App

Input:

- `transcript.txt`

Output:

- AI-generated images saved into `./images`

### Stage C: Inside This App Again

Input:

- `./images`
- `transcript.txt`
- `voiceover.mp3`

Output:

- `output.mp4`
- optional captioned video

***

## Project Structure

```text
.
├── main.py                       # CLI entry point
├── api.py                        # FastAPI REST API
├── modules/
│   ├── transcript_parser.py      # Parse transcript timestamps
│   ├── timing_calculator.py      # Calculate image durations from transcript timing
│   ├── ffmpeg_engine.py          # Render slideshow video with FFmpeg
│   ├── audio_muxer.py            # Merge audio with final video
│   ├── transcriber.py            # Audio transcription and word timestamps
│   ├── caption_generator.py      # Generate captions/subtitles
│   └── pipeline.py               # Main workflow orchestrator
├── tests/
├── requirements.txt
└── README.md
```

***

## Use Cases

This app is useful for:

- Voice-first AI video pipelines.
- Narrated story video generation.
- Educational or explainer slideshow creation.
- Social media automation workflows.
- Captioned slideshow video rendering.

***

## Running Tests

```bash
pytest
```
EOF && sed -n '1,220p' output/README.md | head -n 80