import subprocess
import json
import os
import tempfile
from telegram import send_image, send_message, send_gallery, pin_message, delete_message
import time
from gemini import ask_gemini, ask_gemini_structured
from pydantic import BaseModel, Field
import requests
from datetime import datetime, timedelta, timezone, time as dt_time
from googleapiclient.discovery import build
from bs4 import BeautifulSoup

RSS_URL = os.environ.get('RSS_URL')

hyperlink = "🔹 <a href='https://t.me/N17_Tottenham'>N17 Tottenham</a> | <a href='https://t.me/+2TG8ZxphObwzN2Q0'>VivaSpurs</a>"

def get_twitter_preview_url(twitter_url):
    # Normalize URL and use a crawler User-Agent to get static HTML meta tags
    url = twitter_url.replace("x.com", "twitter.com")
    headers = {"User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        print(response)
        
        soup = BeautifulSoup(response.text, 'html.parser')
        image_tag = (
            soup.find("meta", property="twitter:image") or 
            soup.find("meta", property="og:image") or
            soup.find("meta", attrs={"name": "twitter:image"})
        )
        
        if image_tag and image_tag.get("content"):
            image_url = image_tag["content"]
            # Append modifier to fetch the highest available resolution
            if "twimg.com" in image_url and "name=" not in image_url:
                image_url += "?name=large"
            return image_url
            
    except requests.RequestException:
        pass
        
    return None

def get_community_posts(channel_url):
    # Create a temporary directory so we don't clutter your main folders
    with tempfile.TemporaryDirectory() as tmpdir:
        
        # Build the CLI command
        # -f specifies the output folder path
        command = ["yp-dl", "-f", tmpdir, "-l", "10", channel_url]
        
        print(f"Scraping community posts for {channel_url}...")
        
        # Run the command and wait for it to finish
        result = subprocess.run(command, capture_output=True, text=True)
        
        if result.returncode != 0:
            print("Error executing yp-dl:")
            print(result.stderr)
            return None

        # Look for the generated JSON file in the temporary directory
        files = [f for f in os.listdir(tmpdir) if f.endswith('.json')]
        
        if not files:
            print("No JSON file was generated. Check if the channel URL is valid.")
            return None
        
        # Read the first json file found
        json_file_path = os.path.join(tmpdir, files[0])
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        return data

with open('config.json', 'r', encoding='utf-8') as file:
    config = json.load(file)

SEEN_VIDEOS_FILE = "seen_videos.json"
YOUTUBE_API_KEY = os.environ.get('GOOGLE')
YOUTUBE_CHANNEL_IDS = [{"channel id": "UCUz_XIKFQOrliSqPZWJBq2g", "summarize": False, "max videos" : 5}, {"channel id": "UCEg25rdRZXg32iwai6N6l0w", "summarize": False, "max videos": 50}, {"channel id": "UC-HSLEEHVlnqlgTB7UptLeg", "summarize": False, "max videos" : 1}]

youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)

with open(SEEN_VIDEOS_FILE, 'r', encoding='utf-8') as f:
    data = json.load(f)
