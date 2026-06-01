from flask import Flask, jsonify, request
from flask_cors import CORS
import yt_dlp
import re

app = Flask(__name__)
CORS(app)

def get_platform(url):
    if 'tiktok.com' in url: return 'TikTok'
    if 'instagram.com' in url: return 'Instagram'
    if 'youtube.com' in url or 'youtu.be' in url: return 'YouTube'
    if 'twitter.com' in url or 'x.com' in url: return 'Twitter'
    if 'facebook.com' in url: return 'Facebook'
    return 'Video'

@app.route('/info', methods=['GET'])
def get_info():
    url = request.args.get('url', '')
    if not url:
        return jsonify({'error': 'URL gerekli'}), 400

    platform = get_platform(url)

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'noplaylist': True,
    }

    # TikTok için watermark'sız
    if platform == 'TikTok':
        ydl_opts['extractor_args'] = {'tiktok': {'api_hostname': 'api22-normal-c-alisg.tiktokv.com'}}

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            qualities = []
            formats = info.get('formats', [])

            seen = set()
            for f in reversed(formats):
                height = f.get('height')
                ext = f.get('ext', 'mp4')
                furl = f.get('url', '')
                vcodec = f.get('vcodec', '')
                acodec = f.get('acodec', '')

                if not furl or furl in seen:
                    continue

                # Sadece video formatları
                if vcodec != 'none' and height:
                    label = f'{height}p'
                    if label not in [q['label'] for q in qualities]:
                        qualities.append({
                            'label': label,
                            'url': furl,
                            'format': ext if ext != 'none' else 'mp4',
                            'size': ''
                        })
                        seen.add(furl)

                # Audio only
                if vcodec == 'none' and acodec != 'none' and len([q for q in qualities if 'MP3' in q['label']]) == 0:
                    qualities.append({
                        'label': 'Ses (MP3)',
                        'url': furl,
                        'format': 'mp3',
                        'size': ''
                    })
                    seen.add(furl)

            # En yüksek kaliteden sırala
            video_q = [q for q in qualities if 'MP3' not in q['label']]
            audio_q = [q for q in qualities if 'MP3' in q['label']]
            
            def sort_key(q):
                try:
                    return int(q['label'].replace('p', ''))
                except:
                    return 0
            
            video_q.sort(key=sort_key, reverse=True)
            qualities = video_q + audio_q

            # En az 1 kalite olsun
            if not qualities and info.get('url'):
                qualities.append({
                    'label': 'HD',
                    'url': info['url'],
                    'format': info.get('ext', 'mp4'),
                    'size': ''
                })

            return jsonify({
                'title': info.get('title', f'{platform} Videosu'),
                'thumbnail': info.get('thumbnail', ''),
                'platform': platform,
                'author': info.get('uploader', ''),
                'duration': str(info.get('duration', '')),
                'qualities': qualities
            })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'message': 'Video Downloader API çalışıyor!'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
