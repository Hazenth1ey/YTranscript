"""The ``ytranscript`` terminal command.

Examples::

    ytranscript https://youtu.be/dQw4w9WgXcQ
    ytranscript https://youtu.be/dQw4w9WgXcQ --format srt --output song.srt
    ytranscript https://youtu.be/dQw4w9WgXcQ --languages es,en
    ytranscript https://youtu.be/dQw4w9WgXcQ --translate-to en
    ytranscript https://youtu.be/dQw4w9WgXcQ --list-languages
    ytranscript https://vimeo.com/123456 --whisper --whisper-model small

How it works: ``argparse`` (Python's built-in option parser) reads the words
you typed after ``ytranscript``, we call ``get_transcript`` with them, and
print or save the result. Any ``TranscriptError`` is shown as a one-line
message and the program exits with status 1 (the Unix convention for
"something went wrong").
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .errors import TranscriptError
from .fetch import list_available_languages
from .formats import FORMATS, extension_for, format_transcript
from .pipeline import get_transcript
from .transcribe import DEFAULT_WHISPER_MODEL, WHISPER_MODELS
from .urls import extract_video_id, is_youtube_url


def build_parser() -> argparse.ArgumentParser:
    """Describe every option the command accepts (also powers ``--help``)."""
    parser = argparse.ArgumentParser(
        prog="ytranscript",
        description="Generate a transcript from a video link (YouTube captions, or Whisper speech-to-text).",
    )
    parser.add_argument("url", help="Video link, e.g. https://youtu.be/dQw4w9WgXcQ")
    parser.add_argument(
        "-f", "--format",
        choices=list(FORMATS),
        default="txt",
        help="Output format (default: txt). " + "; ".join(f"{k}: {v[2]}" for k, v in FORMATS.items()),
    )
    parser.add_argument(
        "-o", "--output",
        metavar="FILE",
        help="Save to this file instead of printing. Use '-o auto' to name it after the video ID.",
    )
    parser.add_argument(
        "-l", "--languages",
        default="en",
        help="Comma-separated language codes to prefer, in order (default: en).",
    )
    parser.add_argument(
        "--translate-to",
        metavar="CODE",
        help="Ask YouTube to machine-translate the captions into this language, e.g. en.",
    )
    parser.add_argument(
        "-t", "--timestamps",
        action="store_true",
        help="For txt format: put a [m:ss] timestamp before every line.",
    )
    parser.add_argument(
        "--list-languages",
        action="store_true",
        help="Just show which caption languages the video offers, then exit.",
    )
    parser.add_argument(
        "--whisper",
        action="store_true",
        help="Skip captions and transcribe the audio with Whisper (needs optional deps).",
    )
    parser.add_argument(
        "--whisper-fallback",
        action="store_true",
        help="Try captions first; if the video has none, transcribe the audio with Whisper.",
    )
    parser.add_argument(
        "--whisper-model",
        choices=WHISPER_MODELS,
        default=DEFAULT_WHISPER_MODEL,
        help=f"Whisper model size (default: {DEFAULT_WHISPER_MODEL}). Bigger = slower but more accurate.",
    )
    parser.add_argument(
        "--whisper-language",
        metavar="CODE",
        help="Force Whisper to this language instead of auto-detecting.",
    )
    parser.add_argument("-q", "--quiet", action="store_true", help="Don't print progress messages.")
    parser.add_argument("--version", action="version", version=f"ytranscript {__version__}")
    return parser


def _output_path(args: argparse.Namespace) -> Path | None:
    """Work out where to save, or None to print to the screen."""
    if not args.output:
        return None
    if args.output == "auto":
        stem = extract_video_id(args.url) if is_youtube_url(args.url) else "transcript"
        return Path(stem + extension_for(args.format))
    return Path(args.output)


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns the exit code (0 = success)."""
    parser = build_parser()
    args = parser.parse_args(argv)

    # Progress messages go to *stderr* so they never mix with the transcript
    # on stdout. That means ``ytranscript URL > file.txt`` still gives a clean file.
    def progress(msg: str) -> None:
        if not args.quiet:
            print(msg, file=sys.stderr)

    try:
        if args.list_languages:
            tracks = list_available_languages(args.url)
            if not tracks:
                print("This video has no captions.")
                return 0
            print(f"{'code':<8} {'language':<28} {'type':<10} translatable")
            for t in tracks:
                kind = "auto" if t["is_generated"] else "manual"
                print(f"{t['language_code']:<8} {t['language']:<28} {kind:<10} {'yes' if t['is_translatable'] else 'no'}")
            return 0

        languages = [code.strip() for code in args.languages.split(",") if code.strip()]

        transcript = get_transcript(
            args.url,
            languages=languages,
            translate_to=args.translate_to,
            use_whisper=args.whisper,
            whisper_fallback=args.whisper_fallback,
            whisper_model=args.whisper_model,
            whisper_language=args.whisper_language,
            progress=progress,
        )
        rendered = format_transcript(transcript, args.format, timestamps=args.timestamps)

        path = _output_path(args)
        if path is None:
            sys.stdout.write(rendered)
        else:
            path.write_text(rendered, encoding="utf-8")
            progress(
                f"Saved {len(transcript.segments)} lines ({transcript.language}, "
                f"{'auto' if transcript.is_generated else 'manual'}) to {path}"
            )
        return 0

    except TranscriptError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        return 130


if __name__ == "__main__":  # lets ``python -m ytranscript.cli`` work too
    sys.exit(main())
