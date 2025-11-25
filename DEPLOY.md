# Deployment to Vercel

## Prerequisites
1.  **Vercel Account**: Sign up at [vercel.com](https://vercel.com).
2.  **Vercel CLI** (Optional but recommended): `npm i -g vercel`

## Steps

1.  **Push to GitHub**:
    *   Create a new repository on GitHub.
    *   Push this code to it:
        ```bash
        git remote add origin <your-github-repo-url>
        git branch -M main
        git push -u origin main
        ```

2.  **Import to Vercel**:
    *   Go to Vercel Dashboard -> "Add New..." -> "Project".
    *   Import your GitHub repository.
    *   **Environment Variables**: Add your `API_TOKEN` in the Vercel project settings (Settings -> Environment Variables).
        *   Key: `API_TOKEN`
        *   Value: `8216575053:AAEZWPgZP8Owoc5zlkfNr7UKjTkh3I6H75w` (or your actual token)

3.  **Set Webhook**:
    *   After deployment, you'll get a URL (e.g., `https://your-project.vercel.app`).
    *   You must tell Telegram to send updates to this URL.
    *   Run this in your browser:
        ```
        https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook?url=https://<YOUR_VERCEL_URL>/api/index
        ```

## ⚠️ Important Limitations on Vercel

*   **Timeouts**: Vercel functions (Free Tier) time out after **10 seconds**. Downloading/Uploading large videos will likely fail.
*   **Filesystem**: Read-only (except `/tmp`).
*   **FFmpeg**: Not installed by default. 1080p downloads (which require merging video+audio) might fail.
*   **State**: The "Quality Selection" menu relies on in-memory state, which **will be lost** between requests on Vercel. You might need to click the quality button multiple times or it might not work.

**Recommendation**: For a video downloader bot, a VPS (like DigitalOcean, Hetzner, or a cheap VM) is **much better** than Serverless/Vercel because it allows long-running processes (downloads) and persistent storage.
