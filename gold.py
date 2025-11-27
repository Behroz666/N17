import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime, timedelta, timezone
from translate import article_summarize, translate
from telegram import send_image , send_message
import time

SEEN_FILE = "seen_articles.json"

with open('config.json', 'r', encoding='utf-8') as file:
    config = json.load(file)

if os.path.exists(SEEN_FILE):
    with open(SEEN_FILE, "r") as f:
        seen_articles = set(json.load(f))
else:
    seen_articles = set()

# Function to fetch latest articles from football.london
def get_latest_articles(url: str):
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')

    articles = []
    for a in soup.select("a.headline"):
        title = a.get_text(strip=True)
        link = a["href"]
        if link.startswith("/"):
            link = "https://www.football.london" + link
        articles.append((title, link))
    print(articles)
    return articles

# Function to scrape full article text and date
def scrape_article(url: str):
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')

    # Extract paragraphs
    paragraphs = soup.select("div.article-body p")
    text = " ".join(p.get_text(strip=True) for p in paragraphs)

    # Extract date (football.london uses <time> tag)
    date_tag = soup.find("time")
    pub_date = None
    if date_tag and date_tag.has_attr("datetime"):
        try:
            pub_date = datetime.fromisoformat(date_tag["datetime"].replace("Z", "+00:00"))
        except Exception:
            pass

    banner_url = None
    og_image = soup.find("meta", property="og:image")
    if og_image and og_image.has_attr("content"):
        banner_url = og_image["content"]
    print(text, pub_date, banner_url)
    return text, pub_date, banner_url

if __name__ == "__main__":
    news_url = "https://www.football.london/authors/alasdair-gold/"
    articles = get_latest_articles(news_url)

    one_day_ago = datetime.now(timezone.utc) - timedelta(days=1)
    new_seen = set(seen_articles)

    for title, link in articles:

        if any(char in title for char in ["Tottenham team confirmed vs", "LIVE", "highlights", "player rating"]):
            continue

        if link in seen_articles:
            continue  # Skip duplicates

        article_text, pub_date, banner_url = scrape_article(link)
        if not article_text or not pub_date:
            continue
        print(pub_date)
        if pub_date < one_day_ago:
            continue  # Skip if older than 1 day
        print(title)
        try:
            fa_title = translate(config, title, "0", additional = "")
        except:
            fa_title = translate(config, title, "1", additional = "") + "`"
        print(title + "\n\n turns into" + fa_title)

        if len(fa_title) < 2 * len(title):
            title = fa_title

        text = f"<a href='{link}'>{title}</a>\n\n"
        time.sleep(5)

        print(f"\n--- {title} ({pub_date}) ---")
        if banner_url:
            print(f"Banner Image: {banner_url}")
        summary = article_summarize(config, article_text, fa_title)
        print(summary)
        text = text + f"<blockquote expandable>{summary.replace('قدوس','کودوس').replace('خاوی','ژاوی')}</blockquote>\n\n✍️ By Alasdair Gold at {(pub_date + timedelta(hours=3, minutes=30)).strftime('%Y.%m.%d %I:%M %p')}\n\n🔹 <a href='https://t.me/N17_Tottenham'>N17 Tottenham</a> | <a href='https://t.me/+2TG8ZxphObwzN2Q0'>VivaSpurs</a>"
        try:
            if len(summary + title) < 940 :
                send_image(config, text, banner_url)
            else:
                send_image(config, "", banner_url)
                send_message(config, text, config["Main Chat id"])
        except:
            send_message(config, text, config["Main Chat id"])
        time.sleep(5)
        new_seen.add(link)

    # Save updated seen URLs
    with open(SEEN_FILE, "w") as f:
        json.dump(list(new_seen), f)
