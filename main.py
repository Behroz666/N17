import json
import time
from rss import get_rss_feed
from translate import translate
from telegram import send_image, send_message

if __name__ == "__main__":

    with open('config.json', 'r', encoding='utf-8') as file:
        config = json.load(file)

    with open('tweet_ids.json', 'r', encoding='utf-8') as file:
        tweet_ids = json.load(file)

    tweets = get_rss_feed(config)
    for tweet in tweets:
        if tweet[0][20:] not in tweet_ids["done"][20:]:
            try:
                print(tweet[1])
                try:
                    fa = translate(config, tweet[1])
                except:
                    time.sleep(60)
                    fa = translate(config, tweet[1])
                link = tweet[0].replace("rss.","").replace("xcancel", "x")
                message = f"{fa}\n\n<blockquote expandable><a href='{link}'>🇬🇧</a>: {tweet[1]}</blockquote>\n\n<a href='{"https://t.me/+2TG8ZxphObwzN2Q0"}'>VivaSpurs</a> | <a href='{"https://t.me/N17_Tottenham"}'>N17 Tottenham</a>"
                if tweet[2] == 0:
                    send_message(config, message)
                else:
                    send_image(config, message, tweet[2])
                tweet_ids["done"].append(tweet[0])
                time.sleep(45)
            except:
                if tweet[0] in tweet_ids["done"]:
                    tweet_ids["done"].remove(tweet[0])
                time.sleep(60)
                continue
    
    with open('tweet_ids.json', 'w', encoding='utf-8') as file:
        json.dump(tweet_ids, file)
