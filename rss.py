import feedparser
import re
from datetime import datetime, timezone

def extract_id(url):
    last_part = url.split('/')[-1]
    id_part = last_part.split('#')[0]
    return id_part

def get_rss_feed(page):
    feed = feedparser.parse(f"https://xcancel.com/{page}/rss")
    response = []
    if feed.bozo:
        print("There was an error parsing the feed.")
    else:
        for entry in feed.entries:
            img_urls = re.findall(r'<img src="(.*?)"', entry.summary)
            if img_urls:
                response.append([extract_id(entry.link), entry.title, 1, img_urls, datetime.strptime(entry.published, '%a, %d %b %Y %H:%M:%S %Z').replace(tzinfo=timezone.utc)])
            else:
                response.append([extract_id(entry.link), entry.title, 0, [], datetime.strptime(entry.published, '%a, %d %b %Y %H:%M:%S %Z').replace(tzinfo=timezone.utc)])
    return response