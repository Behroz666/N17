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
        tweets = get_rss_feed(page)
        for tweet in tweets:
            now_local = datetime.now().astimezone()
            one_day_ago_utc = now_local.astimezone(timezone.utc) - timedelta(days=1)
            if tweet[4] > one_day_ago_utc:
                last_day_news.append(tweet[1])
        time.sleep(30)
    print(last_day_news)
    text = summarize(config, last_day_news)
    message = "خلاصه اخبار امروز:\n\n" + text + "\n\n@N17_Tottenham"
    send_message(config, message, config["Summary Chat id"])

