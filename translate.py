import requests
import json
import os
import random

AI_TOKEN = os.environ.get('AI_TOKEN')
AI_TOKEN = AI_TOKEN.split(",")
print("len ai key list:" + str(len(AI_TOKEN)))

def is_new(config, text, history):
    response = requests.post(
    url="https://openrouter.ai/api/v1/chat/completions",
    headers={
        "Authorization": f"Bearer {random.choice(AI_TOKEN)}",
        "Content-Type": "application/json",
    },
    data=json.dumps({
        "model": config["Model Name"],
        "messages": [
            {
            "role": "user",
            "content": str(text)
            },
            {
            "role": "system",
            "content": f"{config['agent system prompt']}\n\n{history}\n\nJust Answer True or False"
            }
        ],
        
    })
    )
    print(response.json())
    answer = response.json()['choices'][0]['message']['content']

    if str(answer).lower().startswith("f"):
        return True
    else:
        return False    

def article_summarize(config, text, title):
    response = requests.post(
    url="https://openrouter.ai/api/v1/chat/completions",
    headers={
        "Authorization": f"Bearer {random.choice(AI_TOKEN)}",
        "Content-Type": "application/json",
    },
    data=json.dumps({
        "model": config["Model Name"],
        "messages": [
            {
            "role": "user",
            "content": str(text)
            },
            {
            "role": "system",
            "content": config["Acticle System Prompt"] + f"تو باید این عنوان را هم در نظر داشته باشی {title} و به سوال و موضوع اصلی مطرح شده در این عنوان بپردازی اگر نوشته جالب دیگری هم در متن وجود داشت و میتوانستی با در نظر گرفتن محدودیت طول متن خروجی آن را هم ذکر کنی آن را انجام بده. پس تو باید یک پاراگراف حذاب و خلاصه از متن داده شده با در نظر داشتن عنوان ارائه بدی"
            }
        ],
        
    })
    )

    response_json = response.json()
    print(response_json)
    return response_json['choices'][0]['message']['content']

def summarize(config, text):
    response = requests.post(
    url="https://openrouter.ai/api/v1/chat/completions",
    headers={
        "Authorization": f"Bearer {random.choice(AI_TOKEN)}",
        "Content-Type": "application/json",
    },
    data=json.dumps({
        "model": config["Model Name"],
        "messages": [
            {
            "role": "user",
            "content": str(text)
            },
            {
            "role": "system",
            "content": config["Summarize System Prompt"]
            }
        ],
        
    })
    )

    response_json = response.json()
    print(response_json)
    return response_json['choices'][0]['message']['content']

def translate(config, text, fail, additional):
    if fail == "1":
        model = config["Fallback Model Name"]
    else:
        model = config["Model Name"]
    response = requests.post(
    url="https://openrouter.ai/api/v1/chat/completions",
    headers={
        "Authorization": f"Bearer {random.choice(AI_TOKEN)}",
        "Content-Type": "application/json",
    },
    data=json.dumps({
        "model": model,
        "messages": [
            {
            "role": "user",
            "content": str(text)
            },
            {
            "role": "system",
            "content": config["Translation System Prompt"] + additional
            }
        ],
        
    })
    )

    response_json = response.json()
    print(response_json)
    return response_json['choices'][0]['message']['content']
