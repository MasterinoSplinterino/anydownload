# 🎥 AnyDownload Pro Bot

A powerful, professional Telegram bot for downloading high-quality videos and music from **YouTube**, **Instagram**, and **Spotify**.

Built with Python, `aiogram`, `yt-dlp`, and `Pyrogram`.

## 🚀 Features

### 📺 Video & Audio Downloading
*   **YouTube**:
    *   Download videos in **1080p**, **720p**, or **360p**.
    *   Extract audio (MP3/M4A).
    *   Supports Shorts and regular videos.
*   **Instagram**:
    *   Download **Reels**, **Stories**, and **Posts**.
    *   Automatic link detection.
*   **Spotify**:
    *   Download tracks as high-quality audio files.
    *   Includes metadata and cover art (via `spotDL`).

### ⚡ Advanced Capabilities
*   **Large File Support (up to 2GB)**:
    *   Bypasses the standard 50MB bot API limit.
    *   Uses a separate **MTProto process** (`uploader.py`) to upload large files directly to Telegram.
    *   Does **not** block the bot while uploading.
*   **Smart Fallback**:
    *   If a file is >2GB (rare), it uploads to **Catbox.moe** and sends a link.
*   **Auto-Cleanup**:
    *   Automatically deletes files after sending.
    *   Background task cleans up "stuck" files every 10 minutes.

### 🛡️ Security & Administration
*   **Whitelist System**: Only allowed users can use the bot.
*   **Admin Panel**:
    *   Admin (ID 177036997) has full access.
    *   Command `/add @username` to instantly add new users to the whitelist.
*   **Secure Config**: API keys are stored in `.env`.

---

## 🛠 Prerequisites

1.  **Python 3.10+**
2.  **FFmpeg**: Required for video merging and audio conversion.
    *   **Windows**: `winget install "FFmpeg (Essentials Build)"`
    *   **Linux**: `sudo apt install ffmpeg`
    *   **macOS**: `brew install ffmpeg`
3.  **Telegram API Credentials**:
    *   Get `API_ID` and `API_HASH` from [my.telegram.org](https://my.telegram.org) (required for large file uploads).

---

## ⚙️ Installation

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/MasterinoSplinterino/anydownload.git
    cd anydownload
    ```

2.  **Create a Virtual Environment**:
    ```bash
    python -m venv venv
    # Windows
    venv\Scripts\activate
    # Linux/macOS
    source venv/bin/activate
    ```

3.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configuration**:
    *   Rename `.env.example` to `.env`.
    *   Open `.env` and fill in your credentials:
        ```ini
        API_TOKEN=your_bot_token
        API_ID=your_api_id
        API_HASH=your_api_hash
        ```

5.  **Run the Bot**:
    ```bash
    # Windows
    run.bat
    # OR
    python bot.py
    ```

---

## 📖 Usage

### User Commands
*   `/start` - Start the bot.
*   **Send a Link** - Just send a link from YouTube, Instagram, or Spotify.
    *   **YouTube**: Choose quality (1080p/720p/Audio).
    *   **Instagram/Spotify**: Downloads start automatically.

### Admin Commands (Only for Admin)
*   `/add @username` - Add a user to the whitelist (`allowed_users.txt`).
    *   Example: `/add @durov`

---

## 📂 Project Structure

*   `bot.py`: Main bot logic (aiogram). Handles user interaction and downloading.
*   `uploader.py`: Separate script (Pyrogram) for uploading large files via MTProto.
*   `resolver.py`: Helper script to resolve usernames to User IDs.
*   `downloader.py`: Wrapper around `yt-dlp` and `spotDL`.
*   `config.py`: Loads configuration from `.env`.
*   `allowed_users.txt`: List of authorized User IDs.

## 📝 License

MIT License.
