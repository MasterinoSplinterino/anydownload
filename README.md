# YouTube & Instagram Downloader Bot

This bot downloads videos from YouTube and Instagram using `yt-dlp`.

## Setup

1.  **Install Python** (if not already installed).
2.  **Install FFmpeg**:
    *   Download from [ffmpeg.org](https://ffmpeg.org/download.html).
    *   Extract and add the `bin` folder to your system PATH.
3.  **Get Telegram API Credentials** (Required for large file uploads):
    *   Go to [my.telegram.org](https://my.telegram.org) and log in.
    *   Click **API development tools**.
    *   Create a new application (enter any name/shortname).
    *   Copy **App api_id** and **App api_hash**.
    *   Open `config.py` and paste them there.
4.  **Install Dependencies**:
    ```bash
    python -m venv venv
    venv\Scripts\pip install -r requirements.txt
    ```
    *(Already done if you used the agent)*

## Running

Double-click `run.bat` or run:
```bash
venv\Scripts\python bot.py
```

## Features

*   **YouTube**: Select quality (1080p, 720p, 360p, Audio).
*   **Instagram**: Auto-download videos/reels.

## Note on spotDL
The user requested `spotDL` for the backend. `spotDL` is primarily for downloading Spotify music by finding matches on YouTube. For direct YouTube video downloading, we use `yt-dlp`, which is the underlying engine `spotDL` uses and is the industry standard for this task.
