# Ollama Chat 🤖✨

Ollama を利用した、美しくモダンなローカル LLM チャットアプリケーションです。
グラスモーフィズムデザインを採用した Web インターフェースと、シンプルな CLI の両方を提供します。

<p align="center">
  <img src="src/web/static/img/logo.svg" width="128" alt="Ollama Chat Logo">
</p>

## ✨ 特徴

- 🎨 **美しく、最高なデザイン**: 最新のグラスモーフィズム（透過ガラス風）デザインを採用。
- ⚡ **高速なレスポンス**: FastAPI と HTMX を組み合わせた、シンプルで強力な Web アプリケーション。
- 🤖 **Ollama 連携**: ローカルで動作する LLM（デフォルト: gemma3）とシームレスに対話。
- 🛠️ **マルチインターフェース**: ブラウザからでも、ターミナル（CLI）からでも利用可能。
- 🔄 **モデル切り替え**: Web 画面上から、利用可能なモデルを動的に変更可能。
- 📱 **レスポンシブ**: デスクトップはもちろん、モバイル端末でも快適に動作。
- **ストリーミング表示**: SSE で応答をリアルタイムに描画し、タイピングアニメーションを表示。

## 🚀 クイックスタート

### 1. 前提条件

- [Ollama](https://ollama.com/) がインストールされ、動作していること。
- 使用するモデル（例: `gemma3`）が `ollama pull` されていること。
- Python 3.10 以上がインストールされていること。

### 2. インストール

```bash
# リポジトリをクローン
git clone https://github.com/Araiseimitsu/ollama_chat.git
cd ollama_chat

# 仮想環境の作成と有効化
python -m venv .venv
.venv\Scripts\activate  # Windows

# 依存関係のインストール
pip install -r requirements.txt
```

### 3. 実行

#### Web インターフェース

```bash
# 開発サーバーの起動
py -3.14 -m uvicorn src.web.app:app --reload
```

起動後、ブラウザで `http://127.0.0.1:8000` にアクセスしてください。

#### CLI インターフェース

```bash
py -3.14 src/cli.py
```

## 📂 プロジェクト構成

```text
ollama_chat/
├── .docs/              # ドキュメント（変更履歴など）
├── src/                # ソースコード
│   ├── core/           # ロジック・クライアント
│   └── web/            # Web インターフェース (FastAPI)
│       ├── static/     # 静的ファイル (CSS, JS, Images)
│       └── templates/  # HTML テンプレート
├── requirements.txt    # 依存ライブラリ
└── README.md           # 本ファイル
```

## 🛠️ 技術スタック

- **Backend**: FastAPI (Python)
- **Frontend**: Tailwind CSS, HTMX, Jinja2
- **Icon**: SVG Custom Design
- **Architecture**: Single Responsibility Principle

## 📝 ライセンス

MIT License

---
Created with ❤️ by Antigravity
