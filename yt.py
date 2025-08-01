import os
import datetime
import requests
from googleapiclient.discovery import build
import yt_dlp
import json # To parse yt_dlp output for size estimation
import tempfile
from telegram import send_message
import subprocess

with open('config.json', 'r', encoding='utf-8') as file:
    config = json.load(file)

# --- Configuration Constants ---
# Telegram Bot API file size limit in bytes (50 MB)
TELEGRAM_API_LIMIT_BYTES = 50 * 1024 * 1024

# --- Environment Variables (to be set in GitHub Secrets) ---
# Your YouTube Data API v3 key
YOUTUBE_API_KEY = config["Google"]
# The ID of the YouTube channel you want to monitor
YOUTUBE_CHANNEL_ID = "UCEg25rdRZXg32iwai6N6l0w"
# Your Telegram Bot Token (get from BotFather)
TELEGRAM_BOT_TOKEN = config["Bot Token"]
# The chat ID where the bot should post videos (can be a user ID or a group chat ID)
TELEGRAM_CHAT_ID = config["Main Chat id"]
# YouTube cookies string from GitHub Secrets
YOUTUBE_COOKIES = os.environ.get('YOUTUBE_COOKIES')

# --- YouTube API Setup ---
# Build the YouTube API client
youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)

def compress_video(input_path: str, output_path: str, crf: int = 28, preset: str = 'slow'):
    """
    Run one-pass FFmpeg re-encode at the given CRF & preset.
    Returns True if the process succeeds.
    """
    cmd = [
        'ffmpeg', '-y',
        '-i', input_path,
        '-c:v', 'libx264', '-crf', str(crf), '-preset', preset,
        '-c:a', 'aac', '-b:a', '64k',
        output_path
    ]
    subprocess.run(cmd, check=True)
    return os.path.exists(output_path)

def compress_to_limit(input_path: str, output_path: str, size_limit: int,
                      start_crf: int = 28, max_crf: int = 40, step: int = 2):
    """
    Loop CRF from start_crf up to max_crf to try and get under size_limit.
    Returns True and leaves output_path if successful; False otherwise.
    """
    crf = start_crf
    while crf <= max_crf:
        compress_video(input_path, output_path, crf=crf)
        if os.path.getsize(output_path) <= size_limit:
            return True
        crf += step
    return False

def get_channel_uploads_playlist_id(youtube_service, channel_id):
    """
    Fetches the uploads playlist ID for a given YouTube channel ID.
    This playlist contains all public videos uploaded by the channel.
    """
    try:
        # Request channel details to get the uploads playlist ID
        request = youtube_service.channels().list(
            part='contentDetails',
            id=channel_id
        )
        response = request.execute()

        if response and response.get('items'):
            # The uploads playlist ID is typically found in contentDetails.relatedPlaylists.uploads
            playlist_id = response['items'][0]['contentDetails']['relatedPlaylists']['uploads']
            print(f"Found uploads playlist ID: {playlist_id}")
            return playlist_id
        else:
            print(f"Could not find uploads playlist for channel ID: {channel_id}")
            return None
    except Exception as e:
        print(f"Error fetching uploads playlist ID: {e}")
        return None

def get_new_videos(youtube_service, playlist_id, published_after_dt):
    """
    Fetches videos from a YouTube playlist that were published after a specific datetime.
    """
    new_videos = []
    next_page_token = None

    # Format the datetime to RFC3339 for YouTube API
    published_after_iso = published_after_dt.isoformat("T") + "Z"
    print(f"Searching for videos published after: {published_after_iso}")

    while True:
        try:
            # Request playlist items
            request = youtube_service.playlistItems().list(
                part='snippet,contentDetails',
                playlistId=playlist_id,
                maxResults=50, # Max results per page
                pageToken=next_page_token
            )
            response = request.execute()

            for item in response.get('items', []):
                video_id = item['contentDetails']['videoId']
                video_title = item['snippet']['title']
                published_at_str = item['snippet']['publishedAt']

                # Parse the publishedAt string to a datetime object
                published_at_dt = datetime.datetime.fromisoformat(published_at_str.replace('Z', '+00:00'))

                # Compare with the threshold datetime
                if published_at_dt > published_after_dt:
                    new_videos.append({'id': video_id, 'title': video_title})
                    print(f"Found new video: '{video_title}' (ID: {video_id}) published at {published_at_dt}")
                else:
                    # Videos are usually returned in reverse chronological order,
                    # so if we hit an old video, we can stop searching.
                    print(f"Video '{video_title}' (ID: {video_id}) published at {published_at_dt} is too old. Stopping search.")
                    next_page_token = None # Stop pagination
                    break # Exit the for loop

            next_page_token = response.get('nextPageToken')
            if not next_page_token:
                break # No more pages

        except Exception as e:
            print(f"Error fetching new videos: {e}")
            break # Exit the while loop on error

    return new_videos

