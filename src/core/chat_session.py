from typing import List, Dict, Optional, Any


class ChatSession:
    def __init__(self, system_prompt: Optional[str] = None) -> None:
        self._messages: List[Dict[str, Any]] = []
        if system_prompt:
            self._messages.append({"role": "system", "content": system_prompt})

    @property
    def messages(self) -> List[Dict[str, Any]]:
        return list(self._messages)

    def add_user(self, content: str, images: Optional[List[Dict[str, str]]] = None) -> None:
        message: Dict[str, Any] = {"role": "user", "content": content}
        if images:
            message["images"] = images
        self._messages.append(message)

    def add_assistant(self, content: str, thinking: Optional[str] = None) -> None:
        """
        アシスタントのメッセージを追加

        Args:
            content: 最終回答テキスト
            thinking: 思考過程（thinkingモデル使用時のみ）
        """
        message = {"role": "assistant", "content": content}
        if thinking:
            message["thinking"] = thinking
        self._messages.append(message)

    def ollama_messages(self) -> List[Dict[str, Any]]:
        """
        Ollama API 用に整形したメッセージを返す。
        画像は base64 文字列の配列へ変換し、thinking などの表示用キーは除外する。
        """
        normalized: List[Dict[str, Any]] = []
        for message in self._messages:
            role = message.get("role")
            content = message.get("content", "")
            payload: Dict[str, Any] = {"role": role, "content": content}

            if role == "user" and message.get("images"):
                images = message.get("images", [])
                payload["images"] = [
                    image.get("data") if isinstance(image, dict) else image
                    for image in images
                ]
            normalized.append(payload)

        return normalized
