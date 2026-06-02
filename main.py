from flask import Flask, jsonify, request
from flask_cors import CORS
import yt_dlp
import os
import base64
import tempfile
import re

app = Flask(__name__)
CORS(app)

def create_cookie_file(b64_content):
    try:
        decoded = base64.b64decode(b64_content).decode('utf-8')
        tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
        tmp.write(decoded)
        tmp.flush()
        return tmp.name
    except:
        return None

def get_platform(url):
    if 'tiktok.com' in url: return 'TikTok'
    if 'instagram.com' in url: return 'Instagram'
    if 'youtube.com' in url or 'youtu.be' in url: return 'YouTube'
    if 'twitter.com' in url or 'x.com' in url: return 'Twitter'
    if 'facebook.com' in url: return 'Facebook'
    return 'Video'

def get_ydl_opts(platform):
    base = {
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
    }

    if platform == 'Instagram':
        b64 = os.environ.get('COOKIES_B64')
        if b64:
            cookie_file = create_cookie_file(b64)
            if cookie_file:
                base['cookiefile'] = cookie_file
        base['http_headers'] = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.instagram.com/',
        }

    if platform == 'Twitter':
        b64 = os.environ.get('COOKIES_B64_TWITTER')
        if b64:
            cookie_file = create_cookie_file(b64)
            if cookie_file:
                base['cookiefile'] = cookie_file
        base['http_headers'] = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
        }
        base['extractor_args'] = {
            'twitter': {'api': ['syndication']}
        }

    if platform == 'TikTok':
        b64 = os.environ.get('COOKIES_B64_TIKTOK')
        if b64:
            cookie_file = create_cookie_file(b64)
            if cookie_file:
                base['cookiefile'] = cookie_file
        base['http_headers'] = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
            'Referer': 'https://www.tiktok.com/',
        }
        base['extractor_args'] = {
            'tiktok': {
                'webpage_download': ['true'],
            }
        }

    return base

def find_best_audio_url(formats):
    best_audio = None
    best_abr = 0
    for f in formats:
        vcodec = f.get('vcodec', 'none')
        acodec = f.get('acodec', 'none')
        abr = f.get('abr', 0) or 0
        furl = f.get('url', '')
        if vcodec == 'none' and acodec != 'none' and furl and abr > best_abr:
            best_abr = abr
            best_audio = furl
    return best_audio

def get_twitter_audio_url(video_m3u8_url):
    """Twitter video .m3u8 URL'sinden ses stream URL'sini türetir."""
    try:
        # https://video.twimg.com/amplify_video/ID/pl/avc1/WxH/xxx.m3u8
        # -> https://video.twimg.com/amplify_video/ID/pl/audio/en_US/index.m3u8
        match = re.match(r'(https://video\.twimg\.com/(?:amplify_video|ext_tw_video)/\d+)/pl/', video_m3u8_url)
        if match:
            base = match.group(1)
            return f'{base}/pl/audio/en_US/index.m3u8'
    except:
        pass
    return None

@app.route('/info', methods=['GET'])
def get_info():
    url = request.args.get('url', '')
    if not url:
        return jsonify({'error': 'URL gerekli'}), 400

    platform = get_platform(url)
    ydl_opts = get_ydl_opts(platform)

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = info.get('formats', [])

            best_audio_url = find_best_audio_url(formats)

            qualities = []
            seen_heights = set()
            seen_urls = set()

            for f in reversed(formats):
                height = f.get('height')
                ext = f.get('ext', 'mp4')
                furl = f.get('url', '')
                vcodec = f.get('vcodec', 'none')

                if not furl or furl in seen_urls:
                    continue

                if vcodec != 'none' and height and height not in seen_heights:
                    seen_heights.add(height)
                    seen_urls.add(furl)

                    audio_url = None
                    if platform == 'Instagram':
                        audio_url = best_audio_url
                    elif platform == 'Twitter':
                        # Önce formatlardan bulmaya çalış, yoksa URL'den türet
                        audio_url = best_audio_url or get_twitter_audio_url(furl)

                    qualities.append({
                        'label': f'{height}p',
                        'url': furl,
                        'audio_url': audio_url,
                        'format': ext if ext not in ['none', ''] else 'mp4',
                        'size': '',
                    })

            if best_audio_url:
                qualities.append({
                    'label': 'Ses (MP3)',
                    'url': best_audio_url,
                    'audio_url': None,
                    'format': 'mp3',
                    'size': '',
                })

            def sort_key(q):
                try:
                    return int(q['label'].replace('p', ''))
                except:
                    return 0

            video_q = [q for q in qualities if 'MP3' not in q['label']]
            audio_q = [q for q in qualities if 'MP3' in q['label']]
            video_q.sort(key=sort_key, reverse=True)
            qualities = video_q + audio_q

            if not qualities and info.get('url'):
                qualities.append({
                    'label': 'HD',
                    'url': info['url'],
                    'audio_url': None,
                    'format': info.get('ext', 'mp4'),
                    'size': '',
                })

            if not qualities:
                return jsonify({'error': 'Video formatı bulunamadı. Link herkese açık mı?'}), 500

            return jsonify({
                'title': info.get('title', f'{platform} Videosu'),
                'thumbnail': info.get('thumbnail', ''),
                'platform': platform,
                'author': info.get('uploader', ''),
                'duration': str(info.get('duration', '')),
                'qualities': qualities,
            })

    except yt_dlp.utils.ExtractorError as e:
        err = str(e)
        if 'login' in err.lower() or 'private' in err.lower():
            return jsonify({'error': 'Bu içerik özel veya giriş gerektiriyor.'}), 500
        if 'rate' in err.lower():
            return jsonify({'error': 'Rate limit aşıldı. Biraz bekle.'}), 500
        return jsonify({'error': f'Video alınamadı: {err[:200]}'}), 500
    except Exception as e:
        return jsonify({'error': str(e)[:200]}), 500

@app.route('/health', methods=['GET'])
def health():
    ig_status = "✓" if os.environ.get('COOKIES_B64') else "✗"
    tw_status = "✓" if os.environ.get('COOKIES_B64_TWITTER') else "✗"
    tk_status = "✓" if os.environ.get('COOKIES_B64_TIKTOK') else "✗"
    return jsonify({
        'status': 'ok',
        'message': 'Video Downloader API çalışıyor!',
        'instagram_cookies': ig_status,
        'twitter_cookies': tw_status,
        'tiktok_cookies': tk_status,
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)


@app.route('/proxy', methods=['GET'])
def proxy():
    import requests
    from flask import Response
    url = request.args.get('url', '')
    if not url:
        return jsonify({'error': 'URL gerekli'}), 400
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
            'Referer': 'https://twitter.com/',
        }
        r = requests.get(url, headers=headers, stream=True, timeout=60)
        return Response(
            r.iter_content(chunk_size=8192),
            content_type=r.headers.get('Content-Type', 'video/mp4'),
            status=r.status_code,
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500
