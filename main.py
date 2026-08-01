#!/usr/bin/env python3
"""
CLI Entry Point for Modular Slideshow Video Generator
"""
import argparse
import sys
from pathlib import Path
from typing import List

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt

from modules.ffmpeg_engine import check_ffmpeg_installed
from modules.audio_muxer import check_ffprobe_installed
from modules.transcriber import (
    check_whisper_installed,
    transcribe_audio,
    format_segments_as_transcript,
    save_word_timestamps_json
)
from modules.timing_calculator import MismatchWarning
from modules.pipeline import SlideshowPipeline

console = Console()


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate a slideshow video synchronized with transcript timestamps & optional Whisper audio transcription."
    )
    parser.add_argument(
        "--images-dir", "-i",
        required=True,
        type=str,
        help="Path to folder containing numerically ordered images (1.jpg, 2.png, ...)"
    )
    parser.add_argument(
        "--transcript", "-t",
        default=None,
        type=str,
        help="Path to text transcript file containing bracketed timestamps like [m:ss] or [mm:ss]"
    )
    parser.add_argument(
        "--transcribe-audio",
        default=None,
        type=str,
        help="Path to audio file to transcribe automatically using OpenAI Whisper (mutually exclusive with --transcript)"
    )
    parser.add_argument(
        "--whisper-model",
        default="small",
        type=str,
        help="Whisper model size: tiny, base, small, medium, large (default: small for high word precision)"
    )
    parser.add_argument(
        "--save-transcript",
        default=None,
        type=str,
        help="Path to save generated text transcript file (default: output_transcript.txt)"
    )
    parser.add_argument(
        "--save-word-timestamps",
        default=None,
        type=str,
        help="Path to save word-level timestamps JSON file (default: output_words.json)"
    )
    parser.add_argument(
        "--output", "-o",
        default="output.mp4",
        type=str,
        help="Output video file path (default: output.mp4)"
    )
    parser.add_argument(
        "--audio", "-a",
        type=str,
        default=None,
        help="Optional path to audio file (mp3, wav, m4a, etc.) to multiplex into output video"
    )
    parser.add_argument(
        "--audio-offset",
        type=float,
        default=0.0,
        help="Audio start delay/advance offset in seconds (positive to delay audio, negative to trim audio)"
    )
    parser.add_argument(
        "--keep-temp",
        action="store_true",
        default=False,
        help="Keep intermediate raw silent video file when --audio is specified"
    )
    parser.add_argument(
        "--total-duration", "-d",
        type=float,
        default=None,
        help="Optional total duration for final image fallback (in seconds)"
    )
    parser.add_argument(
        "--resolution", "-r",
        default="1920x1080",
        type=str,
        help="Output video resolution WxH (default: 1920x1080, must be even dimensions)"
    )
    parser.add_argument(
        "--fps",
        type=int,
        default=30,
        help="Output video framerate (default: 30)"
    )
    parser.add_argument(
        "--on-mismatch",
        choices=["ask", "truncate", "error"],
        default="ask",
        help="Handling mode when timestamp count != image count (default: ask)"
    )

    return parser.parse_args()


def handle_interactive_mismatch(timestamps_count: int, images_count: int) -> str:
    """Prompts user when N != M in interactive terminal mode."""
    console.print()
    console.print(Panel(
        f"[bold yellow]⚠️ Mismatch Warning![/bold yellow]\n\n"
        f"Timestamps count in transcript ([bold cyan]{timestamps_count}[/bold cyan]) "
        f"does not match image count in directory ([bold cyan]{images_count}[/bold cyan]).",
        title="[bold red]Count Mismatch[/bold red]",
        border_style="yellow"
    ))

    k = min(timestamps_count, images_count)
    choice = Prompt.ask(
        "Choose how to proceed",
        choices=["continue", "abort"],
        default="continue"
    )

    if choice == "continue":
        console.print(f"[green]Continuing using the shorter count ({k} segments)...[/green]\n")
        return "truncate"
    else:
        console.print("[red]Operation aborted by user.[/red]")
        sys.exit(1)


def format_time(seconds: float) -> str:
    """Formats float seconds into M:SS.ms string."""
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{int(h):02d}:{int(m):02d}:{s:05.2f}"
    return f"{int(m):02d}:{s:05.2f}"


