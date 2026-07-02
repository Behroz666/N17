import requests
import os
import time

BOT_TOKEN = os.environ.get('BOT_TOKEN')
max_attempts = 2

def send_message(config, text, chat_id, preview):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    if not preview:
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview":True
        }
    else:
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
    attempts = 0
    while attempts < max_attempts: 
        response = requests.post(url, data=payload)
        response_json = response.json()
        print(response_json)
        if response_json.get('ok') == True:
            return response_json['result']['message_id']
        else:
            attempts += 1
            error_code = response_json.get('error_code')
            if error_code == 429:
                retry_after = response_json.get('parameters', {}).get('retry_after', 5)
                print(f"send message: Rate limit exceeded (429). Retrying after {retry_after} seconds...")
                time.sleep(retry_after + 1)
            else:
                raise Exception(f"Telegram API Error: {response_json.get('description', 'Unknown Error')}")

def send_image(config, text, link):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"

    try:
        # Get the image content (bytes)
        image_response = requests.get(link, timeout=15)
        image_response.raise_for_status()
        image_data = image_response.content
    except Exception as e:
        print(f"Failed to download image from source: {e}")
        return None
    
    payload = {
        "chat_id": config["Main Chat id"],
        "caption": text,
        "parse_mode": "HTML"
    }

    files = {
        'photo': ('image.jpg', image_data)
    }
    attempts = 0
    while attempts < max_attempts: 
        response = requests.post(url, data=payload, files=files)
        response_json = response.json()
        print(response_json)
        if response_json.get('ok') == True:
            return response_json['result']['message_id']
        else:
            attempts += 1
            error_code = response_json.get('error_code')
            if error_code == 429:
                retry_after = response_json.get('parameters', {}).get('retry_after', 5)
                print(f"send image: Rate limit exceeded (429). Retrying after {retry_after} seconds...")
                time.sleep(retry_after + 1)
            else:
                raise Exception(f"Telegram API Error: {response_json.get('description', 'Unknown Error')}")

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
    attempts = 0
    while attempts < max_attempts: 
        response = requests.post(url, data=payload)
        response_json = response.json()
        print(response_json)
        if response_json.get('ok') == True:
            print("message pinned")
            return
        else:
            attempts += 1
            error_code = response_json.get('error_code')
            if error_code == 429:
                retry_after = response_json.get('parameters', {}).get('retry_after', 5)
                print(f"pin message : Rate limit exceeded (429). Retrying after {retry_after} seconds...")
                time.sleep(retry_after + 1)
            else:
                raise Exception(f"Telegram API Error: {response_json.get('description', 'Unknown Error')}")

def delete_message(config, message_id):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage"
    payload = {
        "chat_id": config["Main Chat id"],
        "message_id": message_id
    }

    attempts = 0
    while attempts < max_attempts: 
        response = requests.post(url, data=payload)
        response_json = response.json()
        print(response_json)
        if response_json.get('ok') == True:
            return response.json()
        else:
            attempts += 1
            error_code = response_json.get('error_code')
            if error_code == 429:
                retry_after = response_json.get('parameters', {}).get('retry_after', 5)
                print(f"delete message : Rate limit exceeded (429). Retrying after {retry_after} seconds...")
                time.sleep(retry_after + 1)
            else:
                raise Exception(f"Telegram API Error: {response_json.get('description', 'Unknown Error')}")
