import json
import time
from rss import get_rss_feed
from datetime import datetime, timedelta, timezone
from translate import summarize
from telegram import send_message

if __name__ == "__main__":

    with open('config.json', 'r', encoding='utf-8') as file:
        config = json.load(file)

    last_day_news = []

    for page in config["pages"]:
        print(page)
        tweets = get_rss_feed(page)
        for tweet in tweets:
            now_local = datetime.now().astimezone()
            one_day_ago_utc = now_local.astimezone(timezone.utc) - timedelta(days=1)
            if tweet[4] > one_day_ago_utc and all(x not in tweet[1] for x in ["🎙️", "🗣️"]):
                last_day_news.append(tweet[1])
        time.sleep(30)
    print(last_day_news)
    text = summarize(config, last_day_news)
    text = text.replace("**", "").replace("*   ", "")
    final = ""
    parts = text.split("\n\n")
    for part in parts:
        emoji = part[:1]
        body = part.replace(emoji, "")
        result = body.split(":", 1)[1].strip()
        final = final + emoji + " " + result + "\n\n"
    message = "خلاصه اخبار امروز:\n\n" + final + "<a href='https://t.me/+QjvW46AcqcAwZjg8'>برای اخبار فوری و متن کامل مصاحبه ها به گپ ما بپیوندید</a>" + "\n\n@N17_Tottenham"
    send_message(config, message, config["Summary Chat id"])

    for admin in config["admins"]:
        send_message(config, message, admin)

