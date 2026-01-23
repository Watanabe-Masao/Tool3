"""
データベーススキーマ定義
SQLAlchemy ORMモデル
"""
from sqlalchemy import (
    Column, Integer, String, Float, Date, DateTime, Boolean,
    ForeignKey, UniqueConstraint, Index, Enum as SQLEnum
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

Base = declarative_base()


class Store(Base):
    """店舗マスタ"""
    __tablename__ = "stores"

    store_id = Column(String(10), primary_key=True)
    store_name = Column(String(100), nullable=False)
    area = Column(String(50))  # エリア
    store_type = Column(String(20))  # 店舗タイプ（大型/中型/小型）
    opening_date = Column(Date)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # リレーション
    sales = relationship("Sales", back_populates="store")


class Category(Base):
    """カテゴリーマスタ（階層構造）"""
    __tablename__ = "categories"

    category_id = Column(String(10), primary_key=True)
    category_name = Column(String(100), nullable=False)
    parent_id = Column(String(10), ForeignKey("categories.category_id"), nullable=True)
    level = Column(Integer, nullable=False)  # 1:カテゴリー, 2:クラス, 3:単品
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 自己参照リレーション
    parent = relationship("Category", remote_side=[category_id], backref="children")
    sales = relationship("Sales", back_populates="category")


class Sales(Base):
    """売上実績"""
    __tablename__ = "sales"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sales_date = Column(Date, nullable=False)
    store_id = Column(String(10), ForeignKey("stores.store_id"), nullable=False)
    category_id = Column(String(10), ForeignKey("categories.category_id"), nullable=False)
    sales_amount = Column(Float, nullable=False)  # 売上金額
    sales_quantity = Column(Integer)  # 販売数量
    customer_count = Column(Integer)  # 客数
    created_at = Column(DateTime, default=datetime.utcnow)

    # リレーション
    store = relationship("Store", back_populates="sales")
    category = relationship("Category", back_populates="sales")

    # インデックス
    __table_args__ = (
        UniqueConstraint("sales_date", "store_id", "category_id", name="uix_sales_date_store_category"),
        Index("ix_sales_date", "sales_date"),
        Index("ix_sales_store", "store_id"),
        Index("ix_sales_category", "category_id"),
    )


class Weather(Base):
    """天候データ"""
    __tablename__ = "weather"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False)
    area = Column(String(50), nullable=False)  # エリア
    temperature_max = Column(Float)  # 最高気温
    temperature_min = Column(Float)  # 最低気温
    temperature_avg = Column(Float)  # 平均気温
    precipitation = Column(Float, default=0)  # 降水量(mm)
    humidity = Column(Float)  # 湿度
    is_rain = Column(Boolean, default=False)  # 雨フラグ
    weather_type = Column(String(20))  # 天気タイプ（晴れ/曇り/雨/雪）
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("date", "area", name="uix_weather_date_area"),
        Index("ix_weather_date", "date"),
    )


class EventType(enum.Enum):
    """イベントタイプ"""
    FIXED_DATE = "fixed_date"  # 固定日付（節分、クリスマスなど）
    FLOATING = "floating"  # 曜日依存（ハッピーマンデー等）
    STORE_EVENT = "store_event"  # 店舗イベント
    SEASONAL = "seasonal"  # 季節イベント


class EventCalendar(Base):
    """イベントカレンダー"""
    __tablename__ = "event_calendar"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_date = Column(Date, nullable=False)
    event_name = Column(String(100), nullable=False)
    event_type = Column(String(20), nullable=False)
    # 前後の影響度（-3〜+3日など）
    pre_days_effect = Column(Integer, default=0)  # 前日からの影響
    post_days_effect = Column(Integer, default=0)  # 翌日への影響
    impact_factor = Column(Float, default=1.0)  # 影響度（1.0=標準）
    store_id = Column(String(10), ForeignKey("stores.store_id"), nullable=True)  # NULL=全店舗
    category_id = Column(String(10), ForeignKey("categories.category_id"), nullable=True)  # NULL=全カテゴリ
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_event_date", "event_date"),
    )


class PointPolicy(Base):
    """ポイント政策"""
    __tablename__ = "point_policies"

    policy_id = Column(String(20), primary_key=True)
    policy_name = Column(String(100), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    point_rate = Column(Float, nullable=False)  # ポイント倍率（例: 2.0 = 2倍）
    target_day_of_week = Column(Integer, nullable=True)  # 対象曜日（0=月〜6=日、NULL=毎日）
    store_id = Column(String(10), ForeignKey("stores.store_id"), nullable=True)  # NULL=全店舗
    category_id = Column(String(10), ForeignKey("categories.category_id"), nullable=True)  # NULL=全カテゴリ
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_point_policy_date", "start_date", "end_date"),
    )


class ForecastResult(Base):
    """予測結果"""
    __tablename__ = "forecast_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    forecast_date = Column(Date, nullable=False)  # 予測対象日
    created_date = Column(Date, nullable=False)  # 予測作成日
    horizon = Column(String(20), nullable=False)  # daily/weekly/monthly
    level = Column(String(30), nullable=False)  # 階層レベル
    store_id = Column(String(10), nullable=True)
    category_id = Column(String(10), nullable=True)

    # 予測値
    forecast_value = Column(Float, nullable=False)  # 予測中央値
    forecast_lower = Column(Float)  # 下限値
    forecast_upper = Column(Float)  # 上限値

    # ベース予測と残差予測
    base_forecast = Column(Float)  # 安定成分
    residual_forecast = Column(Float)  # 変動成分

    # 信頼度
    confidence_rank = Column(String(1), nullable=False)  # A〜E
    confidence_score = Column(Float)  # 0〜1

    # 実績（後から更新）
    actual_value = Column(Float, nullable=True)
    forecast_error = Column(Float, nullable=True)  # 予測誤差

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_forecast_date", "forecast_date"),
        Index("ix_forecast_created", "created_date"),
    )


class ModelMetadata(Base):
    """モデルメタデータ"""
    __tablename__ = "model_metadata"

    id = Column(Integer, primary_key=True, autoincrement=True)
    model_name = Column(String(100), nullable=False)
    model_type = Column(String(50), nullable=False)  # base/residual
    level = Column(String(30), nullable=False)  # 階層レベル
    store_id = Column(String(10), nullable=True)
    category_id = Column(String(10), nullable=True)

    # モデル情報
    model_path = Column(String(255), nullable=False)
    feature_names = Column(String(1000))  # JSON形式
    training_start_date = Column(Date)
    training_end_date = Column(Date)

    # 精度指標
    mape = Column(Float)  # Mean Absolute Percentage Error
    rmse = Column(Float)  # Root Mean Square Error
    r2_score = Column(Float)  # R2 Score

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
