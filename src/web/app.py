import os
import logging
import json
import base64
from typing import Annotated, List, Optional, Dict

from fastapi import FastAPI, Request, Form, Depends, UploadFile, File
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, StreamingResponse

from src.core.ollama_client import OllamaClient
from src.core.chat_session import ChatSession

app = FastAPI(title="Ollama Chat UI")

# 静的ファイルのマウント
app.mount("/static", StaticFiles(directory="src/web/static"), name="static")

# テンプレートエンジンの設定
templates = Jinja2Templates(directory="src/web/templates")

# グローバルセッション（簡易実装）
session_store = {
    "chat_session": ChatSession(),
    "ollama_client": OllamaClient(
        host=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
        model=os.getenv("OLLAMA_MODEL", "gemma3")
    )
}

def get_chat_session():
    return session_store["chat_session"]

def get_ollama_client():
    return session_store["ollama_client"]

async def encode_images(files: Optional[List[UploadFile]]) -> List[Dict[str, str]]:
    if not files:
        return []

    encoded_images: List[Dict[str, str]] = []
    for upload in files:
        # ファイル名がない、または空のファイルはスキップ（フォームで画像を選択していない場合）
        if not upload.filename:
            continue

        if not upload.content_type or not upload.content_type.startswith("image/"):
            raise ValueError("画像ファイルのみ送信できます。")

        data = await upload.read()
        if not data:
            continue

        encoded_images.append({
            "data": base64.b64encode(data).decode("ascii"),
            "mime": upload.content_type
        })

    return encoded_images

@app.get("/", response_class=HTMLResponse)
async def read_root(
    request: Request,
    ollama_client: OllamaClient = Depends(get_ollama_client)
):
    models = ollama_client.list_models()

    # モデル一覧が取得できた場合
    if models:
        # 現在設定されているモデルが一覧にない場合（デフォルトのgemma3など）
        # 最初のモデルを自動選択する
        if ollama_client.model not in models:
            ollama_client.model = models[0]
            logging.info(f"Default model auto-switched to: {ollama_client.model}")
    else:
        # 一覧が取れなかった場合は現在の設定を維持して表示だけする
        models = [ollama_client.model]

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "messages": [],
            "current_model": ollama_client.model,
            "models": models
        }
    )

@app.post("/chat", response_class=HTMLResponse)
async def chat(
    request: Request,
    user_input: Annotated[str, Form()] = "",
    images: Annotated[Optional[List[UploadFile]], File()] = None,
    chat_session: ChatSession = Depends(get_chat_session),
    ollama_client: OllamaClient = Depends(get_ollama_client)
):
    try:
        image_payloads = await encode_images(images)
    except ValueError as exc:
        reply = f"エラー: {exc}"
        chat_session.add_assistant(reply)
        return templates.TemplateResponse(
            "partials/chat_history.html",
            {"request": request, "messages": chat_session.messages}
        )
    if not user_input or not user_input.strip():
        if not image_payloads:
            return HTMLResponse("")
        user_input = ""

    if image_payloads:
        supports_images = ollama_client.supports_images()
        if supports_images is False:
            reply = f"エラー: 現在のモデル「{ollama_client.model}」は画像入力に対応していません。"
            chat_session.add_assistant(reply)
            return templates.TemplateResponse(
                "partials/chat_history.html",
                {"request": request, "messages": chat_session.messages}
            )

    chat_session.add_user(user_input, images=image_payloads if image_payloads else None)

    try:
        # 現在のモデルが画像をサポートするかどうかを確認
        supports_images = ollama_client.supports_images()
        # Ollama API を使用（thinking自動抽出）
        thinking, reply = ollama_client.chat(
            chat_session.ollama_messages(supports_images=supports_images if supports_images is not None else True),
            stream=False
        )
        chat_session.add_assistant(reply, thinking=thinking)

        if thinking:
            logging.debug(f"Thinking extracted - thinking: {len(thinking)} chars, reply: {len(reply)} chars")
        else:
            logging.debug(f"No thinking - reply: {len(reply)} chars")

    except Exception as e:
        logging.error(f"Error communicating with Ollama: {e}")
        reply = f"エラーが発生しました: {e}"
        chat_session.add_assistant(reply)

    return templates.TemplateResponse(
        "partials/chat_history.html",
        {"request": request, "messages": chat_session.messages}
    )

