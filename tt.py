import subprocess
import json
import os
import requests
from gemini import ask_gemini
from telegram import send_image, send_message

from bs4 import BeautifulSoup
from datetime import datetime
import re
import cloudscraper
from datetime import datetime, timedelta

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
                fa = ask_gemini(user_prompt=title, system_prompt=config["Translation System Prompt"])
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

            url_send = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo'
            files = {
                'video': open(compressed_file, 'rb'),
            }
            data_send = {
                'chat_id': target_chat_id,
                'caption': f"<blockquote expandable><a href='{video_url}'>{title}</a></blockquote>\n\n{hyperlink}",
                'parse_mode': "HTML"
            }
            response_send = requests.post(url_send, data=data_send, files=files)

            if response_send.ok and len(title)>10:
                # Parse the response to get the message_id
                result = response_send.json()['result']
                message_id = result['message_id']

                fa = ask_gemini(user_prompt=title, system_prompt=config["Translation System Prompt"])
                
                # Edit the message caption with the translated version
                url_edit = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/editMessageCaption'
                data_edit = {
                    'chat_id': target_chat_id,
                    'message_id': message_id,
                    'caption': f"{fa}\n\n<blockquote expandable><a href='{video_url}'>{title}</a></blockquote>\n\n{hyperlink}",
                    'parse_mode': "HTML"
                }
                response_edit = requests.post(url_edit, data=data_edit)
                
                # Optional: Check if edit was successful
                if not response_edit.ok:
                    print(f"Failed to edit caption: {response_edit.text}")
            else:
                print(f"Failed to send video: {response_send.text}")
            
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

    # Highlights video (YouTube iframe)
    iframe = soup.find("iframe", src=True)
    if iframe and "youtube.com" in iframe["src"]:
        match_info["highlight_video"] = iframe["src"]
    else: 
        match_info["highlight_video"] = ""

    # Match report
    report_container = soup.find("article", class_="prose")
    if report_container:
        paragraphs = report_container.find_all("p")
        report_text = '\n'.join(p.get_text(strip=True) for p in paragraphs)
        match_info["report"] = re.sub(r'\s+', ' ', report_text).strip()
    else:
        match_info["report"]=""

    # Goalscorers
    # Match info structure
    match_info["teams"] = {}

    # --- TEAM 1 (the first score block, e.g. Spurs) ---
    team1_block = soup.select_one("p.text-3xl") or soup.select_one("p.text-3xl.md:text-5xl")
    if team1_block:
        # Find the parent container
        container = team1_block.find_parent("div")

        # Team name and score
        team_name = container.find("span", class_="text-navy-400").get_text(strip=True)
        team_score = container.find("span", class_="text-sky-500").get_text(strip=True)

        match_info["teams"][team_name] = {"score": team_score, "goals": {}, "cards": {}}

        # Loop through goals/cards
        for li in container.select("ul li.flex.items-center"):
            player = li.find("a") or li.find("span", class_="font-bold")
            if not player:
                continue
            player_name = player.get_text(strip=True)

            for div in li.select("div.inline-flex.items-center.gap-1"):
                minute = div.find("span", class_="text-sky-500")
                if not minute:
                    continue
                minute_text = minute.get_text(strip=True)

                svg = div.find("svg")
                svg_str = str(svg) if svg else ""
                if "#b91c1c" in svg_str:  # red card
                    match_info["teams"][team_name]["cards"].setdefault(player_name, []).append(
                        {"type": "red", "minute": minute_text}
                    )
                elif "#eab147" in svg_str:  # yellow card
                    match_info["teams"][team_name]["cards"].setdefault(player_name, []).append(
                        {"type": "yellow", "minute": minute_text}
                    )
                elif "#ba0000" in svg_str:  # own goal
                    match_info["teams"][team_name]["cards"].setdefault(player_name, []).append(
                        {"type": "own goal", "minute": minute_text}
                    )
                elif "#7d7d7d" in svg_str:  # missed penalty
                    match_info["teams"][team_name]["cards"].setdefault(player_name, []).append(
                        {"type": "missed pen", "minute": minute_text}
                    )
                else:  # goal
                    match_info["teams"][team_name]["goals"].setdefault(player_name, []).append(minute_text)

    # --- TEAM 2 (the flex gap-4 block, e.g. West Ham) ---
    for block in soup.select("div.flex.gap-4"):
        team_name_tag = block.select_one("p.text-navy-400")
        score_tag = block.select_one("p.text-sky-500")
        if not team_name_tag:
            continue

        team_name = team_name_tag.get_text(strip=True)
        team_score = score_tag.get_text(strip=True) if score_tag else None

        match_info["teams"][team_name] = {"score": team_score, "goals": {}, "cards": {}}

        for li in block.select("ul li.flex.items-center"):
            player = li.find("a") or li.find("span", class_="font-bold")
            if not player:
                continue
            player_name = player.get_text(strip=True)

            for div in li.select("div.inline-flex.items-center.gap-1"):
                minute = div.find("span", class_="text-sky-500")
                if not minute:
                    continue
                minute_text = minute.get_text(strip=True)

                svg = div.find("svg")
                svg_str = str(svg) if svg else ""
                if "#b91c1c" in svg_str:  # red card
                    match_info["teams"][team_name]["cards"].setdefault(player_name, []).append(
                        {"type": "red", "minute": minute_text}
                    )
                elif "#eab147" in svg_str:  # yellow card
                    match_info["teams"][team_name]["cards"].setdefault(player_name, []).append(
                        {"type": "yellow", "minute": minute_text}
                    )
                elif "#ba0000" in svg_str:  # own goal
                    match_info["teams"][team_name]["cards"].setdefault(player_name, []).append(
                        {"type": "own goal", "minute": minute_text}
                    )
                elif "#7d7d7d" in svg_str:  # missed penalty
                    match_info["teams"][team_name]["cards"].setdefault(player_name, []).append(
                        {"type": "missed pen", "minute": minute_text}
                    )

                else:  # goal
                    match_info["teams"][team_name]["goals"].setdefault(player_name, []).append(minute_text)


    return match_info

