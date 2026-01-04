import logging
import re
import json
from typing import List, Dict, Tuple, Optional, Generator, Any

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
        self._image_support_cache: Dict[str, Optional[bool]] = {}

    def set_model(self, model: str) -> None:
        if model == self.model:
            return
        self.model = model
        self._pending_model_load = True
        self._session = requests.Session()

    def _request_timeout(self) -> Tuple[float, float]:
        read_timeout = self.load_timeout if self._pending_model_load else self.timeout
        return (self.connect_timeout, read_timeout)

    def chat(self, messages: List[Dict[str, Any]], stream: bool = False) -> Tuple[Optional[str], str]:
        """
        チャットを実行してthinkingと回答を返す

        Returns:
            (thinking_content, answer_content) のタプル
            thinking対応モデルの場合はthinkingを抽出、それ以外はNone
        """
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

        content = message.get("content", "")
        raw_thinking = message.get("thinking") or message.get("reasoning")

        if raw_thinking:
            thinking = raw_thinking.strip()
            answer = content
        else:
            # thinkingタグの有無で動的に判定（モデル名に依らず抽出を試みる）
            thinking, answer = self._extract_thinking(content)

        if thinking:
            logging.debug(f"Thinking extracted: {len(thinking)} chars, answer: {len(answer)} chars")

        return thinking, answer

    def _is_thinking_model(self, model_name: str) -> bool:
        """
        モデルがthinking機能をサポートしているか判定

        thinking対応モデル:
        - deepseek-r1 系
        - qwq 系
        - qwen 系
        - その他の推論モデル
        """
        model_lower = model_name.lower()
        thinking_keywords = [
            "deepseek-r1",
            "r1",
            "qwq",
            "qwen",
            "reasoning",
            "think",
        ]
        return any(keyword in model_lower for keyword in thinking_keywords)

    def _guess_image_model(self, model_name: str) -> Optional[bool]:
        model_lower = model_name.lower()
        image_keywords = [
            "llava",
            "bakllava",
            "llama3.2-vision",
            "llama-vision",
            "vision",
            "qwen2-vl",
            "qwen-vl",
            "qwenvl",
            "minicpm",
            "moondream",
            "cogvlm",
            "phi-3-vision",
            "phi-4-vision",
        ]
        if any(keyword in model_lower for keyword in image_keywords):
            return True
        return None

    def supports_images(self, model_name: Optional[str] = None) -> Optional[bool]:
        """
        モデルが画像入力をサポートしているか判定する。
        Ollama /api/show の capabilities を優先し、取得できない場合はモデル名から推測する。
        """
        target_model = model_name or self.model
        if target_model in self._image_support_cache:
            return self._image_support_cache[target_model]

        url = f"{self.host}/api/show"
        try:
            response = self._session.post(
                url,
                json={"name": target_model},
                timeout=self._request_timeout()
            )
            response.raise_for_status()
            data: Dict[str, Any] = response.json()
            details = data.get("details", {}) if isinstance(data.get("details"), dict) else {}
            capabilities = details.get("capabilities") or data.get("capabilities")

            if isinstance(capabilities, list):
                result = any(str(item).lower() == "vision" for item in capabilities)
            else:
                result = self._guess_image_model(target_model)
        except Exception as e:
            logging.warning("Failed to detect image capability for %s: %s", target_model, e)
            result = self._guess_image_model(target_model)

        if result is not None:
            self._image_support_cache[target_model] = result
        return result

    def _extract_thinking(self, content: str) -> Tuple[Optional[str], str]:
        """
        レスポンスからthinking部分と回答部分を抽出

        多くのthinkingモデルは <think>...</think> タグで思考過程を出力する
        タグがあれば動的にthinking対応と判定される
        """
        # <think>...</think> パターンを検索
        think_pattern = r'<think>(.*?)</think>'
        matches = re.findall(think_pattern, content, re.DOTALL)

        if matches:
            # thinkingタグが見つかった場合
            thinking = "\n\n".join(matches)  # 複数のthinkタグがある場合は結合
            # thinkタグを除去して回答部分を取得
            answer = re.sub(think_pattern, '', content, flags=re.DOTALL).strip()
            return thinking.strip(), answer

        # thinkタグがない場合は通常の応答として扱う
        return None, content

    def chat_stream(self, messages: List[Dict[str, Any]]) -> Generator[Dict[str, str], None, None]:
        """
        チャットをストリーミング実行してthinkingと回答を逐次返す

        Yields:
            {"type": "thinking", "content": "..."} または
            {"type": "response", "content": "..."}
        """
        url = f"{self.host}/api/chat"
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
        }
        logging.debug("POST %s payload=%s (streaming)", url, payload)

        try:
            response = self._session.post(
                url,
                json=payload,
                timeout=self._request_timeout(),
                stream=True
            )
            response.raise_for_status()

            if self._pending_model_load:
                self._pending_model_load = False

            # ストリーミング状態の管理
            in_think_tag = False
            accumulated_buffer = ""

            for line in response.iter_lines():
                if not line:
                    continue

                try:
                    chunk = json.loads(line)
                    message = chunk.get("message", {})
                    content = message.get("content", "")
                    thinking_chunk = message.get("thinking") or message.get("reasoning") or chunk.get("thinking") or chunk.get("reasoning")

                    if thinking_chunk:
                        yield {"type": "thinking", "content": thinking_chunk}

                    if not content:
                        continue

                    # バッファに追加
                    accumulated_buffer += content

                    # <think>タグの開始を検出
                    if "<think>" in accumulated_buffer and not in_think_tag:
                        # タグ前の部分をresponseとして出力
                        before_tag = accumulated_buffer.split("<think>")[0]
                        if before_tag.strip():
                            yield {"type": "response", "content": before_tag}

                        in_think_tag = True
                        # タグ以降をバッファに保持
                        accumulated_buffer = accumulated_buffer.split("<think>", 1)[1]

                    # </think>タグの終了を検出
                    if "</think>" in accumulated_buffer and in_think_tag:
                        # タグ内の内容をthinkingとして出力
                        think_content = accumulated_buffer.split("</think>")[0]
                        if think_content.strip():
                            yield {"type": "thinking", "content": think_content}

                        in_think_tag = False
                        # タグ後の部分をバッファに保持
                        accumulated_buffer = accumulated_buffer.split("</think>", 1)[1]

                    # タグ内の場合は逐次thinking出力
                    elif in_think_tag:
                        yield {"type": "thinking", "content": content}
                        accumulated_buffer = ""
                    # タグ外の場合は逐次response出力
                    else:
                        # まだタグが開始していない可能性があるため、バッファを確認
                        if "<think>" not in accumulated_buffer:
                            yield {"type": "response", "content": content}
                            accumulated_buffer = ""

                except json.JSONDecodeError as e:
                    logging.error(f"Failed to parse streaming response: {e}")
                    continue

            # 最後にバッファに残っている内容を出力
            if accumulated_buffer.strip():
                if in_think_tag:
                    yield {"type": "thinking", "content": accumulated_buffer}
                else:
                    yield {"type": "response", "content": accumulated_buffer}

        except requests.HTTPError as e:
            logging.error(f"HTTP Error: {e}")
            raise e
        except Exception as e:
            logging.error(f"Streaming error: {e}")
            raise e

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
