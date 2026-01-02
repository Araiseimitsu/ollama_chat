import argparse
import logging
import os
import sys
from requests import RequestException
from requests import HTTPError

from src.core.ollama_client import OllamaClient
from src.core.chat_session import ChatSession


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ollama（gemma3）簡易チャットボット")
    parser.add_argument("--model", default="gemma3", help="使用するモデル名")
    parser.add_argument(
        "--host",
        default=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
        help="OllamaのホストURL（例: http://localhost:11434）",
    )
    parser.add_argument("--system", default="", help="システムプロンプト")
    parser.add_argument("--timeout", type=float, default=60.0, help="タイムアウト（秒）")
    parser.add_argument("--debug", action="store_true", help="デバッグログを有効化")
    return parser


def configure_logging(debug: bool) -> None:
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(level=level, format="[%(levelname)s] %(message)s")


def print_help() -> None:
    print("/exit または /quit で終了")
    print("空行は無視されます")


def format_http_error(exc: HTTPError) -> str:
    response = exc.response
    if response is None:
        return ""
    status = response.status_code
    url = response.url
    detail = ""
    try:
        payload = response.json()
        detail = payload.get("error", "")
    except ValueError:
        detail = response.text.strip()
    detail = detail.replace("\n", " ").strip()
    if detail:
        return f"HTTP {status} / {url} / {detail}"
    return f"HTTP {status} / {url}"


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()
    configure_logging(args.debug)

    session = ChatSession(system_prompt=args.system or None)
    client = OllamaClient(host=args.host, model=args.model, timeout=args.timeout)

    print("Ollama チャットボットを開始します。")
    print_help()

    while True:
        try:
            user_input = input("あなた> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n終了します。")
            return 0

        if not user_input:
            continue

        if user_input in {"/exit", "/quit"}:
            print("終了します。")
            return 0

        session.add_user(user_input)
        try:
            reply = client.chat(session.messages, stream=False)
        except HTTPError as exc:
            detail = format_http_error(exc)
            logging.error("Ollamaへの接続に失敗しました: %s", exc)
            if detail:
                print(f"詳細: {detail}")
            print("確認ポイント:")
            print("- Ollamaが起動しているか")
            print("- モデル名が正しいか（例: gemma3）")
            print("- ホストURLが正しいか（例: http://localhost:11434）")
            print("- モデルが未取得なら `ollama pull gemma3` を実行")
            return 1
        except RequestException as exc:
            logging.error("Ollamaへの接続に失敗しました: %s", exc)
            print("確認ポイント:")
            print("- Ollamaが起動しているか")
            print("- モデル名が正しいか（例: gemma3）")
            print("- ホストURLが正しいか（例: http://localhost:11434）")
            return 1

        session.add_assistant(reply)
        print(f"AI> {reply}")


if __name__ == "__main__":
    sys.exit(main())
