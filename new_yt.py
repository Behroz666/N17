import os
import json
import time
import requests
from googleapiclient.discovery import build
from telegram import send_message
from gemini import ask_gemini

with open('config.json', 'r', encoding='utf-8') as file:
    config = json.load(file)

# --- Configuration Constants ---
TELEGRAM_API_LIMIT_BYTES = 50 * 1024 * 1024  # Telegram bot API file size limit (50 MB)
SEEN_VIDEOS_FILE = "seen_videos.json"
ADMIN_CHAT_ID = 1140637004

# How many of the most recent uploads to look at each run. Bump this up if the
# workflow might ever miss a run (e.g. GH Actions outage) so nothing slips through.
MAX_RECENT_VIDEOS_TO_CHECK = 50

# --- Environment Variables (set as GitHub Secrets) ---
YOUTUBE_API_KEY = os.environ.get('GOOGLE')
YOUTUBE_CHANNEL_ID = "UCEg25rdRZXg32iwai6N6l0w"
TELEGRAM_BOT_TOKEN = os.environ.get('BOT_TOKEN')
TELEGRAM_CHAT_ID = config["Media Chat id"]

# Cobalt instance to use for downloading. Leave COBALT_API_URL unset to
# automatically pick a public, no-auth, YouTube-capable instance from the
# community instance tracker (https://instances.cobalt.best) each run. Set
# COBALT_API_URL if you switch to a self-hosted or dedicated instance later.
COBALT_API_URL = os.environ.get('COBALT_API_URL', '').rstrip('/')
COBALT_API_KEY = os.environ.get('COBALT_API_KEY')  # optional, "Api-Key <key>" auth
COBALT_USER_AGENT = "yt-telegram-uploader/1.0 (+https://github.com/)"

_public_instance_cache = None  # populated lazily, once per run

# --- YouTube API Setup ---
youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)


# --------------------------------------------------------------------------
# Seen-videos persistence
# --------------------------------------------------------------------------

