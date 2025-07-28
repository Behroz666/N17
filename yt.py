import os
import datetime
import requests
from googleapiclient.discovery import build
import yt_dlp
import json # To parse yt_dlp output for size estimation

with open('config.json', 'r', encoding='utf-8') as file:
    config = json.load(file)

# --- Configuration Constants ---
# Telegram Bot API file size limit in bytes (50 MB)
TELEGRAM_API_LIMIT_BYTES = 50 * 1024 * 1024

# --- Environment Variables (to be set in GitHub Secrets) ---
# Your YouTube Data API v3 key
YOUTUBE_API_KEY = config["Google"]
# The ID of the YouTube channel you want to monitor
YOUTUBE_CHANNEL_ID = "TottenhamHotspur"
# Your Telegram Bot Token (get from BotFather)
TELEGRAM_BOT_TOKEN = config["Bot Token"]
# The chat ID where the bot should post videos (can be a user ID or a group chat ID)
TELEGRAM_CHAT_ID = config["Summary Chat id"]

# --- YouTube API Setup ---
# Build the YouTube API client
youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)

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

def get_video_info_and_size(video_url, quality_format):
    """
    Simulates a yt-dlp download to get video information and estimated file size.
    Returns (estimated_size_bytes, filename) or (None, None) on failure.
    """
    ydl_opts = {
        'format': quality_format,
        'simulate': True,  # Only simulate, don't download
        'force_generic_extractor': True, # Important for consistent info extraction
        'quiet': True,     # Suppress console output
        'no_warnings': True, # Suppress warnings
        'skip_download': True, # Ensure no download occurs
        'print_json': True, # Print info as JSON
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(video_url, download=False)
            # yt-dlp returns a lot of info, we need to find the best format's size
            # Sometimes 'filesize' is present directly, sometimes 'filesize_approx'
            # Or we might need to iterate through 'formats' to find the one matching our quality_format
            
            # For 'print_json': True, the output is a JSON string
            # We need to re-extract info from the string output.
            # A more robust way is to use the 'extract_info' method directly.
            
            # If info_dict is already a dict (which it should be if download=False),
            # we can directly access its properties.
            
            # Find the best format that matches the quality_format
            best_format = None
            if 'formats' in info_dict:
                for f in info_dict['formats']:
                    if f.get('format_note') and quality_format in f.get('format_note'):
                        best_format = f
                        break
                    # More robust check based on height/vcodec
                    if 'height' in f and 'vcodec' in f and f['vcodec'] != 'none':
                        if '360p' in quality_format and f['height'] <= 360:
                            best_format = f
                            break
                        if '240p' in quality_format and f['height'] <= 240:
                            best_format = f
                            break
            
            if best_format:
                estimated_size = best_format.get('filesize') or best_format.get('filesize_approx')
                filename = ydl.prepare_filename(info_dict) # Get the expected filename
                return estimated_size, filename
            else:
                print(f"Could not find a suitable format for {video_url} with quality {quality_format}")
                return None, None
    except yt_dlp.utils.DownloadError as e:
        print(f"yt-dlp error getting info for {video_url} with {quality_format}: {e}")
        return None, None
    except Exception as e:
        print(f"General error getting video info for {video_url} with {quality_format}: {e}")
        return None, None

def download_and_upload_video(video_id, video_title, telegram_bot_token, telegram_chat_id):
    """
    Downloads a video from YouTube at the best possible quality within Telegram's size limit
    and uploads it to Telegram.
    """
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    temp_filename = f"{video_id}.mp4" # Temporary filename for download

    # Define quality formats to try, in order of preference
    # 'bestvideo[height<=360]+bestaudio/best[height<=360]' tries to get separate video/audio and merge,
    # or a combined best stream <= 360p.
    # 'worst' is a general fallback for smallest size.
    quality_options = [
        ('bestvideo[height<=360]+bestaudio/best[height<=360]', '360p'),
        ('bestvideo[height<=240]+bestaudio/best[height<=240]', '240p'),
        ('worst', 'worst_quality') # Fallback to absolute smallest if 240p is still too big
    ]

    download_format = None
    final_filename = None
    estimated_size = None

    # Step 1: Check estimated size for each quality option
    for format_string, quality_name in quality_options:
        print(f"Checking estimated size for {video_title} ({video_id}) at {quality_name}...")
        current_estimated_size, current_filename = get_video_info_and_size(video_url, format_string)

        if current_estimated_size is not None:
            print(f"Estimated size for {quality_name}: {current_estimated_size / (1024 * 1024):.2f} MB")
            if current_estimated_size <= TELEGRAM_API_LIMIT_BYTES:
                download_format = format_string
                estimated_size = current_estimated_size
                final_filename = current_filename # This filename is what yt-dlp would use
                print(f"Selected {quality_name} for download. Estimated size: {estimated_size / (1024 * 1024):.2f} MB")
                break # Found a suitable quality, stop checking
            else:
                print(f"{quality_name} ({current_estimated_size / (1024 * 1024):.2f} MB) is too large for Telegram's {TELEGRAM_API_LIMIT_BYTES / (1024 * 1024):.2f} MB limit.")
        else:
            print(f"Could not get estimated size for {quality_name} for {video_title} ({video_id}).")

    if not download_format:
        print(f"No suitable quality found for '{video_title}' (ID: {video_id}) within Telegram's size limit. Skipping.")
        return

    # Step 2: Download the video
    print(f"Attempting to download '{video_title}' (ID: {video_id}) with format: {download_format}...")
    ydl_opts = {
        'format': download_format,
        'outtmpl': temp_filename, # Save to the temporary filename
        'merge_output_format': 'mp4', # Ensure output is mp4 if merging
        'quiet': True,
        'no_warnings': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
        print(f"Successfully downloaded '{video_title}' to {temp_filename}")

        # Verify actual file size before uploading
        actual_file_size = os.path.getsize(temp_filename)
        print(f"Actual downloaded file size: {actual_file_size / (1024 * 1024):.2f} MB")

        if actual_file_size > TELEGRAM_API_LIMIT_BYTES:
            print(f"Downloaded file '{temp_filename}' is still too large ({actual_file_size / (1024 * 1024):.2f} MB) after download. Skipping upload.")
            return # Don't upload if it's over the limit

        # Step 3: Upload to Telegram
        print(f"Uploading '{video_title}' to Telegram...")
        telegram_api_url = f"https://api.telegram.org/bot{telegram_bot_token}/sendVideo"
        
        with open(temp_filename, 'rb') as video_file:
            files = {'video': video_file}
            data = {
                'chat_id': telegram_chat_id,
                'caption': f"New video: {video_title}\n{video_url}"
            }
            response = requests.post(telegram_api_url, files=files, data=data)

            if response.status_code == 200:
                print(f"Successfully uploaded '{video_title}' to Telegram.")
            else:
                print(f"Failed to upload '{video_title}' to Telegram. Status code: {response.status_code}, Response: {response.text}")

    except yt_dlp.utils.DownloadError as e:
        print(f"yt-dlp error downloading {video_title} ({video_id}): {e}")
    except Exception as e:
        print(f"An unexpected error occurred during download or upload for {video_title} ({video_id}): {e}")
    finally:
        # Clean up the downloaded file
        if os.path.exists(temp_filename):
            os.remove(temp_filename)
            print(f"Cleaned up temporary file: {temp_filename}")

def main():
    """
    Main function to orchestrate the video fetching, downloading, and uploading process.
    """
    # Check if all necessary environment variables are set
    if not all([YOUTUBE_API_KEY, YOUTUBE_CHANNEL_ID, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID]):
        print("Error: One or more environment variables (YOUTUBE_API_KEY, YOUTUBE_CHANNEL_ID, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID) are not set.")
        print("Please set them as GitHub Secrets.")
        return

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
        download_and_upload_video(video['id'], video['title'], TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)

if __name__ == "__main__":
    main()
