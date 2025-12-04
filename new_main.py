from feed import extract_posts_from_html
import os
import json
import requests
from telegram import send_image, send_message, pin_message, delete_message
from translate import translate
import unicodedata
import time

hyperlink = "🔹 <a href='https://t.me/N17_Tottenham'>N17 Tottenham</a> | <a href='https://t.me/+2TG8ZxphObwzN2Q0'>VivaSpurs</a>"

def normalize_stylized(text: str) -> str:
    normalized = []
    for char in text:
        try:
            name = unicodedata.name(char)
        except ValueError:
            # Character might not have a name (e.g., emoji), keep as-is
            normalized.append(char)
            continue

        # Handle stylized letters/numbers
        if "MATHEMATICAL" in name:
            # Extract the base letter/number from the name
            parts = name.split()
            base = parts[-1]
            normalized.append(base)
        else:
            normalized.append(char)

    return "".join(normalized)

RSS_URL = os.environ.get('RSS_URL')
FEED_URL = os.environ.get('FEED_URL')

if __name__ == "__main__":

    print(f"Fetching content from the feed")

    try:
        # A User-Agent header is often required to avoid being blocked by servers
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(FEED_URL, headers=headers)
        response.raise_for_status()  # Raises an HTTPError for bad responses (4xx, 5xx)
        
        html_data = response.text
        data = extract_posts_from_html(html_data)
    except requests.exceptions.RequestException as e:
        print(f"Error fetching the URL: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")


    with open('config.json', 'r', encoding='utf-8') as file:
        config = json.load(file)
    with open('seen_feed.json', 'r', encoding='utf-8') as file:
        seen_feed_json = json.load(file)
        seen_feed = seen_feed_json["done"]

    for feed in data:
        try:
            if feed["post_url"].replace(str("rss." + str(RSS_URL)), str(RSS_URL)) in seen_feed or feed["post_url"].replace(str(RSS_URL), str("rss." + str(RSS_URL))) in seen_feed:
                seen_feed.append(feed["post_url"])
                continue
            if feed["post_url"] not in seen_feed:

                if len(feed["text"]) == 0 or feed["text"] == "Gif" or str(feed["text"]).startswith("R to @spurssglobal: football.london/tottenham-ho…") or "LIVE" in str(feed["text"]):
                    seen_feed.append(feed["post_url"])
                    continue
                else:
                    if len(feed["text"]) < 10:
                        fa = feed["text"]
                    elif str(feed["text"]).startswith("R to ") and len(feed["text"]) < 30:
                        fa = feed["text"]
                    else:
                        try:
                            fa = translate(config, normalize_stylized(feed["text"]), "1", additional = "")
                        except:
                            try:
                                fa = translate(config, normalize_stylized(feed["text"]), "1", additional = "")
                            except:
                                fa = translate(config, normalize_stylized(feed["text"]), "0", additional = "")


                if len(fa) < (len(feed["text"])/2):
                    continue

                fa = fa.replace("#","").replace('قدوس','کودوس').replace('خاوی','ژاوی').replace("*", "").replace("`","")

                unwanted_chars = (':', '.', ' ', "\n")
                if fa.startswith(unwanted_chars):
                    fa = fa[1:]

                if str("rss." + str(RSS_URL)) in feed["post_url"]:
                    feed["post_url"] = feed["post_url"].replace(str("rss." + str(RSS_URL)), "x.com")
                if str(RSS_URL) in feed["post_url"]:
                    feed["post_url"] = feed["post_url"].replace(str(RSS_URL), "x.com")

                if feed["image_url"] is None:
                    limit = 4096
                    if len(fa + feed["text"]) < (limit - 256):
                        message = f"{fa}\n\n<blockquote expandable><a href='{feed["post_url"]}'>🇬🇧</a>: {feed["text"]}</blockquote>\n\n{hyperlink}"
                    elif len(fa) < (limit - 456):
                        message = f"{fa}\n\n<blockquote expandable><a href='{feed["post_url"]}'>🇬🇧</a>: {feed["text"][:(limit - 256 -len(fa))]}</blockquote>\n\n{hyperlink}"
                    else:
                        message = f"{fa[:(limit - 196)]}\n\n{hyperlink}"
                else:
                    limit = 1024
                    if len(fa + feed["text"]) < (limit - 256):
                        message = f"{fa}\n\n<blockquote expandable><a href='{feed["post_url"]}'>🇬🇧</a>: {feed["text"]}</blockquote>\n\n{hyperlink}"
                    elif len(fa) < (limit - 456):
                        message = f"{fa}\n\n<blockquote expandable><a href='{feed["post_url"]}'>🇬🇧</a>: {feed["text"][:(limit - 256 -len(fa))]}</blockquote>\n\n{hyperlink}"
                    else:
                        message = f"{fa[:(limit - 196)]}\n\n{hyperlink}"

                print(message)
                if feed["image_url"] is None:
                    message_id = send_message(config, message, config["Main Chat id"])
                else:
                    message_id = send_image(config, message, feed["image_url"])
                pin_message(config, message_id)
                delete_message(config, message_id + 1)
                seen_feed.append(feed["post_url"])
                time.sleep(15)
        except:
            continue
    
    seen_feed_json["done"] = seen_feed
    with open('seen_feed.json', 'w', encoding='utf-8') as file:
        json.dump(seen_feed_json, file)
        print("saving done")