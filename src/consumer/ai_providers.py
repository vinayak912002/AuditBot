from abc import ABC, abstractmethod
import os
import json
import logging

logger = logging.getLogger(__name__)

class BaseAIProvider(ABC):
    """
    Interface for AI extraction providers. 
    Every new provider (e.g., DeepSeek, Groq) must implement this class.
    """
    @abstractmethod
    def extract_invoice_data(self, text: str) -> dict:
        """Standard method to extract structured JSON from raw text."""
        pass

class AnthropicProvider(BaseAIProvider):
    """Implementation for Anthropic's Claude models."""
    def __init__(self):
        from anthropic import Anthropic
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.model = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20240620")

    def extract_invoice_data(self, text: str) -> dict:
        prompt = f"Extract Vendor, Date, Amount, and Tax from the following text:\n\n{text}\n\nReturn JSON only."
        response = self.client.messages.create(
            model=self.model,
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        try:
            return json.loads(response.content[0].text)
        except Exception:
            return {"raw_response": response.content[0].text}

class OpenAIProvider(BaseAIProvider):
    """Implementation for OpenAI's GPT models."""
    def __init__(self):
        from openai import OpenAI
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o")

    def extract_invoice_data(self, text: str) -> dict:
        prompt = f"Extract Vendor, Date, Amount, and Tax from the following text:\n\n{text}\n\nReturn JSON only."
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        try:
            return json.loads(response.choices[0].message.content)
        except Exception:
            return {"raw_response": response.choices[0].message.content}

class GeminiProvider(BaseAIProvider):
    """Implementation for Google's Gemini models."""
    def __init__(self):
        import google.generativeai as genai
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")
        self.model = genai.GenerativeModel(self.model_name)

    def extract_invoice_data(self, text: str) -> dict:
        prompt = f"Extract Vendor, Date, Amount, and Tax from the following text:\n\n{text}\n\nReturn JSON only."
        # Using Google's native JSON mode
        response = self.model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        try:
            return json.loads(response.text)
        except Exception:
            return {"raw_response": response.text}

def get_ai_provider() -> BaseAIProvider:
    """
    FACTORY FUNCTION:
    Reads the AI_PROVIDER from the .env and returns the corresponding class instance.
    """
    provider_name = os.getenv("AI_PROVIDER", "anthropic").lower()
    if provider_name == "anthropic":
        return AnthropicProvider()
    elif provider_name == "openai":
        return OpenAIProvider()
    elif provider_name == "gemini":
        return GeminiProvider()
    else:
        raise ValueError(f"Unsupported AI provider: {provider_name}")