def main():
    args = parse_args()

    console.print(Panel.fit(
        "[bold cyan]Slideshow Video Generator[/bold cyan]\n"
        "[dim]Synchronizing image sequence with transcript timestamps, Whisper STT & audio[/dim]",
        border_style="cyan"
    ))

    # Validate input transcript / transcribe arguments
    if args.transcript and args.transcribe_audio:
        console.print("[bold red]Error:[/bold red] Cannot specify both --transcript and --transcribe-audio. Please specify only one.")
        sys.exit(1)

    if not args.transcript and not args.transcribe_audio:
        console.print("[bold red]Error:[/bold red] Missing transcript input! Please specify either --transcript <file> OR --transcribe-audio <audio_file>.")
        sys.exit(1)

    # 1. Verify FFmpeg & ffprobe
    try:
        ffmpeg_ver = check_ffmpeg_installed()
        ffprobe_bin = check_ffprobe_installed()
        console.print(f"✓ [green]FFmpeg Engine:[/green] {ffmpeg_ver}")
        console.print(f"✓ [green]ffprobe Utility:[/green] {ffprobe_bin}")
    except EnvironmentError as err:
        console.print(f"[bold red]Error:[/bold red] {err}")
        sys.exit(1)

    # 2. Handle automatic transcription if --transcribe-audio is set
    transcript_file_path = args.transcript

    if args.transcribe_audio:
        try:
            check_whisper_installed()
        except ImportError as err:
            console.print(f"[bold red]Error:[/bold red] {err}")
            sys.exit(1)

        console.print(f"🎙️  [bold yellow]Transcribing audio using Whisper model '{args.whisper_model}'...[/bold yellow]")
        console.print("[dim](Running on CPU/GPU, this may take a few moments depending on model size and audio length)[/dim]")

        with console.status(f"[bold green]Whisper is transcribing '{Path(args.transcribe_audio).name}'...[/bold green]"):
            res = transcribe_audio(args.transcribe_audio, model_size=args.whisper_model)

        # Build formatted transcript text
        formatted_txt = format_segments_as_transcript(res["segments"])

        # Determine transcript output path
        if args.save_transcript:
            t_path = Path(args.save_transcript).resolve()
        else:
            t_path = Path("output_transcript.txt").resolve()

        t_path.parent.mkdir(parents=True, exist_ok=True)
        t_path.write_text(formatted_txt, encoding='utf-8')
        transcript_file_path = str(t_path)

        # Save word-level timestamps JSON
        if args.save_word_timestamps:
            w_path = Path(args.save_word_timestamps).resolve()
        else:
            w_path = Path("output_words.json").resolve()

        save_word_timestamps_json(res["words"], w_path)

        console.print(Panel(
            f"[bold cyan]Whisper Model:[/bold cyan] {args.whisper_model}\n"
            f"[bold cyan]Segments Extracted:[/bold cyan] {len(res['segments'])}\n"
            f"[bold cyan]Word Timestamps Extracted:[/bold cyan] {len(res['words'])}\n"
            f"[bold cyan]Saved Transcript:[/bold cyan] [underline]{t_path}[/underline]\n"
            f"[bold cyan]Saved Word JSON:[/bold cyan] [underline]{w_path}[/underline]",
            title="[bold green]Speech-to-Text Transcription Report[/bold green]",
            border_style="green"
        ))

    pipeline = SlideshowPipeline()

    # 3. Execute pipeline
    try:
        with console.status("[bold green]Calculating timings and rendering video...[/bold green]"):
            segments, v_dur, a_dur, diff, was_extended, extend_by = pipeline.run(
                images_dir=args.images_dir,
                transcript_path=transcript_file_path,
                output_path=args.output,
                audio_path=args.audio,
                audio_offset=args.audio_offset,
                keep_temp=args.keep_temp,
                resolution=args.resolution,
                fps=args.fps,
                total_duration=args.total_duration,
                on_mismatch=args.on_mismatch,
                mismatch_resolver=handle_interactive_mismatch
            )

        # 4. Print schedule report table
        table = Table(title="[bold]Segment Schedule Report[/bold]", show_header=True, header_style="bold magenta")
        table.add_column("#", justify="right", style="dim")
        table.add_column("Image File", style="cyan")
        table.add_column("Start Time", justify="right")
        table.add_column("End Time", justify="right")
        table.add_column("Duration", justify="right", style="green")

        for idx, seg in enumerate(segments, 1):
            table.add_row(
                str(idx),
                Path(seg.image_path).name,
                format_time(seg.start_time),
                format_time(seg.end_time),
                f"{seg.duration:.2f}s"
            )

        console.print(table)

        # 5. Print Audio & Duration Summary Report
        if args.audio:
            diff_text = f"{diff:.2f}s"
            if was_extended:
                status_msg = f"\n[yellow]ℹ️ Video Extended:[/yellow] Video extended by {extend_by:.2f}s by freezing the last frame to match audio duration"
            elif v_dur > (a_dur or 0.0):
                status_msg = f"\n[yellow]ℹ️ Stream Sync:[/yellow] Video was trimmed to match audio track length (-shortest)"
            else:
                status_msg = ""

            console.print(Panel(
                f"[bold cyan]Audio Track:[/bold cyan] {Path(args.audio).name}\n"
                f"[bold cyan]Audio Offset:[/bold cyan] {args.audio_offset:.2f}s\n"
                f"[bold cyan]Raw Video Duration:[/bold cyan] {v_dur:.2f}s\n"
                f"[bold cyan]Audio Track Duration:[/bold cyan] {a_dur:.2f}s\n"
                f"[bold cyan]Duration Difference:[/bold cyan] {diff_text}"
                f"{status_msg}",
                title="[bold green]Audio Muxing Report[/bold green]",
                border_style="green"
            ))
        else:
            console.print(f"[bold green]Total Video Duration:[/bold green] [bold white]{v_dur:.2f}s[/bold white] [dim](Silent Mode)[/dim]\n")

        # 6. Final render status
        console.print(f"[bold green]Success![/bold green] Final slideshow video saved to: [underline cyan]{Path(args.output).resolve()}[/underline cyan]")

    except MismatchWarning as warn:
        resolved = handle_interactive_mismatch(warn.timestamps_count, warn.images_count)
        args.on_mismatch = resolved
        main()

    except Exception as err:
        console.print(f"[bold red]Error during slideshow generation:[/bold red] {err}")
        sys.exit(1)


if __name__ == "__main__":
    main()
