# Audigo

Audio downloader for any public video link. Paste a link from YouTube, Instagram, X, TikTok, Facebook, Vimeo, SoundCloud, and [many more](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md), choose 320, 192 or 128 kbps, and download the audio as an MP3.

Built with Flask + yt-dlp. ffmpeg is bundled through `imageio-ffmpeg`, so you don't need to install it separately.

## Run locally

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python app.py          # http://localhost:5000  (set PORT=xxxx to change)
```

## Deploy (Render / Railway / any VPS)

- Build: `pip install -r requirements.txt`
- Start: `gunicorn -w 2 -t 300 -b 0.0.0.0:$PORT app:app`

## Notes

- Keep yt-dlp up to date (`pip install -U yt-dlp`). Sites change often and old versions stop working.
- Private posts, and some Instagram content, need a login. Those links show "Audio not available".
- Only download content you have the right to use.
