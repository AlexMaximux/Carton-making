"""
FFmpeg Engine Module
Handles FFmpeg availability verification, concat demuxer file generation,
and executing FFmpeg slideshow video rendering.
"""
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import List, Tuple, Union
from modules.timing_calculator import ImageSegment


def check_ffmpeg_installed() -> str:
    """
    Checks if 'ffmpeg' is available in the system PATH.
    Returns the version string if installed, or raises EnvironmentError with installation guide.
    """
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        raise EnvironmentError(
            "FFmpeg is not installed or not found in your system PATH.\n"
            "Please install FFmpeg:\n"
            "  - macOS: brew install ffmpeg\n"
            "  - Ubuntu/Debian: sudo apt update && sudo apt install ffmpeg\n"
            "  - Windows: choco install ffmpeg OR download from https://ffmpeg.org/download.html"
        )
    try:
        res = subprocess.run(
            [ffmpeg_bin, "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        first_line = res.stdout.splitlines()[0] if res.stdout else "FFmpeg available"
        return first_line
    except Exception as e:
        raise EnvironmentError(f"Error checking FFmpeg version: {e}")


def parse_and_validate_resolution(resolution_str: str) -> Tuple[int, int]:
    """
    Parses resolution string (e.g. '1920x1080') and validates that both width and height are even integers.
    H.264 (libx264) requires even dimensions.
    """
    try:
        parts = resolution_str.lower().strip().split('x')
        if len(parts) != 2:
            raise ValueError()
        w, h = int(parts[0]), int(parts[1])
        if w <= 0 or h <= 0:
            raise ValueError()
    except ValueError:
        raise ValueError(
            f"Invalid resolution format: '{resolution_str}'. Expected format like '1920x1080' or '1280x720'."
        )

    if w % 2 != 0 or h % 2 != 0:
        raise ValueError(
            f"Resolution '{w}x{h}' contains odd dimensions. H.264 video codec requires even dimensions "
            f"(e.g., width and height divisible by 2)."
        )

    return w, h


def build_concat_file_content(segments: List[ImageSegment]) -> str:
    """
    Generates content for FFmpeg concat demuxer file.
    Each file entry is followed by its duration in seconds.
    The last file entry is repeated at the end to ensure FFmpeg honors its duration.
    """
    lines = []
    for seg in segments:
        # Escape single quotes in file paths for FFmpeg concat demuxer
        escaped_path = seg.image_path.replace("'", "'\\''")
        lines.append(f"file '{escaped_path}'")
        lines.append(f"duration {seg.duration:.4f}")

    if segments:
        last_escaped = segments[-1].image_path.replace("'", "'\\''")
        lines.append(f"file '{last_escaped}'")

    return "\n".join(lines) + "\n"


def render_slideshow(
    segments: List[ImageSegment],
    output_path: Union[str, Path],
    resolution: str = "1920x1080",
    fps: int = 30,
    additional_filters: List[str] = None
) -> Path:
    """
    Executes FFmpeg concat demuxer to render a slideshow video from ImageSegment list.

    Filter chain used:
    scale=W:H:force_original_aspect_ratio=decrease,pad=W:H:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,fps=FPS,format=yuv420p
    """
    check_ffmpeg_installed()
    w, h = parse_and_validate_resolution(resolution)
    out_file = Path(output_path).resolve()
    out_file.parent.mkdir(parents=True, exist_ok=True)

    concat_content = build_concat_file_content(segments)

    # Write temporary concat list file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as tmp:
        tmp.write(concat_content)
        tmp_path = tmp.name

    try:
        total_dur = segments[-1].end_time if segments else 0.0

        # Build video filter chain
        base_filter = (
            f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
            f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black,"
            f"setsar=1,"
            f"fps={fps},"
            f"format=yuv420p"
        )
        if additional_filters:
            full_filter = base_filter + "," + ",".join(additional_filters)
        else:
            full_filter = base_filter

        cmd = [
            "ffmpeg",
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", tmp_path,
            "-t", f"{total_dur:.4f}",
            "-vf", full_filter,
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            str(out_file)
        ]

        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg rendering failed:\n{result.stderr}")

        return out_file

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
