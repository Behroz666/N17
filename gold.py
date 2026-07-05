import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime, timedelta, timezone
from gemini import ask_gemini, ask_gemini_structured
from telegram import send_image , send_message
import time
import json
from zoneinfo import ZoneInfo
import humanize
from pydantic import BaseModel, Field

SEEN_FILE = "seen_articles.json"
hyperlink = "🔹 <a href='https://t.me/N17_Tottenham'>N17 Tottenham</a> | <a href='https://t.me/+2TG8ZxphObwzN2Q0'>VivaSpurs</a>"

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
    ld_json = soup.find("script", type="application/ld+json")
    data = json.loads(ld_json.string)

    # Extract paragraphs
    text = data.get("articleBody")

    # Extract date
    pub_date = None
    date_str = data.get("datePublished")
    if date_str:
        pub_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))

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
            new_seen.add(link)
            continue

        if link in seen_articles:
            continue  # Skip duplicates

        article_text, pub_date, banner_url = scrape_article(link)
        if not article_text or not pub_date:
            continue
        print(pub_date)
        if pub_date < one_day_ago:
            new_seen.add(link)
            continue  # Skip if older than 1 day
        class ArticleProcessor(BaseModel):
            fa_title: str = Field(description="ترجمه دقیق و رسمی عنوان بدون هیچ کلمه اضافی")
            summary: str = Field(description="خلاصه ۲۰۰۰ کاراکتری جذاب از متن مقاله با در نظر داشتن عنوان")
        
        system_prompt = config["Translation System Prompt"] + config["Acticle System Prompt"] + f"تو باید این عنوان را هم در نظر داشته باشی {title} و به سوال و موضوع اصلی مطرح شده در این عنوان بپردازی اگر نوشته جالب دیگری هم در متن وجود داشت و میتوانستی با در نظر گرفتن محدودیت طول متن خروجی آن را هم ذکر کنی آن را انجام بده. پس تو باید یک پاراگراف حذاب و خلاصه از متن داده شده با در نظر داشتن عنوان ارائه بدی"
        user_prompt = f"""
        [TITLE]
        {title}

        [ARTICLE_TEXT]
        {article_text}
        """

        try:
            result = ask_gemini_structured(
                user_prompt=user_prompt,
                response_schema=ArticleProcessor,
                system_prompt=system_prompt
            )
            fa_title = result.fa_title
            summary = result.summary

            if len(fa_title) < 2 * len(title) and "ترجمه" not in fa_title:
                title = fa_title
            pub_date_aware = pub_date.replace(tzinfo=ZoneInfo("Europe/London"))
            now_utc = datetime.now(timezone.utc)
            relative_time = humanize.naturaltime(now_utc - pub_date_aware)
            text = f"<a href='{link}'>{title}</a>\n\n<blockquote expandable>{summary.replace('قدوس','کودوس').replace('خاوی','ژاوی')}</blockquote>\n\n✍️ {relative_time} by Alasdair Gold \n\n{hyperlink}"
            try:
                if len(summary + title) < 940 :
                    send_image(config, text, banner_url)
                else:
                    send_image(config, "", banner_url)
                    send_message(config, text, config["Main Chat id"])
            except:
                send_message(config, text, config["Main Chat id"])
        except:
            text = f"<a href='{link}'>{title}</a>\n\n{hyperlink}"
            try:
                send_image(config, text, banner_url)
            except:
                send_message(config, text, config["Main Chat id"])    

        time.sleep(5)
        new_seen.add(link)

    # Save updated seen URLs
    with open(SEEN_FILE, "w") as f:
        json.dump(list(new_seen), f)
