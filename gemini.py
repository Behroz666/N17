from google import genai
from google.genai import types
from google.genai.errors import ServerError
from google.genai.errors import APIError
import time
import os
from pydantic import BaseModel
from typing import Type

def ask_gemini_structured(
    user_prompt: str, 
    response_schema: Type[BaseModel], 
    system_prompt: str = None
) -> BaseModel:
    """
    Calls Gemini models with a fallback chain and returns a strongly-typed Pydantic object.
    """
    client = genai.Client(api_key=os.environ.get('GOOGLE_AI_TOKEN'))
    
    # Define your fallback chain in order of preference
    models_to_try = [
        'gemini-3.1-flash-lite',
        'gemini-2.5-flash-lite',
        'gemma-4-31b-it' 
    ]
    
    # Configure the schema and instruct the model to return JSON matching it
    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        response_mime_type="application/json",
        response_schema=response_schema
    )
    
    for model in models_to_try:
        try:
            print(f"Attempting to use model: {model}...")
            response = client.models.generate_content(
                model=model,
                contents=user_prompt,
                config=config
            )
            
            # The SDK automatically parses the JSON text back into your Pydantic model
            # if provided via response_schema on supported versions.
            # If your SDK version returns raw text, use: response_schema.model_validate_json(response.text)
            return response.parsed
            
        except ServerError as e:
            if e.code == 503:
                print(f"⚠️ {model} is facing high demand (503). Trying next fallback...")
                time.sleep(1)
                continue
            else:
                raise e
        except Exception as e:
            print(f"An unexpected error occurred with {model}: {e}")
            raise e
            
    raise RuntimeError("All models in the fallback chain failed due to high demand.")

def ask_gemini(user_prompt: str, system_prompt: str = None) -> str:

    client = genai.Client(api_key=os.environ.get('GOOGLE_AI_TOKEN'))
    
    # Define your fallback chain in order of preference
    models_to_try = [
        'gemini-3.1-flash-lite',
        'gemini-2.5-flash-lite',
        'gemma-4-31b-it' 
    ]
    
    config = types.GenerateContentConfig(
        system_instruction=system_prompt
    )
    
    for model in models_to_try:
        try:
            print(f"Attempting to use model: {model}...")
            response = client.models.generate_content(
                model=model,
                contents=user_prompt,
                config=config
            )
            text_result = response.candidates[0].content.parts[0].text
            return(text_result)
            
        except ServerError as e:
            # Check if it is a 503 or transient overload error
            if e.code == 503:
                print(f"⚠️ {model} is facing high demand (503). Trying next fallback...")
                time.sleep(1) # Small pause before hitting the next endpoint
                continue
            else:
                # If it's a different server error (like a 500), re-raise it
                raise e
        except Exception as e:
            # Catch other unexpected errors (like network dropping completely)
            print(f"An unexpected error occurred with {model}: {e}")
            raise e
            
    # If the loop finishes and all models failed
    raise RuntimeError("All models in the fallback chain failed due to high demand.")

def ask_gemini_youtube(
    video_url: str, 
    YouTubeVideoAnalysis: Type[BaseModel], 
    video_title: str = "Extract the video title yourself"
) -> BaseModel:
    
    # The new SDK automatically picks up GEMINI_API_KEY from os.environ, 
    # but passing it explicitly via GOOGLE_AI_TOKEN works perfectly fine.
    client = genai.Client(api_key=os.environ.get('GOOGLE_AI_TOKEN'))

    models_to_try = [
        'gemini-3.1-flash-lite',
        'gemini-2.5-flash-lite'
    ]

    prompt = (
        "Analyze the provided YouTube video. "
        f"1. This is the video title: '{video_title}'. Translate it accurately into Persian. "
        "2. Provide a detailed summary of the video content strictly in Persian. "
        "The summary must be informative, high-quality, and strictly less than 3500 characters."
    )

    for model in models_to_try:
        try:
            print(f"Attempting to use model: {model}...")
            
            response = client.models.generate_content(
                model=model, # Fix: Used the loop variable instead of a hardcoded string
                contents=[
                    # Fix: For YouTube URLs, use types.FileData instead of from_uri
                    types.Part(
                        file_data=types.FileData(
                            file_uri=video_url,
                            mime_type="video/mp4"
                        )
                    ),
                    types.Part(text=prompt)
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=YouTubeVideoAnalysis,
                    temperature=0.3
                )
            )

            return response.parsed
            
        except APIError as e:
            # The new SDK groups codes under e.code
            if e.code == 503:
                print(f"⚠️ {model} is facing high demand (503). Trying next fallback...")
                time.sleep(2)
                continue
            else:
                print(f"API Error occurred with {model}: {e}")
                raise e
        except Exception as e:
            print(f"An unexpected error occurred with {model}: {e}")
            raise e
            
    raise RuntimeError("All models in the fallback chain failed due to high demand.")