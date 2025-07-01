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
        if tweet[0] not in tweet_ids["done"]:
            print(tweet[1])
            fa = translate(config, tweet[1])
            message = f"🇬🇧:\n\n<blockquote expandable>{tweet[1]}</blockquote>\n\n🇮🇷:\n\n{fa}\n\n🔗:\n{tweet[0].replace("rss.xcancel", "x")}"
            if tweet[2] == 0:
                send_message(config, message)
            else:
                send_image(config, message, tweet[2])
            tweet_ids["done"].append(tweet[0])
            time.sleep(2)
    
    with open('tweet_ids.json', 'w', encoding='utf-8') as file:
        json.dump(tweet_ids, file)
