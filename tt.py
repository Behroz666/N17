import subprocess
import json
import os
import requests
from translate import translate
from telegram import send_image, send_message

from bs4 import BeautifulSoup
from datetime import datetime
import re
import cloudscraper

hyperlink = "🔹 <a href='https://t.me/N17_Tottenham'>N17 Tottenham</a> | <a href='https://t.me/+2TG8ZxphObwzN2Q0'>VivaSpurs</a>"

with open('config.json', 'r', encoding='utf-8') as file:
    config = json.load(file)

TELEGRAM_BOT_TOKEN = os.environ.get('BOT_TOKEN')
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

def download_latest_tiktoks(username):
    max_downloads=10
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
        if count >= max_downloads:
            print("breaking")
            break
        print(count)
        video_info = json.loads(line)
        video_id = video_info.get("id")
        title = video_info.get("title")
        thumbnail_url = video_info["thumbnails"][0]["url"]
        video_url = f"https://www.tiktok.com/@{username}/video/{video_id}"
        
        if video_id in downloaded_ids:
            print(f"Skipping already downloaded: {video_url}")
            count += 1
            continue

        if "photomode" in thumbnail_url:
            if len(title)>10:
                fa = translate(config, title)
            else:
                fa = title
            text = f"{fa}\n\n<blockquote expandable><a href='{video_url}'>{title}</a></blockquote>\n\n{hyperlink}"
            send_image(config, text, thumbnail_url)
            new_ids.add(video_id)
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
        if os.path.getsize(raw_file) < TELEGRAM_API_LIMIT_BYTES:
            compressed_file = f"{video_id}_360p.mp4"
            print(f"compressing new video: {raw_file} to {compressed_file}")
            ffmpeg_cmd = [
                "ffmpeg", "-i", raw_file,
                "-vf", "scale=360:-2",
                "-c:v", "libx264", "-crf", "23", "-preset", "faster",
                "-c:a", "aac", "-b:a", "128k",
                compressed_file
            ]
            subprocess.run(ffmpeg_cmd, check=True)
            os.remove(raw_file)

            file_size_mb = os.path.getsize(compressed_file) / (1024 * 1024)
            target_chat_id = TELEGRAM_CHAT_ID if file_size_mb <= 7 else LARGE_FILE_CHAT_ID

            if len(title)>10:
                fa = translate(config, title)
            else:
                fa = title

            with open(compressed_file, "rb") as f:
                response = requests.post(
                    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo",
                    files={'video': f},
                    data={'chat_id': target_chat_id,
                        'caption': f"{fa}\n\n<blockquote expandable><a href='{video_url}'>{title}</a></blockquote>\n\n{hyperlink}",
                        "parse_mode": "HTML"}
                )
                response.raise_for_status()
            
            os.remove(compressed_file)
        else:
            os.remove(raw_file)

    # Update history
    all_ids = downloaded_ids.union(new_ids)
    save_history(all_ids)

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/117.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Referer": "https://thfcdb.com/",
}

def scrape_match_urls(date_str):
    base_url = "https://thfcdb.com/dates/"
    target_url = f"{base_url}{date_str}/matches"

    try:
        # response = requests.get(target_url, headers=headers)
        # response.raise_for_status()
        scraper = cloudscraper.create_scraper()  
        response = scraper.get(target_url, headers=headers)
    except requests.RequestException as e:
        print(f"Error fetching {target_url}: {e}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")

    links = []
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if "/matches/" in href:
            if href.startswith("/"):
                href = "https://thfcdb.com" + href
            links.append(href)

    return sorted(set(links), reverse=True)  # newest first


