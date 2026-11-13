#!/usr/bin/env python3
"""Joins a VIDEO=1 run's review videos into one journey video,
reports/videos/journey.mp4: every clip in run order, each after a 2s title
card "NN · <scenario> — <who>", desktop and phone clips padded onto one canvas,
the UI verifier's width (ui_verifier_width in .copier-answers.yml) by 900.

Needs ffmpeg (FFMPEG=<path>, else ffmpeg on PATH). The title cards are drawn
by Playwright's Chromium, so ffmpeg needs no text filter. Copy verbatim.
"""

import html
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ACCEPTANCE = Path(__file__).resolve().parents[1]
VIDEOS = ACCEPTANCE / "reports" / "videos"
CLIPS = VIDEOS / "clips.jsonl"
WORK = VIDEOS / ".journey"
OUT = VIDEOS / "journey.mp4"
CARD_SECONDS = 2
FPS = 25
H = 900


def verifier_width():
    try:
        answers = (ACCEPTANCE.parent / ".copier-answers.yml").read_text(encoding="utf-8")
    except OSError:
        return 1280
    found = re.search(r"^ui_verifier_width:\s*(\d+)\s*$", answers, re.MULTILINE)
    return int(found.group(1)) if found else 1280


W = verifier_width() + verifier_width() % 2  # libx264 needs even sizes


def fail(message):
    sys.stderr.write("video_journey: %s\n" % message)
    sys.exit(1)


def find_ffmpeg():
    candidates = [c for c in (os.environ.get("FFMPEG"), "ffmpeg", "/opt/homebrew/bin/ffmpeg") if c]
    tried = []
    for candidate in candidates:
        found = shutil.which(candidate)
        if not found:
            tried.append("%s: not found" % candidate)
            continue
        run = subprocess.run([found, "-hide_banner", "-version"], capture_output=True, text=True, check=False)
        if run.returncode == 0:
            return found
        said = (run.stderr or "").splitlines()
        tried.append("%s: %s" % (candidate, said[0] if said else "exit %d" % run.returncode))
    fail(
        "no working ffmpeg. Install it (Windows: winget install Gyan.FFmpeg; macOS: brew install ffmpeg; "
        "Linux: your package manager), or set FFMPEG=<path>.\n  tried: %s" % "\n         ".join(tried)
    )


def ffmpeg(binary, args):
    run = subprocess.run(
        [binary, "-hide_banner", "-loglevel", "error", "-y"] + args, capture_output=True, text=True, check=False
    )
    if run.returncode != 0:
        fail("ffmpeg %s\n%s" % (" ".join(args), run.stderr))


def main():
    binary = find_ffmpeg()
    if not CLIPS.is_file():
        fail("no %s: run the suite with VIDEO=1 first." % CLIPS)
    clips = [json.loads(line) for line in CLIPS.read_text(encoding="utf-8").splitlines() if line]
    clips = sorted((c for c in clips if (VIDEOS / c["file"]).is_file()), key=lambda c: (c["order"], c["file"]))
    if not clips:
        fail("the last VIDEO=1 run left no clips.")

    shutil.rmtree(WORK, ignore_errors=True)
    WORK.mkdir(parents=True)

    # Title cards, drawn as pictures.
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": W, "height": H})
        for i, clip in enumerate(clips):
            page.set_content(
                '<body style="margin:0;height:100vh;display:flex;flex-direction:column;justify-content:center;'
                "align-items:center;background:#111827;color:#f9fafb;font-family:system-ui,-apple-system,sans-serif;"
                'text-align:center">'
                '<div style="font-size:30px;opacity:.7;margin-bottom:18px">%s</div>'
                '<div style="font-size:46px;font-weight:700;max-width:1100px;line-height:1.25">%s</div>'
                '<div style="font-size:30px;opacity:.8;margin-top:22px">%s</div></body>'
                % (html.escape(clip["order"]), html.escape(clip["scenario"]), html.escape(clip["who"]))
            )
            page.screenshot(path=str(WORK / ("card-%d.png" % i)))
        browser.close()

    # Every part the same size, rate and format, so they join without re-encoding.
    same = "fps=%d,format=yuv420p,setsar=1" % FPS
    encode = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-an"]
    fit = "scale=%d:%d:force_original_aspect_ratio=decrease,pad=%d:%d:(ow-iw)/2:(oh-ih)/2:color=0x374151" % (W, H, W, H)
    parts = []
    for i, clip in enumerate(clips):
        card = WORK / ("card-%d.mp4" % i)
        ffmpeg(binary, ["-loop", "1", "-t", str(CARD_SECONDS), "-i", str(WORK / ("card-%d.png" % i)), "-vf", same] + encode + [str(card)])
        body = WORK / ("clip-%d.mp4" % i)
        ffmpeg(binary, ["-i", str(VIDEOS / clip["file"]), "-vf", "%s,%s" % (fit, same)] + encode + [str(body)])
        parts += [card, body]
        print("%s · %s — %s" % (clip["order"], clip["scenario"], clip["who"]))
    # Forward slashes: ffmpeg's list file reads a backslash as an escape.
    parts_list = WORK / "parts.txt"
    parts_list.write_text(
        "\n".join("file '%s'" % part.as_posix().replace("'", "'\\''") for part in parts), encoding="utf-8"
    )
    ffmpeg(binary, ["-f", "concat", "-safe", "0", "-i", str(parts_list), "-c", "copy", "-movflags", "+faststart", str(OUT)])
    shutil.rmtree(WORK, ignore_errors=True)
    print("wrote %s: %d clips" % (OUT, len(clips)))


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):  # scenario names are not always ASCII; a Windows console may be
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    main()
