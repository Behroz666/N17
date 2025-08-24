import requests
import json
import os

AI_TOKEN = os.environ.get('AI_TOKEN')

def is_new(config, text, history):
    print("1")
    response = requests.post(
    url="https://openrouter.ai/api/v1/chat/completions",
    headers={
        "Authorization": f"Bearer {AI_TOKEN}",
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
            "content": f"{config["agent system prompt"]}\n\n{history}\n\nJust Answer True or False"
            }
        ],
        
    })
    )

    answer = response.json()['choices'][0]['message']['content']
    print(answer)
    if str(answer).lower().startswith("t"):
        return True
    else:
        return False    

def article_summarize(config, text):
    response = requests.post(
    url="https://openrouter.ai/api/v1/chat/completions",
    headers={
        "Authorization": f"Bearer {AI_TOKEN}",
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
            "content": config["Acticle System Prompt"]
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
        "Authorization": f"Bearer {AI_TOKEN}",
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

def translate(config, text):
    response = requests.post(
    url="https://openrouter.ai/api/v1/chat/completions",
    headers={
        "Authorization": f"Bearer {AI_TOKEN}",
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
            "content": config["Translation System Prompt"]
            }
        ],
        
    })
    )

    response_json = response.json()
    print(response_json)
    return response_json['choices'][0]['message']['content']