@app.post("/chat/stream")
async def chat_stream(
    request: Request,
    user_input: Annotated[str, Form()] = "",
    images: Annotated[Optional[List[UploadFile]], File()] = None,
    chat_session: ChatSession = Depends(get_chat_session),
    ollama_client: OllamaClient = Depends(get_ollama_client)
):
    """ストリーミングチャットエンドポイント（SSE形式）"""
    try:
        image_payloads = await encode_images(images)
    except ValueError as exc:
        error_message = f"エラー: {exc}"

        async def error_generator():
            error_event = json.dumps({
                "type": "error",
                "content": error_message
            }, ensure_ascii=False)
            yield f"data: {error_event}\n\n"

        return StreamingResponse(error_generator(), media_type="text/event-stream")
    if not user_input or not user_input.strip():
        if not image_payloads:
            return StreamingResponse(iter([]), media_type="text/event-stream")
        user_input = ""

    if image_payloads:
        supports_images = ollama_client.supports_images()
        if supports_images is False:
            async def error_generator():
                error_event = json.dumps({
                    "type": "error",
                    "content": f"エラー: 現在のモデル「{ollama_client.model}」は画像入力に対応していません。"
                }, ensure_ascii=False)
                yield f"data: {error_event}\n\n"

            return StreamingResponse(error_generator(), media_type="text/event-stream")

    chat_session.add_user(user_input, images=image_payloads if image_payloads else None)

    async def event_generator():
        try:
            thinking_buffer = []
            response_buffer = []
            disconnected = False
            # 現在のモデルが画像をサポートするかどうかを確認
            supports_images = ollama_client.supports_images()

            for chunk in ollama_client.chat_stream(
                chat_session.ollama_messages(supports_images=supports_images if supports_images is not None else True),
                should_stop=lambda: disconnected
            ):
                if await request.is_disconnected():
                    disconnected = True
                    logging.info("Client disconnected. Stopping streaming.")
                    break

                chunk_type = chunk.get("type")
                content = chunk.get("content", "")

                if chunk_type == "thinking":
                    thinking_buffer.append(content)
                elif chunk_type == "response":
                    response_buffer.append(content)

                # SSE形式でデータを送信
                event_data = json.dumps(chunk, ensure_ascii=False)
                yield f"data: {event_data}\n\n"

            if disconnected:
                return

            # ストリーミング完了後、セッションに保存
            thinking_text = "".join(thinking_buffer) if thinking_buffer else None
            response_text = "".join(response_buffer)

            chat_session.add_assistant(response_text, thinking=thinking_text)

            # 完了イベントを送信
            yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"

            logging.debug(f"Streaming completed - thinking: {len(thinking_text) if thinking_text else 0} chars, response: {len(response_text)} chars")

        except Exception as e:
            logging.error(f"Error during streaming: {e}")
            error_event = json.dumps({
                "type": "error",
                "content": f"エラーが発生しました: {str(e)}"
            }, ensure_ascii=False)
            yield f"data: {error_event}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/set_model", response_class=HTMLResponse)
async def set_model(
    request: Request,
    model_name: Annotated[str, Form()]
):
    """モデルを変更する"""
    client = session_store["ollama_client"]
    client.set_model(model_name)
    logging.info(f"Model changed to {model_name}")

    # モデル変更時はチャット履歴をリセットするか、継続するか選べるが、
    # 混乱を避けるため今回は継続する（会話コンテキストが新しいモデルに渡される）

    return HTMLResponse(model_name)

@app.get("/reset", response_class=HTMLResponse)
async def reset_chat(request: Request):
    session_store["chat_session"] = ChatSession()
    return templates.TemplateResponse(
        "partials/chat_history.html", 
        {"request": request, "messages": []}
    )
