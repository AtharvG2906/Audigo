import os
import re
import shutil
import tempfile
from urllib.parse import urlparse

import imageio_ffmpeg
import yt_dlp
from flask import Flask, after_this_request, jsonify, render_template, request, send_file

app = Flask(__name__)
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
QUALITIES = {"320", "192", "128"}  # MP3 bitrates in kbps


class NoAudio(Exception):
    pass


def has_audio(info):
    """Return False only when we can tell for sure the media has no audio track."""
    entries = info.get("requested_formats") or [info]
    codecs = [f.get("acodec") for f in entries]
    if any(c not in (None, "none") for c in codecs):
        return True
    if all(c == "none" for c in codecs):
        # Selected format is silent; check whether any other format carries audio.
        return any(f.get("acodec") not in (None, "none") for f in info.get("formats") or [])
    return True  # unknown codec info — let ffmpeg decide


def is_instagram(url):
    host = (urlparse(url).hostname or "").lower()
    return host == "instagram.com" or host.endswith(".instagram.com")


INSTAGRAM_BLOCKED = ("private", "login", "log in", "cookies", "not available", "unavailable",
                     "empty media", "unable to extract", "rate-limit", "rate limit", "401", "403")


def safe_name(title):
    name = re.sub(r'[\\/:*?"<>|\r\n]+', "", title or "audio").strip()
    return (name[:120] or "audio") + ".mp3"


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/api/audio")
def get_audio():
    data = request.get_json(silent=True) or {}
    url = str(data.get("url", "")).strip()
    quality = str(data.get("quality", "320"))
    if not re.match(r"^https?://", url):
        return jsonify(error="Please paste a valid link starting with http:// or https://"), 400
    if quality not in QUALITIES:
        return jsonify(error="Please choose a valid audio quality."), 400

    workdir = tempfile.mkdtemp(prefix="audio_")

    @after_this_request
    def cleanup(response):
        response.call_on_close(lambda: shutil.rmtree(workdir, ignore_errors=True))
        return response

    opts = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(workdir, "%(id)s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "ffmpeg_location": FFMPEG,
        "max_filesize": 500 * 1024 * 1024,
        "postprocessors": [
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": quality}
        ],
    }

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if info.get("_type") == "playlist":
                entries = [e for e in info.get("entries") or [] if e]
                if not entries:
                    raise NoAudio()
                info = entries[0]
            if not has_audio(info):
                raise NoAudio()
            ydl.process_ie_result(info, download=True)
    except NoAudio:
        return jsonify(error="Audio not available for this link."), 404
    except yt_dlp.utils.DownloadError as e:
        msg = str(e).lower()
        app.logger.warning("yt-dlp failed for %s: %s", url, str(e)[:300])
        if is_instagram(url) and any(k in msg for k in INSTAGRAM_BLOCKED):
            return jsonify(error="Audio not available — this Instagram account is private "
                                 "or the post can't be accessed."), 403
        if any(k in msg for k in ("no video formats", "no audio", "requested format is not available",
                                  "does not pass filter", "there is no video")):
            return jsonify(error="Audio not available for this link."), 404
        if "unsupported url" in msg:
            return jsonify(error="Audio not available — this link isn't supported."), 404
        if any(k in msg for k in ("private", "login", "log in", "sign in", "cookies")):
            return jsonify(error="Audio not available — this content is private or requires login."), 403
        if any(k in msg for k in ("not available", "unavailable", "removed", "deleted")):
            return jsonify(error="Audio not available — this video is unavailable or was removed."), 404
        return jsonify(error="Audio not available — couldn't fetch this link."), 422
    except Exception:
        app.logger.exception("Unexpected error")
        return jsonify(error="Something went wrong. Please try again."), 500

    mp3s = [f for f in os.listdir(workdir) if f.endswith(".mp3")]
    if not mp3s:
        return jsonify(error="Audio not available for this link."), 404

    return send_file(
        os.path.join(workdir, mp3s[0]),
        mimetype="audio/mpeg",
        as_attachment=True,
        download_name=safe_name(info.get("title")),
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
