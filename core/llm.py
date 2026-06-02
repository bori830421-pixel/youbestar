import requests

from core.config import ModelConfig, normalize_chat_api_url, require_complete_config


SYSTEM_PROMPT = "You are a helpful automation agent."


class LLM:
    def __init__(self, config: ModelConfig):
        require_complete_config(config)
        self.api_url = normalize_chat_api_url(config.api_url)
        self.model = config.model.strip()
        self.api_key = config.api_key.strip()

    def chat(self, prompt: str) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        }

        response = requests.post(self.api_url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()

        data = response.json()
        try:
            return data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError(f"Model API returned an unexpected response: {data}") from exc
