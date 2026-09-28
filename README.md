# YTranscript

Paste a video link, get the transcript.

YTranscript takes a YouTube link and gives you the spoken words as plain text,
subtitles (SRT / VTT), JSON or Markdown. It works from the terminal or from a
small web page that runs on your own computer. Nothing is sent anywhere except
to YouTube itself.

```
$ ytranscript https://youtu.be/dQw4w9WgXcQ
We're no strangers to love You know the rules and so do I
A full commitment's what I'm thinking of ...
```

## How it works (the short version)

1. **Find the video ID.** Every YouTube link, whatever its shape, contains an
   11-character ID like `dQw4w9WgXcQ`. We pull it out.
2. **Ask YouTube for captions.** Most videos have captions, either written by
   the uploader or generated automatically by YouTube. We download them with
   the `youtube-transcript-api` library. This takes about a second.
3. **Optional fallback: listen to the audio.** If a video has no captions at
   all, or the link is not YouTube (Vimeo, TikTok, a podcast page...), we can
   download the audio with `yt-dlp` and run it through **Whisper**, an
   open-source speech-recognition model. This is slower (roughly as long as the
   video on a laptop) and needs extra packages, so it is off by default.
4. **Format it.** The captions are turned into the format you asked for.

## Installation

You need Python 3.10 or newer. Check with:

```
python3 --version
```

Then, in a terminal, from the folder containing this README:

```bash
# 1. Create a "virtual environment": a private folder for this project's
#    packages, so they don't mix with anything else on your computer.
python3 -m venv .venv

# 2. Activate it (you do this once per terminal window).
source .venv/bin/activate          # macOS / Linux
.venv\Scripts\activate             # Windows (PowerShell or cmd)

# 3. Install YTranscript. The "-e" means "editable": if you change the code,
#    the change takes effect immediately, no reinstall needed.
pip install -e .
```

That gives you two commands: `ytranscript` (terminal) and `ytranscript-web`
(browser).

To also get the Whisper fallback for videos without captions:

```bash
pip install -e ".[whisper]"
```

The first time Whisper runs it downloads a model file (about 150 MB for the
default `base` model). No `ffmpeg` install is required.

## Using the terminal command

```bash
# Print the transcript as plain text
ytranscript https://www.youtube.com/watch?v=dQw4w9WgXcQ

# Add a timestamp at the start of every line
ytranscript https://youtu.be/dQw4w9WgXcQ --timestamps

# Save as subtitles. "-o auto" names the file after the video ID.
ytranscript https://youtu.be/dQw4w9WgXcQ --format srt --output song.srt
ytranscript https://youtu.be/dQw4w9WgXcQ -f vtt -o auto

# Other formats: json (keeps every timestamp), md (Markdown)
ytranscript https://youtu.be/dQw4w9WgXcQ -f json > transcript.json

# See which caption languages the video offers
ytranscript https://youtu.be/dQw4w9WgXcQ --list-languages

# Prefer Spanish, then English. If neither exists you get whatever the video has.
ytranscript https://youtu.be/dQw4w9WgXcQ --languages es,en

# Ask YouTube to machine-translate the captions into English
ytranscript https://youtu.be/dQw4w9WgXcQ --translate-to en

# Captions first; if there are none, transcribe the audio with Whisper
ytranscript https://youtu.be/dQw4w9WgXcQ --whisper-fallback

# Non-YouTube link: Whisper is the only option
ytranscript https://vimeo.com/123456 --whisper --whisper-model small
```

`ytranscript --help` lists every option.

Progress messages ("Fetching YouTube captions...") go to the terminal's
*error* stream, so `ytranscript URL > file.txt` still produces a clean file.
Add `-q` to silence them.

## Using the web page

```bash
ytranscript-web
```

Open <http://127.0.0.1:5000> in your browser, paste a link, choose a format,
click **Get transcript**. Read it on the page or press **Download**.
Press `Ctrl+C` in the terminal to stop the server.

The page only listens on your own machine. To change the port:
`YTRANSCRIPT_PORT=8080 ytranscript-web`.

## Using it from your own Python code

```python
from ytranscript import get_transcript, format_transcript

transcript = get_transcript("https://youtu.be/dQw4w9WgXcQ", languages=["en"])

print(transcript.language)            # "English"
print(transcript.is_generated)        # False = written by a human
print(len(transcript.segments))       # number of caption lines
print(transcript.segments[0].text)    # "We're no strangers to love"
print(transcript.segments[0].start)   # 0.0 (seconds)

print(format_transcript(transcript, "srt"))
```

## A tour of the code

Everything lives in the `ytranscript/` folder. Each file does one job and
has comments explaining *why*, not just *what*.

| File | Job |
|------|-----|
| `models.py` | The two data shapes: `Segment` (one caption line with start time and duration) and `Transcript` (all the segments plus facts about the video). |
| `errors.py` | Our own error types, so the rest of the program can show one friendly sentence instead of a stack trace. |
| `urls.py` | Turns any link shape (`watch?v=`, `youtu.be/`, `/shorts/`, `/embed/`, bare ID...) into the video ID. |
| `fetch.py` | Talks to YouTube, picks the best caption track (human-made before automatic, your languages before others), translates if asked, and converts library errors into ours. |
| `transcribe.py` | The optional Whisper fallback: download audio with `yt-dlp`, transcribe with `faster-whisper`. Imports its libraries lazily so the rest works without them. |
| `formats.py` | One small function per output format, plus a `FORMATS` table the CLI and web page both read. Adding a format is a one-line change here. |
| `pipeline.py` | The decision-maker: captions or Whisper? |
| `cli.py` | The `ytranscript` command. Reads the options, calls `get_transcript`, prints or saves. |
| `web.py` | The `ytranscript-web` page (Flask). The HTML lives inside the file so there is only one thing to read. |

`tests/` has a test for each of these. They never touch the internet: a fake
YouTube in `tests/conftest.py` hands back canned captions, so the tests run
in under a second anywhere.

## Running the tests

```bash
pip install -e ".[dev]"
pytest
```

You should see `100 passed`. Whenever you change something, run this again; if
it still says all passed, you probably didn't break anything.

## Troubleshooting

**"Captions are turned off for video ..."** The uploader disabled captions.
Use `--whisper-fallback` (after installing the whisper extras).

**"YouTube blocked the request"** YouTube sometimes refuses requests coming
from cloud servers, VPNs or after many requests in a row. Wait a bit, try from
a normal home connection, or use `--whisper` which downloads through a
different route.

**"Could not reach YouTube"** Your computer can't open a connection to
youtube.com. Check Wi-Fi, VPN, proxy or firewall.

**"... is not a YouTube link"** Only YouTube captions can be fetched directly.
For any other site add `--whisper`.

**Whisper is slow.** Use `--whisper-model tiny` for speed, `small` or
`medium` for accuracy. The default `base` is a fair middle ground.

## Ideas for next steps

- Batch mode: a text file of links, one transcript file each.
- Summaries or chapter detection on top of the transcript.
- Speaker labels (Whisper doesn't do this; it needs a "diarization" model).
