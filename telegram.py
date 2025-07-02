import requests

def send_message(config, text):
    url = f"https://api.telegram.org/bot{config["Bot Token"]}/sendMessage"
    payload = {
        "chat_id": config["Chat id"],
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview":True
    }
    requests.post(url, data=payload)

def send_image(config, text, link):
    url = f"https://api.telegram.org/bot{config["Bot Token"]}/sendPhoto"
    payload = {
        "chat_id": config["Chat id"],
        'photo': link,
        "caption": text,
        "parse_mode": "HTML"
    }
    requests.post(url, data=payload)

def send_gallery(config, text, links):
    url = f"https://api.telegram.org/bot{config["Bot Token"]}/sendMediaGroup"
    
    media = []
    for i, link in enumerate(links):
        media_item = {
            "type": "photo",
            "media": link
        }
        if i == 0:
            media_item["caption"] = text
            media_item["parse_mode"] = "HTML"
        media.append(media_item)
    
    payload = {
        "chat_id": config["Chat id"],
        "media": media 
    }
    requests.post(url, json=payload)