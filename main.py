import json
import time
from rss import get_rss_feed
from translate import translate
from telegram import send_image, send_message, send_gallery, pin_message, delete_message

if __name__ == "__main__":

    with open('config.json', 'r', encoding='utf-8') as file:
        config = json.load(file)

    with open('tweet_ids.json', 'r', encoding='utf-8') as file:
        tweet_ids = json.load(file)

    tweets = get_rss_feed(config["page"])
    for tweet in tweets:
        if tweet[0] not in tweet_ids["done"]:
            try:
                print(tweet[1])
                try:
                    fa = translate(config, tweet[1])
                except:
                    time.sleep(60)
                    fa = translate(config, tweet[1])
                message = f"{fa.replace("#","")}\n\n<blockquote expandable><a href='https://x.com/{config["page"]}/status/{tweet[0]}#m'>🇬🇧</a>: {tweet[1]}</blockquote>\n\n<a href='{"https://t.me/+2TG8ZxphObwzN2Q0"}'>VivaSpurs</a> | <a href='{"https://t.me/N17_Tottenham"}'>N17 Tottenham</a>"
                print(message)
                if tweet[2] == 0:
                    response_json = send_message(config, message, config["Main Chat id"])
                else:
                    if len(tweet[3]) == 1:
                        response_json = send_image(config, message, tweet[3][0])
                    else:
                        response_json = send_gallery(config, message, tweet[3])
                print(response_json)
                message_id = response_json['result']['message_id']
                pin_message(config, message_id)
                delete_message(config, message_id + 1)
                tweet_ids["done"].append(tweet[0])
                time.sleep(45)
            except:
                if tweet[0] in tweet_ids["done"]:
                    tweet_ids["done"].remove(tweet[0])
                continue
    
    with open('tweet_ids.json', 'w', encoding='utf-8') as file:
        json.dump(tweet_ids, file)
        print("saving done")