def load_seen_videos():
    """Loads the set of video IDs we've already processed from disk."""
    if not os.path.exists(SEEN_VIDEOS_FILE):
        return None  # signals "first run, no baseline yet"
    try:
        with open(SEEN_VIDEOS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return set(data.get('video_ids', []))
    except Exception as e:
        print(f"Error loading {SEEN_VIDEOS_FILE}: {e}. Starting with an empty set.")
        return set()


def save_seen_videos(seen_ids):
    """Persists the set of seen video IDs to disk."""
    try:
        with open(SEEN_VIDEOS_FILE, 'w', encoding='utf-8') as f:
            json.dump({'video_ids': sorted(seen_ids)}, f, indent=2)
    except Exception as e:
        print(f"Error saving {SEEN_VIDEOS_FILE}: {e}")


# --------------------------------------------------------------------------
# YouTube helpers
# --------------------------------------------------------------------------

def get_channel_uploads_playlist_id(youtube_service, channel_id):
    """Fetches the uploads playlist ID for a given YouTube channel ID."""
    try:
        request = youtube_service.channels().list(
            part='contentDetails',
            id=channel_id
        )
        response = request.execute()

        if response and response.get('items'):
            playlist_id = response['items'][0]['contentDetails']['relatedPlaylists']['uploads']
            print(f"Found uploads playlist ID: {playlist_id}")
            return playlist_id
        else:
            print(f"Could not find uploads playlist for channel ID: {channel_id}")
            return None
    except Exception as e:
        print(f"Error fetching uploads playlist ID: {e}")
        return None


def get_recent_videos(youtube_service, playlist_id, max_videos):
    """
    Fetches up to max_videos of the most recent items from a playlist,
    newest first, regardless of publish date.
    """
    videos = []
    next_page_token = None

    while len(videos) < max_videos:
        try:
            request = youtube_service.playlistItems().list(
                part='snippet,contentDetails',
                playlistId=playlist_id,
                maxResults=min(50, max_videos - len(videos)),
                pageToken=next_page_token
            )
            response = request.execute()

            for item in response.get('items', []):
                videos.append({
                    'id': item['contentDetails']['videoId'],
                    'title': item['snippet']['title'],
                    'published_at': item['snippet']['publishedAt'],
                })

            next_page_token = response.get('nextPageToken')
            if not next_page_token:
                break
        except Exception as e:
            print(f"Error fetching recent videos: {e}")
            break

    return videos


# --------------------------------------------------------------------------
# Cobalt download helpers
# --------------------------------------------------------------------------

def get_public_cobalt_instances():
    """
    Fetches and caches a list of public cobalt API base URLs from the
    community instance tracker, keeping only instances that are online,
    don't require auth/turnstile, and support YouTube. Sorted best-first.
    """
    global _public_instance_cache
    if _public_instance_cache is not None:
        return _public_instance_cache

    instances = []
    try:
        resp = requests.get(
            "https://instances.cobalt.best/api",
            headers={"User-Agent": COBALT_USER_AGENT},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        scored = []
        for inst in data:
            if not inst.get("online"):
                continue
            info = inst.get("info", {})
            if info.get("auth"):
                continue  # needs an api key or turnstile solve we don't have
            services = inst.get("services", {})
            if services.get("youtube") is not True:
                continue
            api_host = inst.get("api")
            if not api_host:
                continue
            scored.append((inst.get("score", 0), f"https://{api_host}"))

        scored.sort(key=lambda x: x[0], reverse=True)
        instances = [url for _, url in scored]
        print(f"Found {len(instances)} usable public cobalt instance(s).")
    except Exception as e:
        print(f"Could not fetch public cobalt instance list: {e}")

    _public_instance_cache = instances
    return instances


def _cobalt_post(base_url, video_url, retries=2, backoff=5):
    """POSTs to a single cobalt instance. Returns parsed JSON, or None on network failure."""
    endpoint = f"{base_url}/"
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'User-Agent': COBALT_USER_AGENT,
    }
    if COBALT_API_KEY:
        headers['Authorization'] = COBALT_API_KEY if ' ' in COBALT_API_KEY else f"Api-Key {COBALT_API_KEY}"

    payload = {
        'url': video_url,
        'downloadMode': 'auto',
        'videoQuality': '360',       # smallest/lowest video quality tier cobalt exposes near 360p
        'audioBitrate': '64',        # smallest reasonable audio bitrate
        'youtubeVideoCodec': 'h264', # widely compatible, keeps things simple for Telegram
        'youtubeVideoContainer': 'mp4',
        'filenameStyle': 'basic',
    }

    last_error = None
    for attempt in range(1, retries + 1):
        try:
            resp = requests.post(endpoint, headers=headers, json=payload, timeout=60)
            if resp.status_code == 429:
                last_error = "rate limited (429)"
                time.sleep(backoff * attempt)
                continue
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            last_error = str(e)
            time.sleep(backoff)

    print(f"Request to {base_url} failed: {last_error}")
    return None


def cobalt_request(video_url, max_instances_to_try=4):
    """
    Tries cobalt instances in order (a pinned COBALT_API_URL if set, otherwise
    the best public instances) until one gives back a usable response.
    Returns the parsed JSON response dict, or None if everything failed.
    """
    if COBALT_API_URL:
        instances = [COBALT_API_URL]
    else:
        instances = get_public_cobalt_instances()

    if not instances:
        print("No cobalt instances available to try.")
        return None

    last_data = None
    for base_url in instances[:max_instances_to_try]:
        data = _cobalt_post(base_url, video_url)
        if data is None:
            continue  # network/timeout failure on this instance, try the next one
        last_data = data
        if data.get('status') != 'error':
            return data
        print(f"cobalt instance {base_url} returned error: {data.get('error')} - trying next instance")

    return last_data


def download_stream(url, dest_path, headers=None):
    """Streams a URL to disk without any re-encoding/compression."""
    with requests.get(url, headers=headers or {}, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(dest_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)


def cobalt_download_video(video_id, dest_path):
    """
    Uses cobalt to fetch a 360p (smallest available) copy of the video and
    writes it to dest_path. Returns True on success, False otherwise.
    No local re-encoding/compression is performed - whatever cobalt hands
    back is what gets saved.
    """
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    data = cobalt_request(video_url)
    if not data:
        return False

    status = data.get('status')

    if status in ('tunnel', 'redirect'):
        download_stream(data['url'], dest_path)
        return os.path.exists(dest_path) and os.path.getsize(dest_path) > 0

    if status == 'local-processing':
        # Only expected for edge cases cobalt can't remux server-side.
        # We still don't compress anything - just stream-copy the pieces
        # cobalt already picked at 360p into a single container.
        tunnels = data.get('tunnel', [])
        if not tunnels:
            print(f"local-processing response with no tunnels for {video_id}")
            return False

        temp_parts = []
        for i, tunnel_url in enumerate(tunnels):
            part_path = f"{video_id}_part{i}.tmp"
            download_stream(tunnel_url, part_path)
            temp_parts.append(part_path)

        if len(temp_parts) == 1:
            os.rename(temp_parts[0], dest_path)
            return True

        # Multiple parts (e.g. separate video/audio) - mux without re-encoding.
        import subprocess
        cmd = ['ffmpeg', '-y']
        for part in temp_parts:
            cmd += ['-i', part]
        cmd += ['-c', 'copy', dest_path]
        try:
            subprocess.run(cmd, check=True)
        finally:
            for part in temp_parts:
                if os.path.exists(part):
                    os.remove(part)
        return os.path.exists(dest_path) and os.path.getsize(dest_path) > 0

    if status == 'picker':
        picker_items = data.get('picker', [])
        video_items = [p for p in picker_items if p.get('type') == 'video']
        if not video_items:
            print(f"picker response with no video items for {video_id}")
            return False
        download_stream(video_items[0]['url'], dest_path)
        return os.path.exists(dest_path) and os.path.getsize(dest_path) > 0

    if status == 'error':
        err = data.get('error', {})
        print(f"Cobalt error for {video_id}: {err}")
        return False

    print(f"Unexpected cobalt response status '{status}' for {video_id}")
    return False


# --------------------------------------------------------------------------
# Telegram helpers
# --------------------------------------------------------------------------

def download_thumbnail(video_id):
    thumbnail_url = f'https://img.youtube.com/vi/{video_id}/maxresdefault.jpg'
    response = requests.get(thumbnail_url)

    if response.status_code == 200:
        with open('thumbnail.jpg', 'wb') as file:
            file.write(response.content)
        print("Thumbnail downloaded successfully.")
    else:
        print("Failed to download thumbnail.")


def upload_video_to_telegram(video_id, video_title, final_file, telegram_bot_token, telegram_chat_id):
    video_url = f"https://youtube.com/watch?v={video_id}"
    download_thumbnail(str(video_id))

    url_send = f'https://api.telegram.org/bot{telegram_bot_token}/sendVideo'
    with open(final_file, 'rb') as video_f, open('thumbnail.jpg', 'rb') as thumb_f:
        files = {
            'video': video_f,
            'thumb': thumb_f,
        }
        data_send = {
            'chat_id': telegram_chat_id,
            'caption': f"<blockquote expandable><a href='{video_url}'>{video_title}</a></blockquote>\n\n🔸 <a href='https://t.me/N17_Media'>N17 TV</a> | <a href='https://t.me/N17_Tottenham'>N17 Tottenham</a> | <a href='https://t.me/+2TG8ZxphObwzN2Q0'>VivaSpurs</a>",
            'parse_mode': "HTML"
        }
        response_send = requests.post(url_send, data=data_send, files=files)

    if response_send.ok and len(video_title) > 10:
        result = response_send.json()['result']
        message_id = result['message_id']
        try:
            fa = ask_gemini(user_prompt=video_title, system_prompt=config["Translation System Prompt"])
        except Exception:
            fa = video_title

        url_edit = f'https://api.telegram.org/bot{telegram_bot_token}/editMessageCaption'
        data_edit = {
            'chat_id': telegram_chat_id,
            'message_id': message_id,
            'caption': f"{fa}\n\n<blockquote expandable><a href='{video_url}'>{video_title}</a></blockquote>\n\n🔸 <a href='https://t.me/N17_Media'>N17 TV</a> | <a href='https://t.me/N17_Tottenham'>N17 Tottenham</a> | <a href='https://t.me/+2TG8ZxphObwzN2Q0'>VivaSpurs</a>",
            'parse_mode': "HTML"
        }
        response_edit = requests.post(url_edit, data=data_edit)

        if not response_edit.ok:
            print(f"Failed to edit caption: {response_edit.text}")
        return True
    else:
        print(f"Failed to send video: {response_send.text}")
        return False


def download_and_upload_video(video_id, video_title, telegram_bot_token, telegram_chat_id):
    """Downloads a 360p copy via cobalt and uploads it to Telegram. Returns True on success."""
    final_file = f"{video_id}_final.mp4"
    try:
        ok = cobalt_download_video(video_id, final_file)
        if not ok:
            print(f"Cobalt download failed for '{video_title}' ({video_id}); will retry next run.")
            return False

        size = os.path.getsize(final_file)
        print(f"Downloaded '{video_title}' ({video_id}) at {size / (1024 * 1024):.1f} MB")

        if size > TELEGRAM_API_LIMIT_BYTES:
            msg = (f"'{video_title}' ({video_id}) is {size / (1024 * 1024):.1f} MB even at 360p, "
                   f"which is over Telegram's 50 MB bot upload limit. Skipping upload.")
            print(msg)
            send_message(config, msg, ADMIN_CHAT_ID)
            return True  # mark as seen so we don't retry a video that can never fit

        success = upload_video_to_telegram(video_id, video_title, final_file,
                                            telegram_bot_token, telegram_chat_id)
        return success

    except Exception as e:
        a = f"An unexpected error occurred processing '{video_title}' ({video_id}): {e}"
        print(a)
        send_message(config, a, ADMIN_CHAT_ID)
        return False
    finally:
        for f in (final_file, 'thumbnail.jpg'):
            if os.path.exists(f):
                os.remove(f)


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main():
    if not all([YOUTUBE_API_KEY, YOUTUBE_CHANNEL_ID, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID]):
        print("Error: one or more required environment variables/config values are missing.")
        return
    # COBALT_API_URL is optional - if unset, we auto-pick a public instance per run.

    uploads_playlist_id = get_channel_uploads_playlist_id(youtube, YOUTUBE_CHANNEL_ID)
    if not uploads_playlist_id:
        print("Could not retrieve uploads playlist ID. Exiting.")
        return

    recent_videos = get_recent_videos(youtube, uploads_playlist_id, MAX_RECENT_VIDEOS_TO_CHECK)
    if not recent_videos:
        print("No videos found on the channel.")
        return

    seen_ids = load_seen_videos()

    if seen_ids is None:
        # First ever run: establish a baseline without posting the entire
        # back catalogue. Only genuinely new videos from now on get posted.
        seen_ids = {v['id'] for v in recent_videos}
        save_seen_videos(seen_ids)
        print(f"No {SEEN_VIDEOS_FILE} found - initialized baseline with "
              f"{len(seen_ids)} existing video(s). Nothing will be posted this run.")
        return

    new_videos = [v for v in recent_videos if v['id'] not in seen_ids]

    if not new_videos:
        print("No new videos found.")
        return

    # Oldest first, so the channel's Telegram feed stays in chronological order.
    new_videos.sort(key=lambda v: v['published_at'])

    print(f"Found {len(new_videos)} new video(s) to process.")
    for video in new_videos:
        success = download_and_upload_video(video['id'], video['title'],
                                              TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
        if success:
            seen_ids.add(video['id'])
            save_seen_videos(seen_ids)  # persist incrementally so a mid-run crash doesn't lose progress


if __name__ == "__main__":
    main()