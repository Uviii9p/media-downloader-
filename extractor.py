import asyncio
import yt_dlp
import httpx
import re
import time
from typing import Dict, Any, Optional, List
from backend.app.models.schemas import MediaMetadata, MediaFormat

class MediaExtractor:
    def __init__(self):
        self.ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'

    def _clean_url(self, url: str) -> str:
        if 'instagram.com' in url:
            # Extract core reel/post ID
            id_match = re.search(r'/(?:reels?|p|stories)/([A-Za-z0-9_-]+)', url)
            if id_match:
                return f"https://www.instagram.com/reel/{id_match.group(1)}/"
        
        # Handle Google Search Redirects
        if 'google.' in url and '/url?' in url:
            match = re.search(r'url=([^&]+)', url)
            if match:
                from urllib.parse import unquote
                return unquote(match.group(1))
                
        return url

    async def extract_info(self, url: str) -> Optional[MediaMetadata]:
        # Handle Data URIs (Base64 images)
        if url.startswith('data:image'):
            return MediaMetadata(
                id="base64-img",
                title="Base64 Image Content",
                thumbnail=url,
                platform="Internal",
                formats=[MediaFormat(format_id="raw", extension="jpg", resolution="Original", url=url)],
                original_url=url[:100] + "..."
            )

        clean_url = self._clean_url(url)
        print(f"[*] Analyzing: {clean_url}")
        
        # Domain Helper
        is_youtube = 'youtube.com' in clean_url or 'youtu.be' in clean_url
        
        # Strategy 1: YouTube Specific (Force YDL)
        if is_youtube:
            try:
                res = await self._strategy_ydl_direct(clean_url)
                if res: return res
            except Exception: pass
            
            # Fallback for cookies if needed (though usually not for public vids)
            try:
                res = await self._strategy_ydl_cookies(clean_url)
                if res: return res
            except Exception: pass
            
            return None # Don't try rapid scrape on YouTube, it gives bad results

        # Strategy 2: Generic Sequential (Rapid -> Direct -> YDL)
        
        # 1. Rapid Scrape (Fastest, low overhead)
        try:
            res = await self._strategy_rapid_scrape(clean_url)
            if res: return res
        except Exception: pass
            
        # 2. Direct File Link
        try:
            res = await self._strategy_direct_file(clean_url)
            if res: return res
        except Exception: pass
            
        # 3. YDL (Heaviest, fallback)
        try:
            res = await self._strategy_ydl_direct(clean_url)
            if res: return res
        except Exception: pass

        return None

    async def _strategy_direct_file(self, url: str) -> Optional[MediaMetadata]:
        """Handles direct links to images or videos."""
        image_exts = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp')
        video_exts = ('.mp4', '.webm', '.ogg', '.mov', '.avi')
        
        lower_url = url.lower().split('?')[0]
        
        if lower_url.endswith(image_exts) or lower_url.endswith(video_exts):
            ext = lower_url.split('.')[-1]
            is_video = any(lower_url.endswith(ve) for ve in video_exts)
            
            return MediaMetadata(
                id=str(int(time.time())),
                title=f"Direct {ext.upper()} Content",
                thumbnail=url if not is_video else None,
                platform="DirectLink",
                formats=[MediaFormat(
                    format_id="direct", 
                    extension=ext, 
                    resolution="Original", 
                    url=url
                )],
                original_url=url
            )
        return None

    async def _strategy_rapid_scrape(self, url: str) -> Optional[MediaMetadata]:
        """Fetches via OpenGraph tags - fast and hard to block."""
        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                headers = {'User-Agent': 'facebookexternalhit/1.1'} # Mimic social crawler
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    text = resp.text
                    # Extract via regex to be fast
                    video_url = re.search(r'property="og:video(:secure_url)?" content="([^"]+)"', text)
                    if video_url:
                        video_link = video_url.group(2).replace('&amp;', '&')
                        return MediaMetadata(
                            id=str(int(time.time())),
                            title="Media Content",
                            platform="RapidScrape",
                            formats=[MediaFormat(format_id="hd", extension="mp4", url=video_link)],
                            original_url=url
                        )
        except Exception:
            pass
        return None

    async def _strategy_ydl_direct(self, url: str) -> Optional[MediaMetadata]:
        opts = {
            'quiet': True, 'no_warnings': True, 'skip_download': True,
            'check_formats': False, 'user_agent': self.ua, 'socket_timeout': 10
        }
        return await self._run_ydl(url, opts, "Direct")

    async def _strategy_ydl_cookies(self, url: str) -> Optional[MediaMetadata]:
        for browser in ['chrome', 'edge', 'firefox']:
            opts = {
                'quiet': True, 'skip_download': True, 'cookiesfrombrowser': (browser,), 'socket_timeout': 10
            }
            res = await self._run_ydl(url, opts, f"Cookies-{browser}")
            if res: return res
        return None

    async def _run_ydl(self, url: str, opts: dict, name: str) -> Optional[MediaMetadata]:
        loop = asyncio.get_event_loop()
        try:
            info = await loop.run_in_executor(None, self._extract_sync, url, opts)
            if info: return self._parse_info(info, url)
        except Exception:
            pass
        return None

    def _extract_sync(self, url: str, opts: dict):
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False)

    def _parse_info(self, info: Dict[str, Any], original_url: str) -> MediaMetadata:
        if 'entries' in info and info['entries']: info = info['entries'][0]
        
        formats = []
        raw_formats = info.get('formats', []) or ([info] if info.get('url') else [])
        
        for f in raw_formats:
            url = f.get('url')
            if not url: continue
            
            # Prioritize combined mp4/h264 formats which are most compatible with browsers
            vcodec = f.get('vcodec', 'none')
            acodec = f.get('acodec', 'none')
            ext = f.get('ext', '')
            
            # We want BOTH video and audio in one file for the best streaming experience
            is_combined = vcodec != 'none' and acodec != 'none'
            
            if is_combined or ext == 'mp4' or 'instagram.com' in original_url:
                formats.append(MediaFormat(
                    format_id=str(f.get('format_id')), 
                    extension=ext or 'mp4',
                    resolution=f.get('resolution') or f.get('height') or 'HD',
                    filesize=f.get('filesize') or f.get('filesize_approx'),
                    url=url
                ))
        
        # Sort formats: Combined MP4s first
        formats.sort(key=lambda x: (x.extension == 'mp4', x.resolution != 'HD'), reverse=True)

        return MediaMetadata(
            id=info.get('id', 'media'), title=info.get('title', 'Media'),
            thumbnail=info.get('thumbnail'), duration=info.get('duration'),
            uploader=info.get('uploader'), platform=info.get('extractor_key', 'Platform'),
            formats=formats, original_url=original_url
        )

extractor = MediaExtractor()
