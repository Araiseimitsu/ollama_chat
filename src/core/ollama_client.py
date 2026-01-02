import logging
from typing import List, Dict

import requests


class OllamaClient:
    def __init__(self, host: str, model: str, timeout: float = 60.0) -> None:
        self.host = host.rstrip("/")
        self.model = model
        self.timeout = timeout
        self._session = requests.Session()

    def chat(self, messages: List[Dict[str, str]], stream: bool = False) -> str:
        url = f"{self.host}/api/chat"
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
        }
        logging.debug("POST %s payload=%s", url, payload)
        response = self._session.post(url, json=payload, timeout=self.timeout)
        
        try:
            response.raise_for_status()
        except requests.HTTPError as e:
            logging.error(f"HTTP Error: {e}")
            logging.error(f"Response content: {response.text}")
            raise e
            
        data = response.json()
        logging.debug("response=%s", data)
        message = data.get("message", {})
        return message.get("content", "")

    def list_models(self) -> List[str]:
        url = f"{self.host}/api/tags"
        try:
            response = self._session.get(url, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            models = [model["name"] for model in data.get("models", [])]
            return models
        except Exception as e:
            logging.error(f"Failed to list models: {e}")
            return []
