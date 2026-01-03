import logging
from typing import List, Dict, Tuple

import requests


class OllamaClient:
    def __init__(
        self,
        host: str,
        model: str,
        timeout: float = 60.0,
        load_timeout: float | None = None,
        connect_timeout: float = 5.0,
    ) -> None:
        self.host = host.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.load_timeout = load_timeout if load_timeout is not None else max(timeout * 3, 120.0)
        self.connect_timeout = connect_timeout
        self._pending_model_load = False
        self._session = requests.Session()

    def set_model(self, model: str) -> None:
        if model == self.model:
            return
        self.model = model
        self._pending_model_load = True
        self._session = requests.Session()

    def _request_timeout(self) -> Tuple[float, float]:
        read_timeout = self.load_timeout if self._pending_model_load else self.timeout
        return (self.connect_timeout, read_timeout)

    def chat(self, messages: List[Dict[str, str]], stream: bool = False) -> str:
        url = f"{self.host}/api/chat"
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
        }
        logging.debug("POST %s payload=%s", url, payload)
        response = self._session.post(url, json=payload, timeout=self._request_timeout())
        
        try:
            response.raise_for_status()
        except requests.HTTPError as e:
            logging.error(f"HTTP Error: {e}")
            logging.error(f"Response content: {response.text}")
            raise e
            
        data = response.json()
        logging.debug("response=%s", data)
        message = data.get("message", {})
        if self._pending_model_load:
            self._pending_model_load = False
        return message.get("content", "")

    def list_models(self) -> List[str]:
        url = f"{self.host}/api/tags"
        try:
            response = self._session.get(url, timeout=(self.connect_timeout, self.timeout))
            response.raise_for_status()
            data = response.json()
            models = [model["name"] for model in data.get("models", [])]
            return models
        except Exception as e:
            logging.error(f"Failed to list models: {e}")
            return []
