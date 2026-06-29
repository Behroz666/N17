from google import genai
from google.genai import types
from google.genai.errors import ServerError
import time
import os

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