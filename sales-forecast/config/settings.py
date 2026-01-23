"""
アプリケーション設定
"""
from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    """アプリケーション設定"""

    # アプリ設定
    APP_NAME: str = "スーパーマーケット売上予測システム"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # データベース
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/sales_forecast.db"

    # モデル設定
    MODEL_PATH: str = "./data/models"

    # 予測設定
    FORECAST_HORIZONS: list = ["daily", "weekly", "monthly"]

    # 階層レベル
    HIERARCHY_LEVELS: list = [
        "company_total",      # 全社トータル
        "store_total",        # 店舗別トータル
        "company_category",   # 全社カテゴリー別
        "store_category",     # 店舗×カテゴリー
        "company_class",      # 全社クラス別
        "store_class",        # 店舗×クラス
    ]

    # 階層整合の重み（上位ほど重要）
    HIERARCHY_WEIGHTS: dict = {
        "company_total": 1.0,
        "store_total": 0.8,
        "company_category": 0.8,
        "store_category": 0.6,
        "company_class": 0.6,
        "store_class": 0.4,
    }

    # 特徴量設定
    LOOKBACK_DAYS: int = 365 * 3  # 過去3年間
    MOVING_AVERAGE_WINDOWS: list = [7, 14, 28]  # 1週間、2週間、4週間

    # 信頼度ランク設定
    CONFIDENCE_RANKS: dict = {
        "A": {"min_accuracy": 0.95, "interval_width": 0.05},
        "B": {"min_accuracy": 0.90, "interval_width": 0.10},
        "C": {"min_accuracy": 0.85, "interval_width": 0.15},
        "D": {"min_accuracy": 0.80, "interval_width": 0.20},
        "E": {"min_accuracy": 0.00, "interval_width": 0.30},
    }

    # 天候API設定（オプション）
    WEATHER_API_KEY: Optional[str] = None
    WEATHER_API_URL: str = "https://api.openweathermap.org/data/2.5"

    class Config:
        env_file = ".env"


settings = Settings()
