import subprocess
import json
import os
import requests

with open('config.json', 'r', encoding='utf-8') as file:
    config = json.load(file)

TELEGRAM_BOT_TOKEN = config["Bot Token"]
TELEGRAM_CHAT_ID = config["Main Chat id"]
LARGE_FILE_CHAT_ID = config["Summary Chat id"]
TELEGRAM_API_LIMIT_BYTES = 50 * 1024 * 1024

HISTORY_FILE = "downloaded_tiktoks.json"

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_history(video_ids):
    with open(HISTORY_FILE, "w") as f:
        json.dump(list(video_ids), f)

def get_video_id_from_url(url):
    # TikTok URLs look like: https://www.tiktok.com/@user/video/VIDEO_ID
    return url.rstrip("/").split("/")[-1]

def download_latest_tiktoks(username, max_downloads=10):
    url = f"https://www.tiktok.com/@{username}"
    print(f"Checking TikToks from: {url}")

    # Let yt-dlp list the videos first
    cmd = ["yt-dlp", "--dump-json", "--flat-playlist", url]
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    downloaded_ids = load_history()
    new_ids = set()
    video_lines = result.stdout.strip().split("\n")

    count = 0
    for line in video_lines:
        video_info = json.loads(line)
        video_id = video_info.get("id")
        video_url = f"https://www.tiktok.com/@{username}/video/{video_id}"
        
        if video_id in downloaded_ids:
            print(f"Skipping already downloaded: {video_url}")
            count += 1
            continue

        print(f"Downloading new video: {video_url}")
        output_template = "%(id)s.%(ext)s"

        subprocess.run([
            "yt-dlp", "-o", output_template, video_url
        ], check=True)
        # for getting the name
        dlp_result = subprocess.run(
            ["yt-dlp", "--print", "filename", "-o", output_template, video_url],
            capture_output=True, text=True, check=True
        )

        new_ids.add(video_id)
        count += 1

        raw_file = dlp_result.stdout.strip()
        if os.path.getsize(raw_file) > TELEGRAM_API_LIMIT_BYTES:
            compressed_file = f"{video_id}_360p.mp4"
            print(f"compressing new video: {raw_file} to {compressed_file}")
            ffmpeg_cmd = [
                "ffmpeg", "-i", raw_file,
                "-vf", "scale=360:-2",
                "-c:v", "libx264", "-crf", "23", "-preset", "slow",
                "-c:a", "aac", "-b:a", "128k",
                compressed_file
            ]
            subprocess.run(ffmpeg_cmd, check=True)
            os.remove(raw_file)

            file_size_mb = os.path.getsize(compressed_file) / (1024 * 1024)
            target_chat_id = TELEGRAM_CHAT_ID if file_size_mb <= 7 else LARGE_FILE_CHAT_ID

            with open(compressed_file, "rb") as f:
                response = requests.post(
                    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo",
                    files={'video': f},
                    data={'chat_id': target_chat_id,
                        'caption': f"New video: \n{video_url}"}
                )
                response.raise_for_status()
            
            os.remove(compressed_file)
        else:
            os.remove(raw_file)

        if count >= max_downloads:
            break

    # Update history
    all_ids = downloaded_ids.union(new_ids)
    save_history(all_ids)

if __name__ == "__main__":
    download_latest_tiktoks("spursofficial")  # Replace with actual username
