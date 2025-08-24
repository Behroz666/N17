import requests
import json
import os
from openai import OpenAI
from pydantic import BaseModel

AI_TOKEN = os.environ.get('AI_TOKEN')

def is_new(config, text, history):
    class AI_Checker(BaseModel):
                is_possible : bool
                why : str
                emoji : str

    client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=AI_TOKEN,
    )

    completion = client.beta.chat.completions.parse(
    model=config["Model Name"],
    messages=[
        {
        "role": "user",
        "content": text
        },
        {
        "role": "system",
        "content" : f"{config["agent system prompt"]}\n\n{history}"
        }
    ],
    response_format=AI_Checker
    )
    print(completion)
    check = completion.choices[0].message.parsed
    return check.is_possible

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