import requests
import json

def translate(config, text):
    response = requests.post(
    url="https://openrouter.ai/api/v1/chat/completions",
    headers={
        "Authorization": f"Bearer {config["AI Token"]}",
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
            "content": config["System Prompt"]
            }
        ],
        
    })
    )

    response_json = response.json()
    return response_json['choices'][0]['message']['content']