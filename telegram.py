import requests

def send_message(config, text):
    url = f"https://api.telegram.org/bot{config["Bot Token"]}/sendMessage"
    payload = {
        "chat_id": config["Chat id"],
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview":True
    }
    response = requests.post(url, data=payload)
    return response.json()

def send_image(config, text, link):
    url = f"https://api.telegram.org/bot{config["Bot Token"]}/sendPhoto"
    payload = {
        "chat_id": config["Chat id"],
        'photo': link,
        "caption": text,
        "parse_mode": "HTML"
    }
    response = requests.post(url, data=payload)
    return response.json()

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
    response = requests.post(url, json=payload)
    return response.json()

def pin_message(config, message_id):
    url = f"https://api.telegram.org/bot{config["Bot Token"]}/pinChatMessage"
    payload = {
        "chat_id": config["Chat id"],
        'message_id': message_id,
        "disable_notification": True
    }
    response = requests.post(url, data=payload)
    return response.json()
