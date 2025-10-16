import json
import time
from rss import get_rss_feed
from datetime import datetime, timedelta, timezone
from translate import summarize
from telegram import send_message
import re

if __name__ == "__main__":

    with open('config.json', 'r', encoding='utf-8') as file:
        config = json.load(file)

    last_day_news = []
    last_hours_news = []
    news = []

    for page in config["pages"]:
        print(page)
        tweets = get_rss_feed(page)
        for tweet in tweets:
            now_local = datetime.now().astimezone()
            one_day_ago_utc = now_local.astimezone(timezone.utc) - timedelta(days=1)
            three_hours_ago_uts = now_local.astimezone(timezone.utc) - timedelta(hours=3)
            if tweet[4] > one_day_ago_utc and all(x not in tweet[1] for x in ["🎙️", "🗣️"]):
                last_day_news.append(tweet[1])
            if tweet[4] > three_hours_ago_uts and all(x not in tweet[1] for x in ["🎙️", "🗣️"]):
                last_hours_news.append(tweet[1])
        time.sleep(10)
    print(last_day_news)
    news.append(summarize(config, last_day_news))
    # quick news for transfer window
    # time.sleep(20)
    # news.append(summarize(config, last_hours_news))
    for text in news:
        text = text.replace("**", "").replace("*   ", "")
        # pattern = re.compile(r"([\u2600-\u27BF\u1F300-\u1FAFF]\uFE0F?)\s*[^:\n]+:\s*")
        # final = pattern.sub(r"\1 ", text)
        if text.count(":") > 1:
            final = ""
            parts = text.split("\n\n")
            for part in parts:
                pattern = r"^(\S)\s*.+?:\s*"
                result = re.sub(pattern, r"\1 ", part)
                final = final + result + "\n\n"
        else: 
            final = text
        message = "خلاصه اخبار امروز:\n\n" + final.replace('قدوس','کودوس').replace('خاوی','ژاوی') + "\n<a href='https://t.me/+QjvW46AcqcAwZjg8'>برای اخبار فوری و متن کامل مصاحبه ها به گپ ما بپیوندید</a>" + "\n\n@N17_Tottenham"
        send_message(config, message, config["Summary Chat id"])

        for admin in config["admins"]:
            send_message(config, message, admin)

