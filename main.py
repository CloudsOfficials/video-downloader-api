from flask import Flask, jsonify, request
from flask_cors import CORS
import yt_dlp

app = Flask(__name__)
CORS(app)

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

    if platform == 'TikTok':
        base['extractor_args'] = {
            'tiktok': {'api_hostname': 'api22-normal-c-alisg.tiktokv.com'}
        }

    if platform == 'Instagram':
        base['http_headers'] = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        base['cookiefile'] = None

    if platform == 'Twitter':
        base['http_headers'] = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
        }
        base['extractor_args'] = {
            'twitter': {'api': ['syndication']}
        }

    return base

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

            qualities = []
            seen_heights = set()
            seen_urls = set()

            # Video formatları
            for f in reversed(formats):
                height = f.get('height')
                ext = f.get('ext', 'mp4')
                furl = f.get('url', '')
                vcodec = f.get('vcodec', 'none')
                acodec = f.get('acodec', 'none')

                if not furl or furl in seen_urls:
                    continue

                if vcodec != 'none' and height and height not in seen_heights:
                    seen_heights.add(height)
                    seen_urls.add(furl)
                    qualities.append({
                        'label': f'{height}p',
                        'url': furl,
                        'format': ext if ext not in ['none', ''] else 'mp4',
                        'size': '',
                    })

            # Ses formatı
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

            if best_audio:
                qualities.append({
                    'label': 'Ses (MP3)',
                    'url': best_audio,
                    'format': 'mp3',
                    'size': '',
                })

            # Yüksekten düşüğe sırala
            def sort_key(q):
                try:
                    return int(q['label'].replace('p', ''))
                except:
                    return 0

            video_q = [q for q in qualities if 'MP3' not in q['label']]
            audio_q = [q for q in qualities if 'MP3' in q['label']]
            video_q.sort(key=sort_key, reverse=True)
            qualities = video_q + audio_q

            # Hiç format bulunamadıysa direkt url dene
            if not qualities and info.get('url'):
                qualities.append({
                    'label': 'HD',
                    'url': info['url'],
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
            return jsonify({'error': 'Bu içerik özel. Herkese açık bir link dene.'}), 500
        return jsonify({'error': f'Video alınamadı: {err[:200]}'}), 500
    except Exception as e:
        return jsonify({'error': str(e)[:200]}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'message': 'Video Downloader API çalışıyor!'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