def get_video_info_and_size(video_url, quality_format, cookies_file_path=None):
    """
    Simulates a yt-dlp download to get video information and estimated file size.
    Returns (estimated_size_bytes, filename) or (None, None) on failure.
    """
    ydl_opts = {
        'format': quality_format, # yt-dlp will select the best matching format
        'simulate': True,  # Only simulate, don't download
        'force_generic_extractor': True, # Important for consistent info extraction
        'quiet': True,     # Suppress console output
        'no_warnings': True, # Suppress warnings
        'skip_download': True, # Ensure no download occurs
        # 'print_json': True, # Not strictly necessary when using as library, extract_info returns dict
    }
    if cookies_file_path:
        ydl_opts['cookiefile'] = cookies_file_path # Pass the cookie file path

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(video_url, download=False)
            
            # After extract_info, info_dict should contain details of the *selected* format
            # based on the 'format' option.
            estimated_size = info_dict.get('filesize') or info_dict.get('filesize_approx')
            filename = ydl.prepare_filename(info_dict) # Get the expected filename
            
            if estimated_size is not None:
                return estimated_size, filename
            else:
                print(f"Could not get estimated size from info_dict for {video_url} with quality {quality_format}. Info_dict keys: {info_dict.keys()}")
                return None, None
    except yt_dlp.utils.DownloadError as e:
        a = f"yt-dlp error getting info for {video_url} with {quality_format}: {e}"
        print(a)
        send_message(config, f"YT error\n\n{a}", 1140637004)
        return None, None
    except Exception as e:
        a = f"General error getting video info for {video_url} with {quality_format}: {e}"
        print(a)
        send_message(config, f"YT error\n\n{a}", 1140637004)
        return None, None

def download_and_upload_video(video_id, video_title, telegram_bot_token,
                              telegram_chat_id, youtube_cookies_str):
    video_url = f"https://youtube.com/watch?v={video_id}"
    raw_file = f"{video_id}_raw.mp4"
    base_compressed = f"{video_id}_base.mp4"
    final_file = f"{video_id}_final.mp4"
    try:
        # 1. Download at 360p
        ydl_opts = {
            'format': 'best[height<=360]',
            'outtmpl': raw_file,
            'quiet': True, 'no_warnings': True
        }
        if youtube_cookies_str:
            with tempfile.NamedTemporaryFile('w', delete=False) as ck:
                ck.write(youtube_cookies_str)
                ydl_opts['cookiefile'] = ck.name

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])

        # 2. Base recompress (everyone gets this)
        compress_video(raw_file, base_compressed, crf=28, preset='slow')
        os.remove(raw_file)

        # 3. If still too big, loop tighter CRF
        if os.path.getsize(base_compressed) > TELEGRAM_API_LIMIT_BYTES:
            success = compress_to_limit(
                base_compressed, final_file,
                TELEGRAM_API_LIMIT_BYTES,
                start_crf=30, max_crf=40, step=2
            )
            if not success:
                print(f"Still >50 MB after crf loop; skipping upload of {video_title}")
                os.remove(base_compressed)
                return
            os.remove(base_compressed)
        else:
            # base_compressed is already under limit
            os.rename(base_compressed, final_file)

        # 4. Upload final_file
        with open(final_file, 'rb') as f:
            requests.post(
                f"https://api.telegram.org/bot{telegram_bot_token}/sendVideo",
                files={'video': f},
                data={'chat_id': telegram_chat_id,
                    'caption': f"New video: {video_title}\n{video_url}"}
            )

        os.remove(final_file)
        if 'cookiefile' in ydl_opts and os.path.exists(ydl_opts['cookiefile']):
            os.remove(ydl_opts['cookiefile'])
    except yt_dlp.utils.DownloadError as e:
        a = f"yt-dlp error downloading {video_title} ({video_id}): {e}"
        print(a)
        send_message(config, f"YT error\n\n{a}", 1140637004)
    except Exception as e:
        a = f"An unexpected error occurred during download or upload for {video_title} ({video_id}): {e}"
        print(a)
        send_message(config, f"YT error\n\n{a}", 1140637004)

def main():
    """
    Main function to orchestrate the video fetching, downloading, and uploading process.
    """
    # Check if all necessary environment variables are set
    if not all([YOUTUBE_API_KEY, YOUTUBE_CHANNEL_ID, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID]):
        print("Error: One or more required environment variables (YOUTUBE_API_KEY, YOUTUBE_CHANNEL_ID, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID) are not set.")
        print("Please set them as GitHub Secrets.")
        return
    
    # YOUTUBE_COOKIES is optional, so it's not part of the 'all' check

    # Calculate the datetime 24 hours ago
    # Use timezone-aware datetime for comparison with YouTube's ISO format
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    last_24_hours_dt = now_utc - datetime.timedelta(hours=24)
    print(f"Current UTC time: {now_utc}")
    print(f"Looking for videos published after: {last_24_hours_dt}")

    # Get the uploads playlist ID for the channel
    uploads_playlist_id = get_channel_uploads_playlist_id(youtube, YOUTUBE_CHANNEL_ID)
    if not uploads_playlist_id:
        print("Could not retrieve uploads playlist ID. Exiting.")
        return

    # Get new videos published in the last 24 hours
    new_videos = get_new_videos(youtube, uploads_playlist_id, last_24_hours_dt)

    if not new_videos:
        print("No new videos found in the last 24 hours.")
        return

    print(f"Found {len(new_videos)} new video(s) to process.")
    for video in new_videos:
        download_and_upload_video(video['id'], video['title'], TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, YOUTUBE_COOKIES)

if __name__ == "__main__":
    main()

