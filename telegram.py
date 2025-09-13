import requests
import os

BOT_TOKEN = os.environ.get('BOT_TOKEN')

def send_message(config, text, chat_id):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview":True
    }
    response = requests.post(url, data=payload)
    response_json = response.json()
    return response_json['result']['message_id']

def send_image(config, text, link):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    payload = {
        "chat_id": config["Main Chat id"],
        'photo': link,
        "caption": text,
        "parse_mode": "HTML"
    }
    response = requests.post(url, data=payload)
    response_json = response.json()
    print(response_json)
    return response_json['result']['message_id']

def send_gallery(config, text, links):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMediaGroup"
    
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
        "chat_id": config["Main Chat id"],
        "media": media 
    }
    response = requests.post(url, json=payload)
    response_json = response.json()
    print(response_json['result'][1]['message_id'])
    return int(response_json['result'][1]['message_id']) + len(links) - 2

def pin_message(config, message_id):
    print(message_id)
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/pinChatMessage"
    payload = {
        "chat_id": config["Main Chat id"],
        'message_id': message_id,
        "disable_notification": True
    }
    print(requests.post(url, data=payload))

def delete_message(config, message_id):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage"
    payload = {
        "chat_id": config["Main Chat id"],
        "message_id": message_id
    }
    response = requests.post(url, data=payload)
    return response.json()
