# Deployment Guide

## Option 1: Coolify (Recommended)

Since you have a VPS with Coolify, this is the best option.

1.  **Create a new Service**:
    *   Select **Source**: Git Repository.
    *   Select this repository (`MasterinoSplinterino/anydownload`).
2.  **Configuration**:
    *   **Build Pack**: Dockerfile (Coolify should auto-detect it).
    *   **Environment Variables**:
        *   Add all variables from your `.env` file:
            *   `API_TOKEN`
            *   `API_ID`
            *   `API_HASH`
3.  **Persistent Storage** (Optional but recommended):
    *   If you want to keep the whitelist (`allowed_users.txt`) between restarts, add a volume mount:
        *   `/app/allowed_users.txt`
4.  **Deploy**: Click "Deploy".

Coolify will build the Docker image (installing Python and FFmpeg) and run your bot.

## Option 2: Docker Compose (Manual VPS)

1.  Clone the repo:
    ```bash
    git clone https://github.com/MasterinoSplinterino/anydownload.git
    cd anydownload
    ```
2.  Create `.env` file with your keys.
3.  Run:
    ```bash
    docker compose up -d
    ```

## Option 3: Manual Systemd (Old school)

See `README.md` for installation steps, then create a systemd service:

```ini
[Unit]
Description=AnyDownload Bot
After=network.target

[Service]
User=root
WorkingDirectory=/path/to/anydownload
ExecStart=/path/to/anydownload/venv/bin/python bot.py
Restart=always

[Install]
WantedBy=multi-user.target
```
