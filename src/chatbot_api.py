from google import genai
from config import *
import logging

# =======================================================
# Gemini API Functions
# =======================================================

gemini_client = genai.Client(api_key=api_keys["GEMINI_API_KEY"])

def get_gemini_response(prompt):
    try:
        response = gemini_client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
        )

        return response.text
    except Exception as e:
        logging.error(f"❌ Error fetching Gemini response: {e}")
        return None