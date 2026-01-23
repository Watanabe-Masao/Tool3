"""
スーパーマーケット売上予測API
メインアプリケーション
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import os

from .api.routes import router as api_router

# アプリケーション作成
app = FastAPI(
    title="スーパーマーケット売上予測API",
    description="""
## 概要
スーパーマーケット部門の売上を階層整合させながら予測するAPIです。

## 特徴
- **2段階予測モデル**: ベース予測（安定成分）+ 残差予測（変動成分）
- **階層整合**: 全社 → 店舗 → カテゴリの階層で整合性を保証
- **信頼度評価**: A〜Eランクで予測精度を評価

## 階層構造
1. 全社トータル（最も信頼度が高い）
2. 店舗別トータル & 全社カテゴリー別
3. 店舗×カテゴリー & 全社クラス別

## 設計思想
- 大きな数字を信頼する
- 小さな数字は補正する
- 当てに行かず、外さない
    """,
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# APIルーター登録
app.include_router(api_router)

# 静的ファイル（フロントエンド）
frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")


@app.get("/", response_class=HTMLResponse)
async def root():
    """ルートページ（ダッシュボードへリダイレクト）"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <meta http-equiv="refresh" content="0; url=/static/index.html">
        <title>売上予測システム</title>
    </head>
    <body>
        <p>リダイレクト中... <a href="/static/index.html">ダッシュボード</a></p>
    </body>
    </html>
    """


@app.on_event("startup")
async def startup_event():
    """アプリケーション起動時の処理"""
    print("=" * 50)
    print("スーパーマーケット売上予測システム 起動")
    print("=" * 50)
    print("API ドキュメント: /api/docs")
    print("ダッシュボード: /static/index.html")
    print("=" * 50)


@app.on_event("shutdown")
async def shutdown_event():
    """アプリケーション終了時の処理"""
    print("アプリケーションを終了します...")


# 開発用起動スクリプト
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