def format_match(teams: dict) -> str:
    lines = []
    for team, data in teams.items():
        # Team header
        score = data.get("score", "0")
        lines.append(f"{team} - {score}:")
        
        # Goals
        goals = data.get("goals", {})
        for player, times in goals.items():
            lines.append(f"{"⚽" * len(times)} {player} - {', '.join(times)}")
        
        # Cards
        cards = data.get("cards", {})
        for player, card_list in cards.items():
            for card in card_list:
                ctype = card.get("type", "").lower()
                minute = card.get("minute", "")
                if ctype == "red":
                    lines.append(f"🔴 {player} - {minute}")
                elif ctype == "yellow":
                    lines.append(f"🟨 {player} - {minute}")
                elif ctype == "own goal":
                    lines.append(f"⚽🤦‍♂️ {player} - {minute}")
                elif ctype == "missed pen":
                    lines.append(f"\n🥅❌ {player} - {minute}")
        
        lines.append("")  # blank line after each team
    
    return "\n".join(lines).strip()

def OTD():
    today = datetime.now()
    try:
        date_input = today.strftime("%-d-%B").lower()  # works on Linux/Mac
    except:
        date_input = today.strftime("%#d-%B").lower()

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
    
    text = f"🗓️ On this day on {match_data["date"]}\n⏳at {(datetime.strptime(match_data["kick_off"], "%H:%M") + timedelta(hours=2.5)).strftime("%H:%M")}\n\n🔸{match_data["title"].split(' ')[0]} {match_data["opposition"]} at {match_data["venue"]} in {match_data["competition"]}"
    if match_data["teams"]:
        text = text + "\n\n" + format_match(match_data["teams"])
    if match_data["report"]: 
        additional = "باید علاوه بر ترجمه دقیق اتفاقات بازی را خلاصه کنی. تو باید اتفاقات بازی را کامل و مفید و جذاب شرح دهی و صحبت های مربی را هم در ترجمه قرار دهی اما در کل نباید متن خروجی بیشتر از 4000 کاراکتر باشد. چیزی جز خلاصه بازی به زبان فارسی نگو و تنها وظایفت را انجام بده و متن خروجی را در قالب جند پاراگراف ارائه بده"
        # try:
        #     fa = translate(config, match_data["report"], "0", additional)
        # except:
        #     fa = translate(config, match_data["report"], "1", additional) + "`"
        fa = translate(config, match_data["report"], "1", additional)
        text = text + f"\n\n<blockquote expandable>{fa[:3600]}</blockquote>"
    if match_data["highlight_video"]:
        text = text + f"\n\n<a href='{match_data["highlight_video"]}'>📽️ Highlight Video</a>"
    print(text)
    send_message(config, text + f"\n\n{hyperlink}", config["Main Chat id"])

if __name__ == "__main__":
    download_latest_tiktoks("spursofficial")
    # try:
    #     OTD()
    # except Exception as e:
    #     print(e)
    #     send_message(config, f"{e}", 1140637004)
