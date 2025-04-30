import os
import requests
import json
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get API key from environment variable
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")


def call_llm(prompt: str) -> str:
    """
    Send a prompt to Claude via Anthropic API and return the response.

    This function requires an Anthropic API key set as ANTHROPIC_API_KEY environment variable.
    """
    if not ANTHROPIC_API_KEY:
        return "[ERROR: ANTHROPIC_API_KEY environment variable not set]"

    try:
        headers = {
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        data = {
            "model": "claude-3-opus-20240229",
            "max_tokens": 1000,
            "messages": [{"role": "user", "content": prompt}],
        }

        response = requests.post(
            "https://api.anthropic.com/v1/messages", headers=headers, json=data
        )

        response.raise_for_status()
        response_data = response.json()
        return response_data["content"][0]["text"]
    except Exception as e:
        return f"[API ERROR: {str(e)}]"


if __name__ == "__main__":
    prompt = "What is the meaning of life?"
    print(call_llm(prompt))
