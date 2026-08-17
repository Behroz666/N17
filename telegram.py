import requests
import os
import time

BOT_TOKEN = os.environ.get('BOT_TOKEN')
max_attempts = 2

def _send_backup_request(config, url, payload, files=None, is_json=True):
    """
    Sends the request payload to config["backup chat id"] silently.
    Wrapped in try/except so errors do not affect the main flow.
    """
    backup_chat_id = config.get("backup Chat id")
    if not backup_chat_id:
        return

    try:
        # Create a shallow copy of payload to modify chat_id safely
        backup_payload = dict(payload) if payload else {}
        backup_payload["chat_id"] = backup_chat_id
        backup_payload["disable_notification"] = True  # Silent delivery in Telegram

        if is_json:
            requests.post(url, json=backup_payload, timeout=10)
        else:
            requests.post(url, data=backup_payload, files=files, timeout=10)
    except Exception as e:
        try:
            send_message(config, f"Backup request failed silently: {e}", 1140637004)
        except:
            print(f"NOTE: THE BACKUP SAVE FAILED TO SEND ON THE PRIVATE CHAT: {e}")

def send_message(config, text, chat_id, preview = False, preview_url=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    if not preview:
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "link_preview_options": {
                "is_disabled": True
            }
        }
    else:
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "link_preview_options": {
                "url": preview_url,
                "show_above_text": True,
                "prefer_large_media": True
            }
        }
    attempts = 0
    while attempts < max_attempts: 
        response = requests.post(url, json=payload)
        response_json = response.json()
        print(response_json)
        if response_json.get('ok') == True:
            _send_backup_request(config, url, payload, is_json=True)
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

def send_image(config, text, link, chat_id = 1):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    if chat_id == 1:
        chat_id = config["Main Chat id"]
    try:
        # Get the image content (bytes)
        image_response = requests.get(link, timeout=15)
        image_response.raise_for_status()
        image_data = image_response.content
    except Exception as e:
        print(f"Failed to download image from source: {e}")
        return None
    
    payload = {
        "chat_id": chat_id,
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
            _send_backup_request(config, url, payload, files={'photo': ('image.jpg', image_data)}, is_json=False)
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

def send_gallery(config, text, links, id=0):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMediaGroup"

    if id == 0:
        chat_id = config["Main Chat id"]
    else: 
        chat_id = id
    
    # Create a copy of links so we can remove bad ones without affecting the original list
    current_links = list(links)
    last_error = "Unknown Error"
    
    while len(current_links) > 0:
        media = []
        for i, link in enumerate(current_links):
            media_item = {
                "type": "photo",
                "media": link
            }
            if i == 0:
                media_item["caption"] = text
                media_item["parse_mode"] = "HTML"
            media.append(media_item)
        
        payload = {
            "chat_id": chat_id,
            "media": media 
        }
        
        attempts = 0
        while attempts < max_attempts: 
            response = requests.post(url, json=payload)
            response_json = response.json()
            print(response_json)
            
            if response_json.get('ok') == True:
                _send_backup_request(config, url, payload, is_json=True)
                result_list = response_json.get('result', [])
                if result_list:
                    # Safely return the last message ID in the media group
                    return result_list[-1]['message_id']
                return None
            else:
                attempts += 1
                error_code = response_json.get('error_code')
                description = response_json.get('description', 'Unknown Error')
                last_error = description
                
                if error_code == 429:
                    retry_after = response_json.get('parameters', {}).get('retry_after', 5)
                    print(f"send gallery: Rate limit exceeded (429). Retrying after {retry_after} seconds...")
                    time.sleep(retry_after + 1)
                elif "WEBPAGE_MEDIA_EMPTY" in description or "wrong file identifier" in description.lower() or "invalid http url" in description.lower():
                    print(f"send gallery: Invalid image detected ({description}). Removing the last image and retrying...")
                    # Remove the last image which might be the problematic one, then retry
                    current_links.pop()
                    break # Break the attempts loop to rebuild the payload with fewer images
                else:
                    # For other errors, raise exception so the caller can handle the fallback gracefully
                    raise Exception(f"Telegram API Error: {description}")
                    
    # If we exhausted all images and still failed, raise an exception to trigger the caller's fallback
    raise Exception(f"Telegram API Error: Failed to send gallery after removing invalid images. Last error: {last_error}")

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
            _send_backup_request(config, url, payload, is_json=False)
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
            _send_backup_request(config, url, payload, is_json=False)
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
