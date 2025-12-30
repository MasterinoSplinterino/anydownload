FROM python:3.11-slim

# Install system dependencies (FFmpeg is required for yt-dlp and spotdl)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
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

# Run the bot
CMD ["python", "-u", "bot.py"]
