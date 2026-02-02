# MediaFlow: Next-Generation Media Processing Engine

**MediaFlow** is a production-grade web application for analyzing, streaming, and extracting media from 1000+ platforms.

## 🚀 Key Features
- **Parallel Analysis Engine**: Triple-node strategy (Direct YDL, Browser Bridge, and Rapid Scrape) ensures < 15s extraction.
- **Ghost-Flow UI**: Premium glassmorphism design with real-time countdown timers.
- **Secure Stream Proxy**: Zero-exposed source URLs for in-browser playback.
- **Cross-Platform**: Full support for YouTube, Instagram Reels, and TikTok.

## 🛠️ Tech Stack
- **Backend**: FastAPI (Python), yt-dlp, httpx.
- **Frontend**: Vanilla JS (ES6+), CSS3 Glassmorphism.

## 🚦 Installation
1. `pip install -r requirements.txt`
2. `python run.py`
3. Open `http://127.0.0.1:8000`

## 📦 Docker
`docker build -t mediaflow .`
`docker run -p 8000:8000 mediaflow`
