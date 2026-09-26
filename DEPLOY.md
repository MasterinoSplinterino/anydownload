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

## Queue & limits

All downloads go through one queue (`queue_manager.py`):

| Variable | Default | Meaning |
|---|---|---|
| `ADMIN_IDS` | `177036997` | Comma-separated admin IDs, no limits |
| `MAX_CONCURRENT_DOWNLOADS` | `2` | Downloads running at the same time |
| `MAX_QUEUE_SIZE` | `50` | Max waiting jobs in total |
| `MAX_JOBS_PER_USER` | `2` | Running + waiting jobs per user |
| `DAILY_LIMIT_PER_USER` | `30` | Successful downloads per 24h (0 = unlimited) |
| `COOLDOWN_SECONDS` | `5` | Min pause between links from one user |

User commands: `/queue`, `/limits`, `/cancel`. Admin: `/stats`, `/setlimit <user_id> <n|default>`.

## YouTube: PO tokens

`docker compose up -d` also starts `brainicism/bgutil-ytdlp-pot-provider`, which generates
PO tokens for yt-dlp. On Coolify (Dockerfile build pack) run that image as a separate service
and set `POT_PROVIDER_URL=http://<service-host>:4416`. The container updates yt-dlp on every
start (`YTDLP_AUTO_UPDATE=0` disables it), so a plain restart picks up YouTube fixes.