seen_ids = set(data.get('video_ids', []))

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
for channel in YOUTUBE_CHANNEL_IDS:
    YOUTUBE_CHANNEL_ID = channel["channel id"]
    MAX_RECENT_VIDEOS_TO_CHECK = channel["max videos"]
    uploads_playlist_id = get_channel_uploads_playlist_id(youtube, YOUTUBE_CHANNEL_ID)

    if not uploads_playlist_id:
        print("Could not retrieve uploads playlist ID. Exiting.")
    else:
        recent_videos = get_recent_videos(youtube, uploads_playlist_id, MAX_RECENT_VIDEOS_TO_CHECK)
        if not recent_videos:
            print("No videos found on the channel.")
        else:
            new_videos = [v for v in recent_videos if v['id'] not in seen_ids]
            if not new_videos:
                print("No new videos found.")
            else:
                new_videos.sort(key=lambda v: v['published_at'])
                print(f"Found {len(new_videos)} new video(s) to process.")
                for video in new_videos:
                    video_link = f"https://www.youtube.com/watch?v={video['id']}"
                    thumbnail_url = f"https://img.youtube.com/vi/{video['id']}/maxresdefault.jpg"
                    if not channel["summarize"]:
                        fa = ask_gemini(user_prompt=video['title'], system_prompt=config["Translation System Prompt"])
                        message = f"<a href='{video_link}'>{fa}</a>\n\n{hyperlink} | <a href='https://t.me/N17_Media'>N17 TV</a>"
                        message_id = send_image(config, message, thumbnail_url, chat_id=config["Media Chat id"])
                        time.sleep(3)
                    else:
                        class YouTubeVideoAnalysis(BaseModel):
                            translated_title: str = Field(
                                description="The Persian translation of the YouTube video title."
                            )
                            summary: str = Field(
                                description="A comprehensive summary of the video content in Persian. Must be strictly less than 3500 characters."
                            )
                    

                        prompt = (
                            "1. Translate the video title accurately into Persian.\n"
                            "2. Provide a detailed summary of the video content strictly in Persian. "
                            "The summary must be informative, high-quality, and strictly less than 3500 characters."
                        )

                        data = (
                            f"Video title: «{video['title']}»\n\n"
                            f"video url: {video_link}\n\n"
                        )

                        youtube_response = ask_gemini_structured(
                            user_prompt=data,
                            response_schema=YouTubeVideoAnalysis,
                            system_prompt=prompt
                        )

                        message = f"<a href='{video_link}'>{youtube_response.translated_title}</a>\n\n<blockquote expandable>{youtube_response.summary}</blockquote>\n\n{hyperlink} | <a href='https://t.me/N17_Media'>N17 TV</a>"

                        message_id = send_image(config, "", thumbnail_url, chat_id=config["Media Chat id"])
                        message_id = send_message(config, message, config["Media Chat id"])
                        time.sleep(3)

                    seen_ids.add(video['id'])

with open(SEEN_VIDEOS_FILE, 'w', encoding='utf-8') as f:
    json.dump({'video_ids': sorted(seen_ids)}, f, indent=2)


with open('seen_feedy.json', 'r', encoding='utf-8') as file:
    done_posts = json.load(file)

TARGET_CHAT_ID = config["Summary Chat id"]

with open("telegram_updates.json", 'r', encoding='utf-8') as file:
    telegram_done = json.load(file)

URL = f"https://api.telegram.org/bot{os.environ.get('BRIDGE_BOT_TOKEN')}/getUpdates"
response = requests.get(URL)


while True:
    data = response.json()
    if response.status_code != 200:
        print(f"API Error ({response.status_code}): {response.text}")
        break
    if not data.get("ok"):
        print(f"Telegram API Error: {data.get('description')}")
        break

    new_updates = data.get("result", [])
    if not new_updates:
        print("No new updates found since your last check.")
        break

    filtered_updates = []
    for update in new_updates:

        message_obj = (
            update.get("message")
            or update.get("edited_message")
        )

        if message_obj and message_obj.get("chat", {}).get("id") == TARGET_CHAT_ID and message_obj.get("from", {}).get("id") == 284403259 and message_obj.get("message_id") not in telegram_done["done"]:
            idx = message_obj.get("text").rfind('https://')
            news_text = message_obj.get("text")[:idx].rstrip()
            news_link = message_obj.get("text")[idx:].replace(f"rss.{RSS_URL}","x.com").replace(RSS_URL,"x.com").strip()
            if len(news_text) == 0 or news_text == "Gif" or str(news_text).startswith("R to @spurssglobal:") or str(news_text).startswith("R to @TheSpursExpress: "):
                telegram_done["done"].append(message_obj.get("message_id"))
            else:
                if len(news_text) < 10:
                    fa = news_text
                elif (str(news_text).startswith("R to ") and len(news_text) < 30) or (str(news_text).startswith("RT by ") and len(news_text) < 30):
                    fa = news_text
                else:
                    fa = ask_gemini(user_prompt=news_text, system_prompt=config["Translation System Prompt"])
                    time.sleep(3)
                message = f"<blockquote expandable>{fa}\n\n<a href='{news_link}'>🇬🇧</a>: {news_text}</blockquote>\n{hyperlink}"
                img_message = f"{fa}\n\n<blockquote expandable><a href='{news_link}'>🇬🇧</a>: {news_text}</blockquote>\n{hyperlink}"
                try:
                    if len(message) > 1024:
                        message_id = send_message(config, message, config["Main Chat id"], preview= True, preview_url=news_link)
                    else:
                        try:
                            message_id = send_image(config, img_message, get_twitter_preview_url(news_link))
                        except:
                            print("sending/fetching the image failed")
                            message_id = send_message(config, message, config["Main Chat id"], preview= True, preview_url=news_link)
                    pin_message(config, message_id)
                    telegram_done["done"].append(message_obj.get("message_id"))
                except Exception as e:
                    a = f"error with this url {news_link}: {e}"
                    print(a)
                    send_message(config, f"{a}", 1140637004)

    break

