import json

import requests

from core.config import ModelConfig, normalize_chat_api_url, normalize_wire_api, require_complete_config


SYSTEM_PROMPT = "You are a helpful automation agent."
MODEL_RESPONSE_TIMEOUT_SECONDS = 120


class LLM:
    def __init__(self, config: ModelConfig):
        require_complete_config(config)
        self.wire_api = normalize_wire_api(config.wire_api)
        self.api_url = normalize_chat_api_url(config.api_url, self.wire_api)
        self.model = config.model.strip()
        self.api_key = config.api_key.strip()

    def _chat_completions_payload(self, prompt: str) -> dict[str, object]:
        return {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        }

    def _responses_payload(self, prompt: str) -> dict[str, object]:
        return {
            "model": self.model,
            "instructions": SYSTEM_PROMPT,
            "input": prompt,
            "temperature": 0.2,
        }

    def _payload(self, prompt: str) -> dict[str, object]:
        if self.wire_api == "responses":
            return self._responses_payload(prompt)
        return self._chat_completions_payload(prompt)

    def _extract_chat_completions_text(self, data: dict[str, object]) -> str:
        try:
            choices = data["choices"]
            if not isinstance(choices, list):
                raise TypeError
            message = choices[0]["message"]
            content = message["content"]
            if not isinstance(content, str):
                raise TypeError
            return content.strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError(f"Model API returned an unexpected response: {data}") from exc

    def _extract_responses_text(self, data: dict[str, object]) -> str:
        output_text = data.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return output_text.strip()

        collected: list[str] = []
        output = data.get("output")
        if isinstance(output, list):
            for item in output:
                if not isinstance(item, dict):
                    continue
                content = item.get("content")
                if not isinstance(content, list):
                    continue
                for part in content:
                    if not isinstance(part, dict):
                        continue
                    text = part.get("text") or part.get("content")
                    if isinstance(text, str) and text.strip():
                        collected.append(text.strip())
        if collected:
            return "\n".join(collected).strip()

        return self._extract_chat_completions_text(data)

    def _extract_text(self, data: dict[str, object]) -> str:
        if self.wire_api == "responses":
            return self._extract_responses_text(data)
        return self._extract_chat_completions_text(data)

    def chat(self, prompt: str) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = self._payload(prompt)

        response = requests.post(
            self.api_url,
            headers=headers,
            json=payload,
            timeout=MODEL_RESPONSE_TIMEOUT_SECONDS,
        )
        response.raise_for_status()

        try:
            data = json.loads(response.content.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Model API returned invalid UTF-8 JSON.") from exc

        if not isinstance(data, dict):
            raise ValueError(f"Model API returned an unexpected response: {data}")
        return self._extract_text(data)
