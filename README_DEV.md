# 🎥 AnyDownload Pro Bot

A powerful Telegram bot for downloading videos from **YouTube** and **Instagram** with high-quality support and large file handling capabilities.

## 🚀 Features

*   **YouTube Downloader**:
    *   Supports resolutions up to **1080p**.
    *   Quality selection menu (1080p, 720p, 360p, Audio Only).
    *   Uses `yt-dlp` for reliable extraction.
*   **Instagram Downloader**:
    *   Downloads Reels, Videos, and Posts.
    *   Auto-detects Instagram links.
*   **Large File Support (>50MB)**:
    *   Bypasses the standard Telegram Bot API limit (50MB).
    *   Uses **Pyrogram (MTProto)** to upload files up to **2GB** directly to Telegram.
*   **Smart Error Handling**:
    *   Graceful fallbacks for missing FFmpeg.
    *   Automatic retry mechanisms.

## 🛠 Tech Stack

*   **Python 3.11+**
*   **aiogram 3.x**: Modern, asynchronous framework for the Telegram Bot API.
*   **Pyrogram**: MTProto client for heavy lifting (large file uploads).
*   **yt-dlp**: The industry-standard media downloader engine.
*   **FFmpeg**: Required for merging video/audio streams for high-quality downloads.

## ⚙️ Installation & Setup

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/yourusername/any-download-bot.git
    cd any-download-bot
    ```

2.  **Install FFmpeg**:
    *   **Windows**: `winget install "FFmpeg (Essentials Build)"` (or download from ffmpeg.org).
    *   **Linux**: `sudo apt install ffmpeg`
    *   **macOS**: `brew install ffmpeg`

3.  **Set up Virtual Environment**:
    ```bash
    python -m venv venv
    # Windows
    venv\Scripts\activate
    # Linux/macOS
    source venv/bin/activate
    ```

4.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

5.  **Configuration**:
    *   Open `config.py`.
    *   Add your **Bot Token** (from @BotFather).
    *   Add your **API_ID** and **API_HASH** (from my.telegram.org) to enable large file uploads.

6.  **Run the Bot**:
    ```bash
    python bot.py
    ```

## 📝 License

This project is open-source and available under the MIT License.
