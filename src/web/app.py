import os
import logging
from typing import Annotated

from fastapi import FastAPI, Request, Form, Depends
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

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
    chat_session: ChatSession = Depends(get_chat_session),
    ollama_client: OllamaClient = Depends(get_ollama_client)
):
    if not user_input or not user_input.strip():
        return HTMLResponse("")

    chat_session.add_user(user_input)
    
    try:
        reply = ollama_client.chat(chat_session.messages, stream=False)
        chat_session.add_assistant(reply)
    except Exception as e:
        logging.error(f"Error communicating with Ollama: {e}")
        reply = f"エラーが発生しました: {e}"
        chat_session.add_assistant(reply)

    return templates.TemplateResponse(
        "partials/chat_history.html", 
        {"request": request, "messages": chat_session.messages}
    )

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
