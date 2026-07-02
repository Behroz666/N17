import subprocess
import json
import os
import tempfile
from telegram import send_image, send_message, send_gallery, pin_message, delete_message
import time
from gemini import ask_gemini, ask_gemini_structured
from pydantic import BaseModel, Field
import requests
from datetime import datetime, timedelta, timezone
import sys

hyperlink = "🔹 <a href='https://t.me/N17_Tottenham'>N17 Tottenham</a> | <a href='https://t.me/+2TG8ZxphObwzN2Q0'>VivaSpurs</a>"

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

with open('seen_feedy.json', 'r', encoding='utf-8') as file:
    done_posts = json.load(file)

TARGET_CHAT_ID = config["Summary Chat id"]

with open("telegram_updates.json", 'r', encoding='utf-8') as file:
    telegram_done = json.load(file)

URL = f"https://api.telegram.org/bot{os.environ.get('BRIDGE_BOT_TOKEN')}/getUpdates"
response = requests.get(URL)

class ErrorInterceptor:
    def __init__(self, original_stderr):
        self.original_stderr = original_stderr

    def write(self, message):
        # Always write to the original stderr so you don't lose normal console output
        self.original_stderr.write(message)
        
        # If the message isn't empty/just whitespace, send it
        if message.strip():
            send_message(config, f"error in mainy.py:\n\n{message}", 1140637004)

    def flush(self):
        self.original_stderr.flush()

# Redirect standard error to our interceptor
sys.stderr = ErrorInterceptor(sys.stderr)

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
            news_text = message_obj.get("text")[:-68]
            news_link = message_obj.get("text")[-68:].replace("rss.xcancel.com","x.com")
            send_message(config, f"news text: {news_text}, news link: {news_link}", 1140637004)
            telegram_done["done"].append(message_obj.get("message_id"))

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
                persian_news_summary: str = Field(description="very short summary of the news given the summary must be in persian")
            
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
                "post id": f"https://t.me/c/1748646263/{message_id}"
            })

            stored_time_str = telegram_done.get("last channel post time")
            last_post_time = datetime.fromisoformat(stored_time_str)
            now = datetime.now(timezone.utc)

            if len(telegram_done["summary"]) > 9:
                # generated channel post
                text = "🗞️اخبار :\n\n"
                for post in telegram_done["summary"]:
                    post_id = post["post id"]
                    post_title = post["title"]
                    post_summary = post["summary"]
                    text = text + f"<a href='{post_id}'>{post_title}</a>\n<blockquote expandable>{post_summary}</blockquote>\n\n"
                text  = text + "<a href='https://t.me/+QjvW46AcqcAwZjg8'>🔸برای اخبار فوری و متن کامل مصاحبه ها به گپ ما بپیوندید</a>\n\n" + hyperlink
                message_id = send_message(config, text, config["Channel id"])
                telegram_done["done summary"] = telegram_done["done summary"].extend(telegram_done["summary"])
                telegram_done["summary"] = []
                telegram_done["last channel post time"] = now.isoformat()
            elif now - last_post_time > timedelta(hours=6) and (last_post_time.time() >= time(18, 30) or last_post_time.time() <= time(10, 30)) and len(telegram_done["summary"]) > 2 : 
                # generated channel post
                text = "🗞️اخبار :\n\n"
                for post in telegram_done["summary"]:
                    post_id = post["post id"]
                    post_title = post["title"]
                    post_summary = post["summary"]
                    text = text + f"<a href='{post_id}'>{post_title}</a>\n<blockquote expandable>{post_summary}</blockquote>\n\n"
                text  = text + "<a href='https://t.me/+QjvW46AcqcAwZjg8'>🔸برای اخبار فوری و متن کامل مصاحبه ها به گپ ما بپیوندید</a>\n\n" + hyperlink
                message_id = send_message(config, text, config["Channel id"])
                telegram_done["done summary"] = telegram_done["done summary"].extend(telegram_done["summary"])
                telegram_done["summary"] = []
                telegram_done["last channel post time"] = now.isoformat()

            # delete_message(config, message_id + 1)
            done_posts["done"].append(url)
            time.sleep(15)

    with open('seen_feedy.json', 'w', encoding='utf-8') as file:
        json.dump(done_posts, file)
        print("saving done feedy")
    
    with open('telegram_updates.json', 'w', encoding='utf-8') as file:
        json.dump(telegram_done, file)
        print("saving done telegram")