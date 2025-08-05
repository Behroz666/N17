import subprocess
import json
import os

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
            continue

        print(f"Downloading new video: {video_url}")
        subprocess.run(["yt-dlp", video_url])
        new_ids.add(video_id)
        count += 1

        if count >= max_downloads:
            break

    # Update history
    all_ids = downloaded_ids.union(new_ids)
    save_history(all_ids)

if __name__ == "__main__":
    download_latest_tiktoks("spursofficial")  # Replace with actual username
