import feedparser
import re

def get_rss_feed(config):
    feed = feedparser.parse(config["RSS"])
    response = []
    if feed.bozo:
        print("There was an error parsing the feed.")
    else:
        for entry in feed.entries:
            img_urls = re.findall(r'<img src="(.*?)"', entry.summary)
            if img_urls:
                response.append([entry.link, entry.title, img_urls[0]])
            else:
                response.append([entry.link, entry.title, 0])
    return response