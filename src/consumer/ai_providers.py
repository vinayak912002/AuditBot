from abc import ABC, abstractmethod
import os
import json
import logging
from src.consumer.schemas import InvoiceData

logger = logging.getLogger(__name__)

class BaseAIProvider(ABC):
    """
    Interface for AI extraction providers. 
    Every new provider (e.g., DeepSeek, Groq) must implement this class.
    """
    def _build_prompt(self, text: str) -> str:
        """Generates a strict prompt injecting the required JSON Schema."""
        schema_json = json.dumps(InvoiceData.model_json_schema(), indent=2)
        return (
            "You are an expert data extraction assistant.\n"
            "Extract the invoice details from the text below.\n"
            "You MUST return ONLY valid JSON that strictly adheres to the following JSON Schema:\n"
            f"{schema_json}\n\n"
            f"Text to extract from:\n{text}"
        )

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
        prompt = self._build_prompt(text)
        response = self.client.messages.create(
            model=self.model,
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        try:
            raw_dict = json.loads(response.content[0].text)
            validated_data = InvoiceData.model_validate(raw_dict)
            return validated_data.model_dump()
        except Exception as e:
            logger.error(f"Anthropic Validation/Parsing failed: {e}")
            return {"raw_response": response.content[0].text, "error": str(e)}

class OpenAIProvider(BaseAIProvider):
    """Implementation for OpenAI's GPT models."""
    def __init__(self):
        from openai import OpenAI
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o")

    def extract_invoice_data(self, text: str) -> dict:
        prompt = self._build_prompt(text)
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        try:
            raw_dict = json.loads(response.choices[0].message.content)
            validated_data = InvoiceData.model_validate(raw_dict)
            return validated_data.model_dump()
        except Exception as e:
            logger.error(f"OpenAI Validation/Parsing failed: {e}")
            return {"raw_response": response.choices[0].message.content, "error": str(e)}

class GeminiProvider(BaseAIProvider):
    """Implementation for Google's Gemini models using the new google-genai SDK."""
    def __init__(self):
        from google import genai
        # Initialize the new genai Client with the API key from environment variables
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")

    def extract_invoice_data(self, text: str) -> dict:
        prompt = self._build_prompt(text)
        
        # Call the Gemini model using the modern Client.models API
        # We pass response_mime_type to enforce structured JSON output from the model
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config={"response_mime_type": "application/json"}
        )
        
        try:
            raw_dict = json.loads(response.text)
            validated_data = InvoiceData.model_validate(raw_dict)
            return validated_data.model_dump()
        except Exception as e:
            logger.error(f"Gemini Validation/Parsing failed: {e}")
            return {"raw_response": response.text, "error": str(e)}

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
