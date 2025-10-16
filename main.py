import json
import time
from rss import get_rss_feed
from translate import translate, is_new
from telegram import send_image, send_message, send_gallery, pin_message, delete_message
import yt_dlp
import os
import requests
import unicodedata

hyperlink = "🔹 <a href='https://t.me/N17_Tottenham'>N17 Tottenham</a> | <a href='https://t.me/+2TG8ZxphObwzN2Q0'>VivaSpurs</a>"

def download_twitter_video(url, output_path):
    # First try 360p
    ydl_opts_360p = {
        'format': 'best[height<=360]',
        'outtmpl': output_path,
    }

    with yt_dlp.YoutubeDL(ydl_opts_360p) as ydl:
        info_dict = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info_dict)

    # Check file size (in MB)
    file_size_mb = os.path.getsize(filename) / (1024 * 1024)

    if file_size_mb > 10:
        # Delete the large file and fallback to worst
        os.remove(filename)

        ydl_opts_worst = {
            'format': 'worst',
            'outtmpl': output_path,
        }

        with yt_dlp.YoutubeDL(ydl_opts_worst) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info_dict)
    return filename

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

if __name__ == "__main__":

    with open('config.json', 'r', encoding='utf-8') as file:
        config = json.load(file)

    with open('new_tweet_ids.json', 'r', encoding='utf-8') as file:
        tweet_ids = json.load(file)

    with open('tweet_ids.json', 'r', encoding='utf-8') as file:
        secondary_tweet_ids = json.load(file)

    tweets = get_rss_feed(config["page"][0])
    for tweet in reversed(tweets):
        if tweet[0] not in tweet_ids["done"]:
            try:
                print(tweet[1])

                if len(tweet[1]) == 0 or tweet[1] == "Gif" or str(tweet[1]).startswith("R to @spurssglobal: football.london/tottenham-ho…"):
                    tweet_ids["done"].append(tweet[0])
                    continue
                else:
                    if len(tweet[1]) < 10:
                        fa = tweet[1]
                    elif str(tweet[1]).startswith("R to ") and len(tweet[1]) < 30:
                        fa = tweet[1]
                    else:
                        try:
                            fa = translate(config, normalize_stylized(tweet[1]), additional = "")
                        except:
                            time.sleep(40)
                            fa = translate(config, normalize_stylized(tweet[1]), additional = "")

                if len(fa) < (len(tweet[1])/2):
                    continue

                fa = fa.replace("#","").replace("قدوس","کودوس").replace("خاوی","ژاوی")
                url = f"https://x.com/{config["page"][0]}/status/{tweet[0]}#m"
                if tweet[2] == 0:
                    limit = 4096
                    if len(fa + tweet[1]) < (limit - 256):
                        message = f"{fa}\n\n<blockquote expandable><a href='{url}'>🇬🇧</a>: {tweet[1]}</blockquote>\n\n{hyperlink}"
                    elif len(fa) < (limit - 456):
                        message = f"{fa}\n\n<blockquote expandable><a href='{url}'>🇬🇧</a>: {tweet[1][:(limit - 256 -len(fa))]}</blockquote>\n\n{hyperlink}"
                    else:
                        message = f"{fa[:(limit - 196)]}\n\n{hyperlink}"
                else:
                    limit = 1024
                    if len(fa + tweet[1]) < (limit - 256):
                        message = f"{fa}\n\n<blockquote expandable><a href='{url}'>🇬🇧</a>: {tweet[1]}</blockquote>\n\n{hyperlink}"
                    elif len(fa) < (limit - 456):
                        message = f"{fa}\n\n<blockquote expandable><a href='{url}'>🇬🇧</a>: {tweet[1][:(limit - 256 -len(fa))]}</blockquote>\n\n{hyperlink}"
                    else:
                        message = f"{fa[:(limit - 196)]}\n\n{hyperlink}"

                print(message)
                if tweet[2] == 0:
                    message_id = send_message(config, message, config["Main Chat id"])
                else:
                    if len(tweet[3]) == 1:
                        print(tweet[3][0])
                        if "video_thumb" not in tweet[3][0]:
                            message_id = send_image(config, message, tweet[3][0])
                        else:
                            try:
                                file_name = download_twitter_video(url, tweet[0])
                                print("incode" + file_name)
                                with open(file_name, 'rb') as f:
                                    response = requests.post(
                                        f"https://api.telegram.org/bot{os.environ.get('BOT_TOKEN')}/sendVideo",
                                        files={'video': f},
                                        data={'chat_id': config["Main Chat id"],
                                            'caption': message,
                                            "parse_mode": "HTML"}
                                    )
                                os.remove(file_name)
                                response_json = response.json()
                                message_id = response_json['result']['message_id']
                            except Exception as e:
                                print(e)
                                send_message(config, f"{e}", 1140637004)
                                if "HTTP Error 403" in e :
                                    tweet_ids["done"].append(tweet[0])
                                message_id = send_image(config, message, tweet[3][0])
                            except:
                                message_id = send_image(config, message, tweet[3][0])
                    else:
                        message_id = send_gallery(config, message, tweet[3])
                pin_message(config, message_id)
                delete_message(config, message_id + 1)
                tweet_ids["done"].append(tweet[0])
                time.sleep(15)
            except:
                if tweet[0] in tweet_ids["done"]:
                    tweet_ids["done"].remove(tweet[0])
                continue
    history = []
    for tweet in tweets:
        if tweet[0] in tweet_ids["done"][-10:]:
            history.append(tweet[1])
    print(history)
    tweets = get_rss_feed(config["page"][1])
    for tweet in reversed(tweets):
        if tweet[0] not in secondary_tweet_ids["done"]:
            try:
                print(tweet[1])

                if len(tweet[1]) == 0 or tweet[1] == "Gif":
                    secondary_tweet_ids["done"].append(tweet[0])
                    continue
                if is_new(config, tweet[1], history):
                    if len(tweet[1]) < 10:
                        fa = tweet[1]
                    elif str(tweet[1]).startswith("R to ") and len(tweet[1]) < 30:
                        fa = tweet[1]
                    else:
                        try:
                            fa = translate(config, tweet[1], additional = "")
                        except:
                            time.sleep(40)
                            fa = translate(config, tweet[1], additional = "")

                    if len(fa) < (len(tweet[1])/2):
                        continue

                    fa = fa.replace("#","").replace("قدوس","کودوس").replace("خاوی","ژاوی")
                    url = f"https://x.com/{config["page"][1]}/status/{tweet[0]}#m"
                    if tweet[2] == 0:
                        limit = 4096
                        if len(fa + tweet[1]) < (limit - 256):
                            message = f"{fa}\n\n<blockquote expandable><a href='{url}'>🇬🇧</a>: {tweet[1]}</blockquote>\n\n{hyperlink}"
                        elif len(fa) < (limit - 456):
                            message = f"{fa}\n\n<blockquote expandable><a href='{url}'>🇬🇧</a>: {tweet[1][:(limit - 256 -len(fa))]}</blockquote>\n\n{hyperlink}"
                        else:
                            message = f"{fa[:(limit - 196)]}\n\n{hyperlink}"
                    else:
                        limit = 1024
                        if len(fa + tweet[1]) < (limit - 256):
                            message = f"{fa}\n\n<blockquote expandable><a href='{url}'>🇬🇧</a>: {tweet[1]}</blockquote>\n\n{hyperlink}"
                        elif len(fa) < (limit - 456):
                            message = f"{fa}\n\n<blockquote expandable><a href='{url}'>🇬🇧</a>: {tweet[1][:(limit - 256 -len(fa))]}</blockquote>\n\n{hyperlink}"
                        else:
                            message = f"{fa[:(limit - 196)]}\n\n{hyperlink}"

                    print(message)
                    if tweet[2] == 0:
                        message_id = send_message(config, message, config["Main Chat id"])
                    else:
                        if len(tweet[3]) == 1:
                            if "video_thumb" not in tweet[3][0]:
                                message_id = send_image(config, message, tweet[3][0])
                            else:
                                try:
                                    file_name = download_twitter_video(url, tweet[0])
                                    with open(file_name, 'rb') as f:
                                        response = requests.post(
                                            f"https://api.telegram.org/bot{os.environ.get('BOT_TOKEN')}/sendVideo",
                                            files={'video': f},
                                            data={'chat_id': config["Main Chat id"],
                                                'caption': message,
                                                "parse_mode": "HTML"}
                                        )
                                    os.remove(file_name)
                                    response_json = response.json()
                                    message_id = response_json['result']['message_id']
                                except:
                                    message_id = send_image(config, message, tweet[3][0])
                        else:
                            message_id = send_gallery(config, message, tweet[3])
                    pin_message(config, message_id)
                    delete_message(config, message_id + 1)
                    secondary_tweet_ids["done"].append(tweet[0])
                    time.sleep(15)
                else:
                    secondary_tweet_ids["done"].append(tweet[0])
                    time.sleep(15)
            except:
                if tweet[0] in tweet_ids["done"]:
                    tweet_ids["done"].remove(tweet[0])
                continue
    
    with open('new_tweet_ids.json', 'w', encoding='utf-8') as file:
        json.dump(tweet_ids, file)
        print("saving done")

    with open('tweet_ids.json', 'w', encoding='utf-8') as file:
        json.dump(secondary_tweet_ids, file)
        print("secondary saving done")
