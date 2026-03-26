import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Load environment variables from the .env file in the same directory as this file
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path)

def call_ai(prompt: str, system_prompt: str = "", config: dict = {}) -> str:
    """
    The Swappable AI Caller - THE Single point for AI interaction.
    
    This function handles all AI calls in the system, currently set up 
    to use the new Google Gen AI SDK (google-genai).
    
    Args:
        prompt (str): The main input text for the AI.
        system_prompt (str): Optional system-level instructions.
        config (dict): Optional configuration parameters like model_name, etc.
    
    Returns:
        str: The generated text response from the AI.
    """
    # Priority for API key:
    # 1. Passed in config['api_key'] 
    # 2. 'AI_API' environment variable (as requested)
    # 3. 'GOOGLE_API_KEY' environment variable (fallback)
    api_key = config.get("api_key") or os.getenv("AI_API") or os.getenv("GOOGLE_API_KEY")
    
    if not api_key:
        raise ValueError("API Key not found. Please set 'AI_API' in your .env or "
                         "pass 'api_key' in the config during the call.")
    
    # Initialize the Google Gen AI Client
    use_vertexai = config.get("vertexai", os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "False").lower() == "true")
    client = genai.Client(api_key=api_key, vertexai=use_vertexai)
    
    # Select the model - default to gemini-2.0-flash
    model_name = config.get("model_name", "gemini-2.0-flash")
    
    # Prepare the GenerateContentConfig
    gen_config = types.GenerateContentConfig(
        system_instruction=system_prompt if system_prompt else None,
        max_output_tokens=config.get("max_tokens", 4096),
        temperature=config.get("temperature", 0.7),
        top_p=config.get("top_p", 1.0),
        stop_sequences=config.get("stop", [])
    )
    
    # Standard generation call
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=gen_config
        )
        
        # Verify the response content exists
        if response and response.text:
            return response.text.strip()
        else:
            return "Error: AI generated an empty response or was blocked."
            
    except Exception as e:
        # Structured error handling for debugging
        return f"Error calling Google Gen AI SDK: {str(e)}"
