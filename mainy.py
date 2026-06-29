import subprocess
import json
import os
import tempfile
from telegram import send_image, send_message, send_gallery, pin_message, delete_message
import time
from gemini import ask_gemini

hyperlink = "🔹 <a href='https://t.me/N17_Tottenham'>N17 Tottenham</a> | <a href='https://t.me/+2TG8ZxphObwzN2Q0'>VivaSpurs</a>"

def get_community_posts(channel_url):
    # Create a temporary directory so we don't clutter your main folders
    with tempfile.TemporaryDirectory() as tmpdir:
        
        # Build the CLI command
        # -f specifies the output folder path
        command = ["yp-dl", "-f", tmpdir, "-l", "10", channel_url]
        
        print(f"Scraping community posts for {channel_url}...")
        
        # Run the command and wait for it to finish
        result = subprocess.run(command, capture_output=True, text=True)
        
        if result.returncode != 0:
            print("Error executing yp-dl:")
            print(result.stderr)
            return None

        # Look for the generated JSON file in the temporary directory
        files = [f for f in os.listdir(tmpdir) if f.endswith('.json')]
        
        if not files:
            print("No JSON file was generated. Check if the channel URL is valid.")
            return None
        
        # Read the first json file found
        json_file_path = os.path.join(tmpdir, files[0])
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        return data

with open('config.json', 'r', encoding='utf-8') as file:
    config = json.load(file)

with open('seen_feedy.json', 'r', encoding='utf-8') as file:
    done_posts = json.load(file)

channel = "https://www.youtube.com/@ChrisCowlin"
posts_json = get_community_posts(channel)

if posts_json:
    # 'posts_json' is now a native Python variable (list or dict)
    print(f"Successfully retrieved {len(posts_json)} posts!")
    for news in reversed(posts_json):
        if news['post_link'] not in done_posts["done"] and "youtu.be" not in news['text']:
            news['text'] = news['text'].replace("#COYS #THFC","")
            url = news['post_link']
            print(url)
            fa = ask_gemini(user_prompt=news['text'], system_prompt=config["Translation System Prompt"])
            if len(fa) < (len(news['text'])/2):
                continue
            if news['images'] is None:
                limit = 4096
                if len(fa + news['text']) < (limit - 300):
                    message = f"{fa}\n\n<blockquote expandable><a href='{url}'>🇬🇧</a>: {news['text']}</blockquote>\n\n✍️ {news['time_since']} by Chris Cowlin\n\n{hyperlink}"
                elif len(fa) < (limit - 500):
                    message = f"{fa}\n\n<blockquote expandable><a href='{url}'>🇬🇧</a>: {news['text'][:(limit - 300 -len(fa))]}</blockquote>\n\n✍️ {news['time_since']} by Chris Cowlin\n\n{hyperlink}"
                else:
                    message = f"{fa[:(limit - 196)]}\n\n{hyperlink}"
            else:
                limit = 1024
                text_is_too_long_needs_splitting = False
                if len(fa + news['text']) < (limit - 300):
                    message = f"{fa}\n\n<blockquote expandable><a href='{url}'>🇬🇧</a>: {news['text']}</blockquote>\n\n✍️ {news['time_since']} by Chris Cowlin\n\n{hyperlink}"
                elif len(fa) < (limit - 450):
                    message = f"{fa}\n\n<blockquote expandable><a href='{url}'>🇬🇧</a>: {news['text'][:(limit - 300 -len(fa))]}</blockquote>\n\n✍️ {news['time_since']} by Chris Cowlin\n\n{hyperlink}"
                elif len(fa) < (limit - 130):
                    message = f"{fa[:(limit - 130)]}\n\n{hyperlink}"
                else: 
                    text_is_too_long_needs_splitting = True
                    limit = 4096
                    if len(fa + news['text']) < (limit - 300):
                        message = f"{fa}\n\n<blockquote expandable><a href='{url}'>🇬🇧</a>: {news['text']}</blockquote>\n\n✍️ {news['time_since']} by Chris Cowlin\n\n{hyperlink}"
                    elif len(fa) < (limit - 500):
                        message = f"{fa}\n\n<blockquote expandable><a href='{url}'>🇬🇧</a>: {news['text'][:(limit - 300 -len(fa))]}</blockquote>\n\n✍️ {news['time_since']} by Chris Cowlin\n\n{hyperlink}"
                    else:
                        message = f"{fa[:(limit - 196)]}\n\n{hyperlink}"
                
            if news['images'] is None:
                message_id = send_message(config, message, config["Main Chat id"])
            elif len(news['images']) == 1:
                if not text_is_too_long_needs_splitting:
                    message_id = send_image(config, message, news['images'][0])
                else:
                    message_id = send_image(config, hyperlink, news['images'][0])
                    message_id = send_message(config, message, config["Main Chat id"])
            elif len(news['images']) > 1:
                if not text_is_too_long_needs_splitting:
                    message_id = send_gallery(config, message, news['images'])
                else:
                    message_id = send_gallery(config, hyperlink, news['images'])
                    message_id = send_message(config, message, config["Main Chat id"])
            pin_message(config, message_id)
            # delete_message(config, message_id + 1)
            done_posts["done"].append(url)
            time.sleep(15)

    with open('seen_feedy.json', 'w', encoding='utf-8') as file:
        json.dump(done_posts, file)
        print("saving done")