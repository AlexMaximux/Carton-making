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
from modules.audio_muxer import check_ffprobe_installed, probe_file_duration
from modules.transcriber import (
    check_whisper_installed,
    transcribe_audio,
    format_segments_as_transcript,
    save_word_timestamps_json
)
from modules.timing_calculator import MismatchWarning
from modules.pipeline import SlideshowPipeline

console = Console()


def parse_args(args_list=None):
    parser = argparse.ArgumentParser(
        description="Generate a slideshow video synchronized with transcript timestamps & optional Whisper audio transcription."
    )
    parser.add_argument(
        "--images-dir", "-i",
        default=None,
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
        help="Path to save generated text transcript file (default: output_transcript.txt in audio directory)"
    )
    parser.add_argument(
        "--save-word-timestamps",
        default=None,
        type=str,
        help="Path to save word-level timestamps JSON file (default: output_words.json in audio directory)"
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
    parser.add_argument(
        "--add-captions",
        action="store_true",
        default=False,
        help="Burn word-highlighted subtitles on output video based on words.json"
    )
    parser.add_argument(
        "--words-json",
        default=None,
        type=str,
        help="Path to word timestamps JSON file (default: output_words.json or from --transcribe-audio)"
    )
    parser.add_argument(
        "--caption-highlight-color",
        default="#FFD60A",
        type=str,
        help="Hex color for active word highlight (default: #FFD60A)"
    )
    parser.add_argument(
        "--caption-text-color",
        default="#FFFFFF",
        type=str,
        help="Hex color for inactive caption text (default: #FFFFFF)"
    )
    parser.add_argument(
        "--caption-outline-color",
        default="#000000",
        type=str,
        help="Hex color for caption outline (default: #000000)"
    )
    def parse_px_int(val: str) -> int:
        clean_val = str(val).strip().rstrip("px").rstrip("PX").strip()
        return int(clean_val)

    parser.add_argument(
        "--caption-font-size",
        default=None,
        type=parse_px_int,
        help="Caption font size in px, e.g. 85 or '85px' (default: auto ~5% of video height)"
    )
    parser.add_argument(
        "--caption-position",
        choices=["bottom", "top", "middle"],
        default="bottom",
        type=str,
        help="Caption vertical position (default: bottom)"
    )
    parser.add_argument(
        "--caption-margin-bottom",
        default=None,
        type=parse_px_int,
        help="Bottom margin in px, e.g. 80 or '80px' (default: auto ~8% of video height)"
    )
    parser.add_argument(
        "--caption-max-words-per-line",
        default=5,
        type=int,
        help="Maximum words per subtitle line (default: 5)"
    )
    parser.add_argument(
        "--caption-font-name",
        default="Arial Black",
        type=str,
        help="Font family name for captions (default: Arial Black)"
    )

    return parser.parse_args(args_list)


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


def main(args_list=None):
    args = parse_args(args_list)

    console.print(Panel.fit(
        "[bold cyan]Slideshow Video Generator & Whisper Transcriber[/bold cyan]\n"
        "[dim]Synchronizing image sequence with transcript timestamps, Whisper STT & audio[/dim]",
        border_style="cyan"
    ))

    # Validate input transcript / transcribe arguments
    if args.transcript and args.transcribe_audio:
        console.print("[bold red]Error:[/bold red] Cannot specify both --transcript and --transcribe-audio. Please specify only one.")
        sys.exit(1)

    if not args.transcript and not args.transcribe_audio:
        console.print("[bold red]Error:[/bold red] Missing input! Please specify either --transcribe-audio <audio_file> (transcribe-only or full mode) OR --images-dir <dir> with --transcript <file>.")
        sys.exit(1)

    if not args.transcribe_audio and not args.images_dir:
        console.print("[bold red]Error:[/bold red] Missing --images-dir argument for manual transcript mode!")
        sys.exit(1)

    # Audio directory for default save locations
    audio_path_obj = Path(args.transcribe_audio).resolve() if args.transcribe_audio else None
    audio_dir = audio_path_obj.parent if audio_path_obj else Path.cwd()

    # Determine save paths
    if args.save_transcript:
        t_save_path = Path(args.save_transcript).resolve()
    else:
        t_save_path = audio_dir / "output_transcript.txt"

    if args.save_word_timestamps:
        w_save_path = Path(args.save_word_timestamps).resolve()
    else:
        w_save_path = audio_dir / "output_words.json"

    # MODE 1: Standalone Transcribe-Only Mode (No --images-dir provided)
    if args.transcribe_audio and not args.images_dir:
        try:
            check_whisper_installed()
            ffprobe_bin = check_ffprobe_installed()
            console.print(f"✓ [green]ffprobe Utility:[/green] {ffprobe_bin}")
        except (ImportError, EnvironmentError) as err:
            console.print(f"[bold red]Error:[/bold red] {err}")
            sys.exit(1)

        audio_dur = probe_file_duration(audio_path_obj)

        console.print(f"\n🎙️  [bold yellow]Running Standalone Transcribe-Only Mode...[/bold yellow]")
        console.print(f"[bold cyan]Target Audio File:[/bold cyan] [underline]{audio_path_obj}[/underline]")
        console.print(f"[bold cyan]Whisper Model:[/bold cyan] {args.whisper_model}")
        console.print("[dim](Running speech-to-text on CPU/GPU, this may take a few moments)[/dim]")

        with console.status(f"[bold green]Whisper is transcribing '{audio_path_obj.name}'...[/bold green]"):
            res = transcribe_audio(audio_path_obj, model_size=args.whisper_model)

        formatted_txt = format_segments_as_transcript(res["segments"])
        t_save_path.parent.mkdir(parents=True, exist_ok=True)
        t_save_path.write_text(formatted_txt, encoding='utf-8')

        save_word_timestamps_json(res["words"], w_save_path)

        console.print(Panel(
            f"[bold cyan]Input Audio File:[/bold cyan] {audio_path_obj.name}\n"
            f"[bold cyan]Total Audio Duration:[/bold cyan] {audio_dur:.2f}s\n"
            f"[bold cyan]Whisper Model:[/bold cyan] {args.whisper_model}\n"
            f"[bold cyan]Segments Extracted:[/bold cyan] {len(res['segments'])}\n"
            f"[bold cyan]Word Timestamps Extracted:[/bold cyan] {len(res['words'])}\n\n"
            f"[bold green]Saved Transcript:[/bold green] [underline]{t_save_path}[/underline]\n"
            f"[bold green]Saved Word JSON:[/bold green] [underline]{w_save_path}[/underline]",
            title="[bold green]Transcribe-Only Summary Report[/bold green]",
            border_style="green"
        ))
        console.print("[bold green]Success![/bold green] Standalone transcription complete.")
        return 0

    # MODE 2 & 3: Video Slideshow Generation (Requires --images-dir)
    try:
        ffmpeg_ver = check_ffmpeg_installed()
        ffprobe_bin = check_ffprobe_installed()
        console.print(f"✓ [green]FFmpeg Engine:[/green] {ffmpeg_ver}")
        console.print(f"✓ [green]ffprobe Utility:[/green] {ffprobe_bin}")
    except EnvironmentError as err:
        console.print(f"[bold red]Error:[/bold red] {err}")
        sys.exit(1)

    transcript_file_path = args.transcript

    if args.transcribe_audio:
        try:
            check_whisper_installed()
        except ImportError as err:
            console.print(f"[bold red]Error:[/bold red] {err}")
            sys.exit(1)

        console.print(f"\n🎙️  [bold yellow]Transcribing audio using Whisper model '{args.whisper_model}'...[/bold yellow]")
        console.print("[dim](Running on CPU/GPU, this may take a few moments depending on model size and audio length)[/dim]")

        with console.status(f"[bold green]Whisper is transcribing '{audio_path_obj.name}'...[/bold green]"):
            res = transcribe_audio(audio_path_obj, model_size=args.whisper_model)

        formatted_txt = format_segments_as_transcript(res["segments"])
        t_save_path.parent.mkdir(parents=True, exist_ok=True)
        t_save_path.write_text(formatted_txt, encoding='utf-8')
        transcript_file_path = str(t_save_path)

        save_word_timestamps_json(res["words"], w_save_path)

        console.print(Panel(
            f"[bold cyan]Whisper Model:[/bold cyan] {args.whisper_model}\n"
            f"[bold cyan]Segments Extracted:[/bold cyan] {len(res['segments'])}\n"
            f"[bold cyan]Word Timestamps Extracted:[/bold cyan] {len(res['words'])}\n"
            f"[bold cyan]Saved Transcript:[/bold cyan] [underline]{t_save_path}[/underline]\n"
            f"[bold cyan]Saved Word JSON:[/bold cyan] [underline]{w_save_path}[/underline]",
            title="[bold green]Speech-to-Text Transcription Report[/bold green]",
            border_style="green"
        ))

    pipeline = SlideshowPipeline()

    words_json_path = None
    if args.add_captions:
        if args.words_json:
            words_json_path = args.words_json
        elif args.transcribe_audio:
            words_json_path = str(w_save_path)
        else:
            possible_path = audio_dir / "output_words.json"
            if possible_path.is_file():
                words_json_path = str(possible_path)
            elif Path("output_words.json").is_file():
                words_json_path = "output_words.json"
            else:
                console.print(
                    "[bold red]Error:[/bold red] --add-captions requires a valid words JSON file. "
                    "Please specify --words-json <path> or run with --transcribe-audio."
                )
                sys.exit(1)

    caption_config = {
        "font_name": args.caption_font_name,
        "font_size": args.caption_font_size,
        "highlight_color": args.caption_highlight_color,
        "text_color": args.caption_text_color,
        "outline_color": args.caption_outline_color,
        "position": args.caption_position,
        "margin_v": args.caption_margin_bottom,
        "max_words_per_line": args.caption_max_words_per_line
    } if args.add_captions else None

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
                mismatch_resolver=handle_interactive_mismatch,
                add_captions=args.add_captions,
                words_json_path=words_json_path,
                caption_config=caption_config
            )

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

        if args.add_captions:
            console.print(Panel(
                f"[bold cyan]Subtitles Mode:[/bold cyan] Word-Highlighted Subtitles\n"
                f"[bold cyan]Words JSON Source:[/bold cyan] {words_json_path}\n"
                f"[bold cyan]Highlight Color:[/bold cyan] {args.caption_highlight_color}\n"
                f"[bold cyan]Text Color:[/bold cyan] {args.caption_text_color}\n"
                f"[bold cyan]Outline Color:[/bold cyan] {args.caption_outline_color}\n"
                f"[bold cyan]Position:[/bold cyan] {args.caption_position} (margin: {args.caption_margin_bottom}px)",
                title="[bold green]Caption Generation Report[/bold green]",
                border_style="green"
            ))

        console.print(f"[bold green]Success![/bold green] Final slideshow video saved to: [underline cyan]{Path(args.output).resolve()}[/underline cyan]")
        return 0

    except MismatchWarning as warn:
        resolved = handle_interactive_mismatch(warn.timestamps_count, warn.images_count)
        args.on_mismatch = resolved
        return main(args_list)

    except Exception as err:
        console.print(f"[bold red]Error during slideshow generation:[/bold red] {err}")
        sys.exit(1)


if __name__ == "__main__":
    main()
