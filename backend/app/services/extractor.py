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

    async def _resolve_google_search_content(self, url: str) -> Optional[str]:
        """Extracts the actual media link from a Google Search result page."""
        try:
            # Use Mobile UA to get cleaner HTML
            mobile_ua = "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Mobile Safari/537.36"
            async with httpx.AsyncClient(follow_redirects=True, verify=False) as client:
                resp = await client.get(url, headers={'User-Agent': mobile_ua})
                if resp.status_code == 200:
                    text = resp.text
                    
                    # 1. Look for common video patterns in raw text
                    patterns = [
                        r'https?://(?:www\.)?youtube\.com/watch\?v=([\w-]{11})',
                        r'https?://youtu\.be/([\w-]{11})',
                        r'https?://(?:www\.)?instagram\.com/(?:p|reel)/([\w-]{11})',
                        r'(https?://[^"\'<>]+\.mp4)'
                    ]
                    
                    for p in patterns:
                        match = re.search(p, text)
                        if match:
                            # If it's a capture group, return that, otherwise return the full match
                            final_link = match.group(0) if p.startswith('(') else match.group(0)
                            print(f"[+] Found resolved link in Google: {final_link}")
                            return final_link
                    
                    # 2. Look for Google Video Search results encoded in URLs
                    gv_match = re.search(r'/url\?q=(https?://[^&]+)', text)
                    if gv_match:
                        from urllib.parse import unquote
                        link = unquote(gv_match.group(1))
                        if 'youtube.com' in link or 'instagram.com' in link or link.endswith('.mp4'):
                            print(f"[+] Found resolved link in Google URL: {link}")
                            return link
        except Exception as e:
            print(f"Error resolving Google Search: {e}")
        return None

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

        if 'google.com/search' in url:
            resolved = await self._resolve_google_search_content(url)
            if resolved:
                url = resolved

        clean_url = self._clean_url(url)
        print(f"[*] Analyzing: {clean_url}")
        
        # Domain Helper
        is_youtube = 'youtube.com' in clean_url or 'youtu.be' in clean_url
        
        # Strategy 1: YouTube Specific (Force YDL)
        if is_youtube:
            # Try Direct YDL
            try:
                print("[*] Trying Strategy: YDL-Direct")
                res = await self._strategy_ydl_direct(clean_url)
                if res: return res
            except Exception as e:
                print(f"[-] YDL-Direct failed: {e}")
            
            # If YouTube YDL fails (common on Vercel), fall through to Strategy 2 (Parallel)
            print("[*] YouTube YDL failed or blocked, trying Parallel Fallbacks...")

        # Strategy 2: Parallel Strategy
        strategies = [
            self._strategy_direct_file(clean_url),
            self._strategy_rapid_scrape(clean_url),
            self._strategy_ydl_direct(clean_url),
            self._strategy_fallback_node(clean_url) # NEW: Public Node Fallback
        ]
        tasks = [asyncio.create_task(s) for s in strategies]
        
        try:
            for completed in asyncio.as_completed(tasks):
                try:
                    result = await completed
                    if result and result.formats:
                        print(f"[+] Strategy Success: {result.platform}")
                        for t in tasks: 
                            if not t.done(): t.cancel()
                        return result
                    else:
                        print(f"[-] A strategy returned no result or formats.")
                except Exception as e:
                    print(f"[-] Strategy failed with error: {str(e)}")
                    continue
        except Exception as e:
            print(f"[!] Extraction Timeout or Global Error: {e}")
        finally:
            for t in tasks:
                if not t.done(): t.cancel()

        print(f"[!] All extraction strategies failed for: {clean_url}")
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

    async def _strategy_fallback_node(self, url: str) -> Optional[MediaMetadata]:
        """Uses a public media resolution node as a last resort."""
        try:
            # This is a public node known to work for many sites
            api_url = f"https://api.cobalt.tools/api/json"
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Referer": "https://cobalt.tools/"
            }
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(api_url, json={"url": url}, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    media_url = data.get('url') or data.get('stream')
                    if media_url:
                        return MediaMetadata(
                            id=str(int(time.time())),
                            title="Media Content (Resolved via Fallback)",
                            platform="FallbackAPI",
                            thumbnail=data.get('thumbnail'),
                            formats=[MediaFormat(
                                format_id="fallback",
                                extension="mp4",
                                resolution="HD",
                                url=media_url
                            )],
                            original_url=url
                        )
        except Exception as e:
            print(f"[-] Fallback Node failed: {e}")
        return None

    async def _strategy_ydl_direct(self, url: str) -> Optional[MediaMetadata]:
        opts = {
            'quiet': True, 'no_warnings': True, 'skip_download': True,
            'check_formats': False, 'user_agent': self.ua, 'socket_timeout': 10,
            'nocheckcertificate': True, 'no_color': True,
            'geo_bypass': True, 'extract_flat': 'in_playlist',
            'referer': 'https://www.google.com/'
        }
        return await self._run_ydl(url, opts, "Direct")


    async def _run_ydl(self, url: str, opts: dict, name: str) -> Optional[MediaMetadata]:
        loop = asyncio.get_event_loop()
        try:
            info = await loop.run_in_executor(None, self._extract_sync, url, opts)
            if info: return self._parse_info(info, url)
        except Exception as e:
            print(f"[!] YDL {name} Error: {str(e)}")
        return None

    def _extract_sync(self, url: str, opts: dict):
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False)

    def _parse_info(self, info: Dict[str, Any], original_url: str) -> MediaMetadata:
        if 'entries' in info and info['entries']: info = info['entries'][0]
        
        is_youtube = 'youtube.com' in original_url or 'youtu.be' in original_url
        formats = []
        raw_formats = info.get('formats', []) or ([info] if info.get('url') else [])
        
        for f in raw_formats:
            url = f.get('url')
            if not url: continue
            
            # Prioritize combined mp4/h264 formats which are most compatible with browsers
            vcodec = f.get('vcodec', 'none')
            acodec = f.get('acodec', 'none')
            ext = f.get('ext', '')
            
            # YouTube often has separate video/audio. We prefer combined but will take what we can.
            is_combined = vcodec != 'none' and acodec != 'none'
            
            # For YouTube, if we can't find combined, we might need to show something.
            # But for simplicity, we focus on what can be streamed directly in browser.
            if is_combined or ext in ['mp4', 'm4a', 'mp3'] or 'instagram.com' in original_url:
                formats.append(MediaFormat(
                    format_id=str(f.get('format_id')), 
                    extension=ext or 'mp4',
                    resolution=f.get('resolution') or (f"{f.get('height')}p" if f.get('height') else "HD"),
                    filesize=f.get('filesize') or f.get('filesize_approx'),
                    url=url
                ))
            elif not is_youtube: # For other sites, be more liberal
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