channel = "https://www.youtube.com/@ChrisCowlin"
posts_json = get_community_posts(channel)

if posts_json:
    # 'posts_json' is now a native Python variable (list or dict)
    print(f"Successfully retrieved {len(posts_json)} posts!")
    for news in reversed(posts_json):
        if news['post_link'] not in done_posts["done"] and "youtu.be" not in news['text']:
            news['text'] = news['text'].replace("#COYS #THFC","")
            url = news['post_link']
            print(url)
            # fa = ask_gemini(user_prompt=news['text'], system_prompt=config["Translation System Prompt"])
            class NEWS(BaseModel):
                persian_news_fulltext: str = Field(description="Full translation of the text based on the system prompt given")
                persian_news_title: str = Field(description="a shot one liner title for the news given the title have to be in persian")
                persian_news_summary: str = Field(description="very short summary of the news that is given. the summary must be in persian. summary must add value to the title")
                similar_title_and_summary: bool = Field(description="if the summary is not needed and is too similar to the title this should be returned as True. if the summary add value to tilte and is descriptive this should be False")
            
            try:
                NEWS_response = ask_gemini_structured(
                    user_prompt=news['text'],
                    response_schema=NEWS,
                    system_prompt=config["Translation System Prompt"]
                )
            except:
                send_message(config, "the structured output failed", 1140637004)
            
            fa = NEWS_response.persian_news_fulltext

            if len(fa) < (len(news['text'])/2):
                continue
            if news['images'] is None:
                limit = 4096
                if len(fa + news['text']) < (limit - 300):
                    message = f"{fa}\n\n<blockquote expandable><a href='{url}'>🇬🇧</a>: {news['text']}</blockquote>\n\n✍️ {news['time_since']} by Chris Cowlin\n\n{hyperlink}"
                elif len(fa) < (limit - 500):
                    message = f"{fa}\n\n<blockquote expandable><a href='{url}'>🇬🇧</a>: {news['text'][:(limit - 300 -len(fa))]}</blockquote>\n\n✍️ {news['time_since']} by Chris Cowlin\n\n{hyperlink}"
                else:
                    message = f"{fa[:(limit - 196)]}\n\n{hyperlink}"
            else:
                limit = 1024
                text_is_too_long_needs_splitting = False
                if len(fa + news['text']) < (limit - 300):
                    message = f"{fa}\n\n<blockquote expandable><a href='{url}'>🇬🇧</a>: {news['text']}</blockquote>\n\n✍️ {news['time_since']} by Chris Cowlin\n\n{hyperlink}"
                elif len(fa) < (limit - 450):
                    message = f"{fa}\n\n<blockquote expandable><a href='{url}'>🇬🇧</a>: {news['text'][:(limit - 300 -len(fa))]}</blockquote>\n\n✍️ {news['time_since']} by Chris Cowlin\n\n{hyperlink}"
                elif len(fa) < (limit - 130):
                    message = f"{fa[:(limit - 130)]}\n\n{hyperlink}"
                else: 
                    text_is_too_long_needs_splitting = True
                    limit = 4096
                    if len(fa + news['text']) < (limit - 300):
                        message = f"{fa}\n\n<blockquote expandable><a href='{url}'>🇬🇧</a>: {news['text']}</blockquote>\n\n✍️ {news['time_since']} by Chris Cowlin\n\n{hyperlink}"
                    elif len(fa) < (limit - 500):
                        message = f"{fa}\n\n<blockquote expandable><a href='{url}'>🇬🇧</a>: {news['text'][:(limit - 300 -len(fa))]}</blockquote>\n\n✍️ {news['time_since']} by Chris Cowlin\n\n{hyperlink}"
                    else:
                        message = f"{fa[:(limit - 196)]}\n\n{hyperlink}"
                
            if news['images'] is None:
                message_id = send_message(config, message, config["Main Chat id"])
            elif len(news['images']) == 1:
                if not text_is_too_long_needs_splitting:
                    message_id = send_image(config, message, news['images'][0])
                else:
                    message_id = send_image(config, hyperlink, news['images'][0])
                    message_id = send_message(config, message, config["Main Chat id"])
            elif len(news['images']) > 1:
                if not text_is_too_long_needs_splitting:
                    message_id = send_gallery(config, message, news['images'])
                else:
                    message_id = send_gallery(config, hyperlink, news['images'])
                    message_id = send_message(config, message, config["Main Chat id"])
            pin_message(config, message_id)

            telegram_done["summary"].append({
                "title": NEWS_response.persian_news_title,
                "summary": NEWS_response.persian_news_summary,
                "is similar": NEWS_response.similar_title_and_summary,
                "post id": f"https://t.me/c/1748646263/{message_id}",
                "image": news['images']
            })

            # delete_message(config, message_id + 1)
            done_posts["done"].append(url)
            time.sleep(15)

    stored_time_str = telegram_done.get("last channel post time")
    last_post_time = datetime.fromisoformat(stored_time_str)
    now = datetime.now(timezone.utc)
    time_passed = now - last_post_time
    print(f"last post:{last_post_time}\ntime passed: {time_passed}\nnews count: {len(telegram_done['summary'])}")

    image_urls = []
    MAX_ALBUM_SIZE = 10

    # Collect per-post image lists (skip posts with no images)
    post_image_lists = []
    for news in telegram_done["summary"]:
        imgs = news.get("image")
        if imgs and len(image_urls) < MAX_ALBUM_SIZE:  # not None and not empty
            post_image_lists.append(imgs)

    # Round-robin: take index 0 from every post, then index 1, then index 2, etc.
    round_idx = 0
    while len(image_urls) < MAX_ALBUM_SIZE:
        added_any = False
        for imgs in post_image_lists:
            if round_idx < len(imgs):
                image_urls.append(imgs[round_idx])
                added_any = True
                if len(image_urls) >= MAX_ALBUM_SIZE:
                    break
        if not added_any:
            break  # no post had an image at this round_idx, we've exhausted everything
        round_idx += 1

    if len(telegram_done["summary"]) > 9:
        print("went on the ton of messages")
        # generated channel post\        
        text = ""
        for post in telegram_done["summary"]:
            post_id = post["post id"]
            post_title = post["title"]
            post_summary = post["summary"]
            try:
                is_similar = post["is similar"]
            except:
                is_similar = False
            if len(post_summary) < 15 or (len(telegram_done["summary"]) > 15 and len(post_summary) > 150) or (len(telegram_done["summary"]) > 15 and len(post_summary) < 50) or (len(post_summary) < (len(post_title)*1.1)) or is_similar:
                text = text + f"<a href='{post_id}'>{post_title}</a>\n\n"
            else:
                text = text + f"<a href='{post_id}'>{post_title}</a>\n<blockquote expandable>{post_summary}</blockquote>\n\n"
        text  = text + "<a href='https://t.me/+QjvW46AcqcAwZjg8'>🔸 برای اخبار فوری و متن کامل مصاحبه ها به گپ ما بپیوندید</a>\n\n" + hyperlink
        print(f"text len: {len(text)}, image_urls: {image_urls}")
        if len(text) < (1024 - 12 + 88*len(telegram_done["summary"]) + 47 + 86 - 40) and len(image_urls) > 0:
            try:
                text = "🗞️ اخبار :\n\n" + text
                message_id = send_gallery(config, text, image_urls, id = config["Channel id"])
            except:
                print("failed to send gallery")
                message_id = send_gallery(config, hyperlink, image_urls, id = config["Media Chat id"])
                text = f"<a href='https://N17_Media/{message_id}'>🗞️</a> اخبار :\n\n" + text
                message_id = send_message(config, text, config["Channel id"], preview= True, preview_url=news_link)
        else: 
            try:
                message_id = send_gallery(config, hyperlink, image_urls, id = config["Media Chat id"])
                text = f"<a href='https://N17_Media/{message_id}'>🗞️</a> اخبار :\n\n" + text
                message_id = send_message(config, text, config["Channel id"], preview= True, preview_url=news_link)
            except:
                print("failed to send to the media channel")
                text = "🗞️ اخبار :\n\n" + text
                message_id = send_message(config, text, config["Channel id"])
        telegram_done["summary done"].extend(telegram_done["summary"])
        telegram_done["summary"] = []
        telegram_done["last channel post time"] = now.isoformat()

    elif time_passed > timedelta(hours=7.5) and (now.time() >= dt_time(19, 30) or now.time() <= dt_time(10, 30)) and len(telegram_done["summary"]) > 3 : 
        print("went on day time post")
        # generated channel post
        text = ""
        for post in telegram_done["summary"]:
            post_id = post["post id"]
            post_title = post["title"]
            post_summary = post["summary"]
            try:
                is_similar = post["is similar"]
            except:
                is_similar = False
            if len(post_summary) < 15 or (len(post_summary) < (len(post_title)*1.1)) or is_similar:
                text = text + f"<a href='{post_id}'>{post_title}</a>\n\n"
            else:
                text = text + f"<a href='{post_id}'>{post_title}</a>\n<blockquote expandable>{post_summary}</blockquote>\n\n"
        print(f"text len: {len(text)}, image_urls: {image_urls}")
        if len(text) < (1024 - 12 + 88*len(telegram_done["summary"]) + 47 + 86 - 40) and len(image_urls) > 0:
            try:
                text = "🗞️ اخبار :\n\n" + text
                message_id = send_gallery(config, text, image_urls, id = config["Channel id"])
            except:
                print("failed to send gallery")
                message_id = send_gallery(config, hyperlink, image_urls, id = config["Media Chat id"])
                text = f"<a href='https://N17_Media/{message_id}'>🗞️</a> اخبار :\n\n" + text
                message_id = send_message(config, text, config["Channel id"], preview= True, preview_url=news_link)
        else: 
            try:
                message_id = send_gallery(config, hyperlink, image_urls, id = config["Media Chat id"])
                text = f"<a href='https://N17_Media/{message_id}'>🗞️</a> اخبار :\n\n" + text
                message_id = send_message(config, text, config["Channel id"], preview= True, preview_url=news_link)
            except:
                print("failed to send to the media channel")
                text = "🗞️ اخبار :\n\n" + text
                message_id = send_message(config, text, config["Channel id"])
        telegram_done["summary done"].extend(telegram_done["summary"])
        telegram_done["summary"] = []
        telegram_done["last channel post time"] = now.isoformat()

    elif now.time() >= dt_time(16, 30) and now.time() <= dt_time(19, 30) and len(telegram_done["summary"]) > 1 and time_passed > timedelta(hours=3):
        print("went on nightly post")
        # generated channel post
        text = ""
        for post in telegram_done["summary"]:
            post_id = post["post id"]
            post_title = post["title"]
            post_summary = post["summary"]
            try:
                is_similar = post["is similar"]
            except:
                is_similar = False
            if len(post_summary) < 15 or (len(post_summary) < (len(post_title)*1.1)) or is_similar:
                text = text + f"<a href='{post_id}'>{post_title}</a>\n\n"
            else:
                text = text + f"<a href='{post_id}'>{post_title}</a>\n<blockquote expandable>{post_summary}</blockquote>\n\n"
        text  = text + "<a href='https://t.me/+QjvW46AcqcAwZjg8'>🔸 برای اخبار فوری و متن کامل مصاحبه ها به گپ ما بپیوندید</a>\n\n" + hyperlink
        print(f"text len: {len(text)}, image_urls: {image_urls}")
        if len(text) < (1024 - 12 + 88*len(telegram_done["summary"]) + 47 + 86 - 40) and len(image_urls) > 0:
            try:
                text = "🗞️ اخبار :\n\n" + text
                message_id = send_gallery(config, text, image_urls, id = config["Channel id"])
            except:
                print("failed to send gallery")
                message_id = send_gallery(config, hyperlink, image_urls, id = config["Media Chat id"])
                text = f"<a href='https://N17_Media/{message_id}'>🗞️</a> اخبار :\n\n" + text
                message_id = send_message(config, text, config["Channel id"], preview= True, preview_url=news_link)
        else: 
            try:
                message_id = send_gallery(config, hyperlink, image_urls, id = config["Media Chat id"])
                text = f"<a href='https://N17_Media/{message_id}'>🗞️</a> اخبار :\n\n" + text
                message_id = send_message(config, text, config["Channel id"], preview= True, preview_url=news_link)
            except:
                print("failed to send to the media channel")
                text = "🗞️ اخبار :\n\n" + text
                message_id = send_message(config, text, config["Channel id"])
        telegram_done["summary done"].extend(telegram_done["summary"])
        telegram_done["summary"] = []
        telegram_done["last channel post time"] = now.isoformat()

    with open('seen_feedy.json', 'w', encoding='utf-8') as file:
        json.dump(done_posts, file)
        print("saving done feedy")
    
    with open('telegram_updates.json', 'w', encoding='utf-8') as file:
        json.dump(telegram_done, file)
        print("saving done telegram")