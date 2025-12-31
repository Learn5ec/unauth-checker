import os
import requests

class AIAgent:
    def __init__(self):
        self.api_key = os.getenv("MISTRAL_API_KEY")
        self.endpoint = "https://api.mistral.ai/v1/chat/completions"
        self.model = "mistral-small-latest"

        if not self.api_key:
            raise RuntimeError("MISTRAL_API_KEY environment variable not set")

    def generate_sample_value(self, param_type: str, name: str, description: str) -> str:
        prompt = (
            "Generate a realistic example value for an API parameter.\n"
            f"Name: {name}\n"
            f"Type: {param_type}\n"
            f"Description: {description}\n"
            "Return only the value."
        )

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": 50
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        try:
            r = requests.post(
                self.endpoint,
                json=payload,
                headers=headers,
                timeout=10
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"].strip()
        except Exception:
            return "test"
