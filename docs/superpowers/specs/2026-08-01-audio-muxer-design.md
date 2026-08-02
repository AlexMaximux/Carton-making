# Design Specification: Audio Muxing & Last Frame Freeze Extension

## Overview
Updates the `audio_muxer` module to handle cases where the audio duration (after offset adjustment) is longer than the raw video duration (`effective_audio_dur > video_duration`). Instead of truncating the audio track with `-shortest`, the engine automatically extends the video by freezing the final video frame using the FFmpeg `tpad` filter.

## Requirements & Rules

1. **Effective Audio Duration Calculation**:
   - If `offset > 0`: `effective_audio_dur = audio_duration + offset`
   - If `offset < 0`: `effective_audio_dur = max(0.0, audio_duration - abs(offset))`
   - If `offset == 0`: `effective_audio_dur = audio_duration`

2. **Offset Argument Injection**:
   In **both** `tpad` extension branch and stream-copy branch, offset arguments are injected directly before `-i audio_path`:
   - `offset > 0`: `-itsoffset {offset}` before `-i audio_path`
   - `offset < 0`: `-ss {abs(offset)}` before `-i audio_path`

3. **Case 1: Audio Longer than Video (`effective_audio_dur > video_duration`)**:
   - `extend_by = effective_audio_dur - video_duration`
   - Applies video filter `tpad=stop_mode=clone:stop_duration={extend_by:.4f}`
   - Command structure:
     ```bash
     ffmpeg -y -i raw_video.mp4 [offset args] -i audio.mp3 \
       -filter_complex "[0:v]tpad=stop_mode=clone:stop_duration={extend_by:.4f}[v]" \
       -map "[v]" -map 1:a:0 \
       -c:v libx264 -preset medium -crf 23 -c:a aac output.mp4
     ```
   - Console Notice: `"Video extended by {extend_by:.2f}s by freezing the last frame to match audio duration"`

4. **Case 2: Video Longer than or Equal to Audio (`video_duration >= effective_audio_dur`)**:
   - Uses stream copy `-c:v copy` and `-c:a aac -shortest` (fast, no video re-encoding).
   - Command structure:
     ```bash
     ffmpeg -y -i raw_video.mp4 [offset args] -i audio.mp3 \
       -map 0:v:0 -map 1:a:0 \
       -c:v copy -c:a aac -shortest output.mp4
     ```

---

## Component Specification

### `modules/audio_muxer.py`
- Function return signature: Returns `(final_output_path, video_duration, audio_duration, duration_diff, was_extended, extend_by)` tuple.
- Branch condition: `effective_audio_dur > video_duration`.

### `main.py` CLI
- Updates `Audio Muxing Report` panel to display explicit notice when video frame freeze extension occurs versus stream shortening.

---

## Verification Plan

### Unit Tests (`tests/test_audio_muxer.py`)
1. `test_mux_audio_video_longer`: Assert `-c:v copy` and `-shortest` are used when `video_duration > effective_audio_dur`.
2. `test_mux_audio_audio_longer_tpad`: Assert `tpad=stop_mode=clone:stop_duration=...` and `-c:v libx264` are used when `effective_audio_dur > video_duration`.
3. `test_mux_audio_tpad_with_positive_offset`: Assert `-itsoffset` is included before `-i audio_path` AND `tpad` uses `extend_by` calculated from `effective_audio_dur`.
4. `test_mux_audio_tpad_with_negative_offset`: Assert `-ss` is included before `-i audio_path` AND `tpad` uses `extend_by` calculated from `effective_audio_dur`.
5. `test_mux_audio_equal_durations`: Assert `-c:v copy` and `-shortest` are used when durations match.

### Integration Verification
1. Create a 3s raw video asset and a 7s audio file asset.
2. Run `main.py` with `--audio`.
3. Probe output video with `ffprobe` and assert final duration is $\approx 7.0$ seconds (video extended by 4s).
