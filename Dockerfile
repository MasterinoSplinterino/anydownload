FROM python:3.11-slim

# Install system dependencies (FFmpeg is required for yt-dlp and spotdl)
# curl and nodejs are required for yt-dlp JavaScript runtime
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Set working directory
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Create necessary directories
RUN mkdir -p downloads data sessions

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV DB_PATH=/app/data/bot.db

# YouTube breaks old yt-dlp versions often: update it on every container start
# (set YTDLP_AUTO_UPDATE=0 to disable)
CMD ["sh", "-c", "if [ \"${YTDLP_AUTO_UPDATE:-1}\" = \"1\" ]; then pip install -q -U --no-cache-dir 'yt-dlp[default]' bgutil-ytdlp-pot-provider || true; fi; exec python -u bot.py"]