def scrape_match_info(match_url):
    """Scrape structured match info including opposition, competition, date, kick-off, venue, highlights, report, and goalscorers."""
    try:
        # response = requests.get(match_url, headers=headers)
        # response.raise_for_status()
        scraper = cloudscraper.create_scraper()  
        response = scraper.get(match_url, headers=headers)
    except requests.RequestException as e:
        print(f"Error fetching {match_url}: {e}")
        return {}

    soup = BeautifulSoup(response.text, "html.parser")

    match_info = {"url": match_url}

    # Title
    header = soup.find("h1")
    if header:
        match_info["title"] = header.get_text(strip=True)

    # Competition & Opposition
    competition_select = soup.find("select", id="matchesToShow")
    if competition_select:
        options = competition_select.find_all("option")
        if len(options) >= 2:
            match_info["opposition"] = options[0].get_text(strip=True)
            match_info["competition"] = options[1].get_text(strip=True)

    # Date
    date_tag = soup.find("dt", string=lambda t: t and "Date" in t)
    if date_tag:
        date_value = date_tag.find_next("p")
        if date_value:
            match_info["date"] = date_value.get_text(strip=True)

    # Kick Off
    kickoff_tag = soup.find("dt", string=lambda t: t and "Kick Off" in t)
    if kickoff_tag:
        kickoff_value = kickoff_tag.find_next("p")
        if kickoff_value:
            match_info["kick_off"] = kickoff_value.get_text(strip=True)

    # Venue
    venue_tag = soup.find("dt", string=lambda t: t and "Venue" in t)
    if venue_tag:
        venue_value = venue_tag.find_next("p")
        if venue_value:
            match_info["venue"] = venue_value.get_text(strip=True)

    # Score
    score = soup.find(class_="score")
    if score:
        match_info["score"] = score.get_text(strip=True)

    # Extra details in tables
    details = {}
    for row in soup.select("table tr"):
        cells = row.find_all("td")
        if len(cells) == 2:
            key = cells[0].get_text(strip=True)
            val = cells[1].get_text(strip=True)
            details[key] = val
    if details:
        match_info["details"] = details

    # Highlights video (YouTube iframe)
    iframe = soup.find("iframe", src=True)
    if iframe and "youtube.com" in iframe["src"]:
        match_info["highlight_video"] = iframe["src"]

    # Match report
    report_container = soup.find("article", class_="prose")
    if report_container:
        paragraphs = report_container.find_all("p")
        report_text = '\n'.join(p.get_text(strip=True) for p in paragraphs)
        match_info["report"] = re.sub(r'\s+', ' ', report_text).strip()

    # Goalscorers
    match_info["goalscorers"] = []
    for li in soup.select("ul li.flex.items-center"):
        player = li.find("a") or li.find("span", class_="font-bold")
        minute = li.find("span", class_="text-sky-500")
        if player and minute:
            match_info["goalscorers"].append(f"{player.get_text(strip=True)} - {minute.get_text(strip=True)}")

    return match_info

def OTD():
    today = datetime.now()
    date_input = today.strftime("%d-%B").lower()

    match_urls = scrape_match_urls(date_input)
    print(f"Found {len(match_urls)} match URLs for {date_input}:")
    for url in match_urls:
        print(url)

    if match_urls:
        newest_match_url = match_urls[0]
        print("\nScraping detailed info from:", newest_match_url)
        match_data = scrape_match_info(newest_match_url)
        print("\nStructured Match Info:")
        for k, v in match_data.items():
            print(f"{k}: {v}")
    
    text = f"On this day on {match_data["date"]} at {match_data["kick_off"]}\n\n{match_data["title"].split(' ')[0]} {match_data["opposition"]} at {match_data["venue"]} in {match_data["competition"]}"
    if match_data["goalscorers"]:
        text = text + "\n\nGoalscorers :"
        for name in match_data["goalscorers"]:
            text = text + "\n" + name
    if match_data["report"]: 
        fa = translate(config, match_data["report"])
        text = text + f"\n\n<blockquote expandable>{fa[:3600]}</blockquote>"
    if match_data["highlight_video"]:
        text = text + f"\n\n<a href='{match_data["highlight_video"]}'>📽️ Highlight Video</a>"
    print(text)
    send_message(config, text + f"\n\n{hyperlink}", config["Main Chat id"])

if __name__ == "__main__":
    download_latest_tiktoks("spursofficial")
    OTD()
