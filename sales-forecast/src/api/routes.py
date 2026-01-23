"""
API ルート定義
"""
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field
from datetime import date, datetime
from typing import List, Optional, Dict, Any
from enum import Enum

router = APIRouter(prefix="/api/v1", tags=["forecast"])


# ==============================
# Enums
# ==============================

class HorizonType(str, Enum):
    """予測期間"""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class LevelType(str, Enum):
    """階層レベル"""
    COMPANY = "company_total"
    STORE = "store_total"
    CATEGORY = "company_category"
    STORE_CATEGORY = "store_category"


class ConfidenceRank(str, Enum):
    """信頼度ランク"""
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"


# ==============================
# Request/Response Models
# ==============================

class ForecastRequest(BaseModel):
    """予測リクエスト"""
    target_date: date = Field(..., description="予測対象日")
    horizon: HorizonType = Field(HorizonType.DAILY, description="予測期間")
    level: Optional[LevelType] = Field(None, description="階層レベル")
    store_id: Optional[str] = Field(None, description="店舗ID")
    category_id: Optional[str] = Field(None, description="カテゴリID")


class ForecastItem(BaseModel):
    """予測結果アイテム"""
    forecast_date: date
    level: str
    store_id: Optional[str] = None
    category_id: Optional[str] = None
    horizon: str
    forecast_value: float = Field(..., description="予測中央値")
    forecast_lower: float = Field(..., description="予測下限値")
    forecast_upper: float = Field(..., description="予測上限値")
    base_forecast: float = Field(..., description="ベース予測値（安定成分）")
    residual_forecast: float = Field(..., description="残差予測値（変動成分）")
    confidence_rank: str = Field(..., description="信頼度ランク（A〜E）")
    confidence_score: float = Field(..., description="信頼度スコア（0〜1）")


class ForecastResponse(BaseModel):
    """予測レスポンス"""
    status: str = "success"
    request_id: str
    created_at: datetime
    forecasts: List[ForecastItem]
    summary: Dict[str, Any]


class HierarchySummary(BaseModel):
    """階層サマリー"""
    level: str
    total_forecast: float
    count: int
    avg_confidence_score: float
    confidence_distribution: Dict[str, int]


class AccuracyMetrics(BaseModel):
    """精度メトリクス"""
    mape: float = Field(..., description="Mean Absolute Percentage Error")
    mae: float = Field(..., description="Mean Absolute Error")
    rmse: float = Field(..., description="Root Mean Square Error")
    bias: float = Field(..., description="予測バイアス")
    n_samples: int


class AccuracyResponse(BaseModel):
    """精度レスポンス"""
    status: str = "success"
    period: Dict[str, date]
    overall: AccuracyMetrics
    by_level: Dict[str, AccuracyMetrics]
    by_confidence_rank: Dict[str, AccuracyMetrics]


class ModelStatusResponse(BaseModel):
    """モデルステータス"""
    status: str = "success"
    models: Dict[str, Dict[str, Any]]
    last_training: Optional[datetime]
    last_forecast: Optional[datetime]


# ==============================
# Endpoints
# ==============================

@router.get("/forecast", response_model=ForecastResponse)
async def get_forecast(
    target_date: date = Query(..., description="予測対象日"),
    horizon: HorizonType = Query(HorizonType.DAILY, description="予測期間"),
    level: Optional[LevelType] = Query(None, description="階層レベル"),
    store_id: Optional[str] = Query(None, description="店舗ID"),
    category_id: Optional[str] = Query(None, description="カテゴリID")
):
    """
    売上予測を取得

    ## パラメータ
    - **target_date**: 予測対象日（必須）
    - **horizon**: 予測期間（daily/weekly/monthly）
    - **level**: 階層レベル（company_total/store_total/company_category/store_category）
    - **store_id**: 店舗ID（任意）
    - **category_id**: カテゴリID（任意）

    ## レスポンス
    - 予測中央値、上限・下限
    - ベース予測（安定成分）と残差予測（変動成分）
    - 信頼度ランク（A〜E）とスコア
    """
    import uuid

    # サンプルレスポンス（実際の実装では予測エンジンを使用）
    sample_forecasts = [
        ForecastItem(
            forecast_date=target_date,
            level="company_total",
            horizon=horizon.value,
            forecast_value=10000000,
            forecast_lower=9500000,
            forecast_upper=10500000,
            base_forecast=9800000,
            residual_forecast=200000,
            confidence_rank="A",
            confidence_score=0.92
        )
    ]

    if store_id:
        sample_forecasts.append(ForecastItem(
            forecast_date=target_date,
            level="store_total",
            store_id=store_id,
            horizon=horizon.value,
            forecast_value=500000,
            forecast_lower=450000,
            forecast_upper=550000,
            base_forecast=480000,
            residual_forecast=20000,
            confidence_rank="B",
            confidence_score=0.85
        ))

    return ForecastResponse(
        status="success",
        request_id=str(uuid.uuid4()),
        created_at=datetime.now(),
        forecasts=sample_forecasts,
        summary={
            "total_forecast": sum(f.forecast_value for f in sample_forecasts),
            "forecast_count": len(sample_forecasts),
            "confidence_distribution": {"A": 1, "B": 1}
        }
    )


@router.post("/forecast", response_model=ForecastResponse)
async def create_forecast(request: ForecastRequest):
    """
    売上予測を作成（POSTリクエスト）

    複数の条件を指定して予測を取得する場合に使用
    """
    return await get_forecast(
        target_date=request.target_date,
        horizon=request.horizon,
        level=request.level,
        store_id=request.store_id,
        category_id=request.category_id
    )


@router.get("/forecast/hierarchy", response_model=List[HierarchySummary])
async def get_hierarchy_forecast(
    target_date: date = Query(..., description="予測対象日"),
    horizon: HorizonType = Query(HorizonType.DAILY, description="予測期間")
):
    """
    階層別予測サマリーを取得

    全階層の予測概要と信頼度分布を返す
    """
    # サンプルレスポンス
    return [
        HierarchySummary(
            level="company_total",
            total_forecast=10000000,
            count=1,
            avg_confidence_score=0.92,
            confidence_distribution={"A": 1}
        ),
        HierarchySummary(
            level="store_total",
            total_forecast=10000000,
            count=10,
            avg_confidence_score=0.85,
            confidence_distribution={"A": 3, "B": 5, "C": 2}
        ),
        HierarchySummary(
            level="company_category",
            total_forecast=10000000,
            count=5,
            avg_confidence_score=0.82,
            confidence_distribution={"A": 2, "B": 2, "C": 1}
        ),
        HierarchySummary(
            level="store_category",
            total_forecast=10000000,
            count=50,
            avg_confidence_score=0.75,
            confidence_distribution={"A": 10, "B": 20, "C": 15, "D": 5}
        )
    ]


@router.get("/accuracy", response_model=AccuracyResponse)
async def get_accuracy(
    start_date: date = Query(..., description="評価開始日"),
    end_date: date = Query(..., description="評価終了日"),
    level: Optional[LevelType] = Query(None, description="階層レベル")
):
    """
    予測精度を取得

    指定期間の予測精度（MAPE、MAE、RMSE等）を返す
    """
    return AccuracyResponse(
        status="success",
        period={"start": start_date, "end": end_date},
        overall=AccuracyMetrics(
            mape=0.05,
            mae=50000,
            rmse=70000,
            bias=-5000,
            n_samples=100
        ),
        by_level={
            "company_total": AccuracyMetrics(
                mape=0.03, mae=30000, rmse=40000, bias=-2000, n_samples=10
            ),
            "store_total": AccuracyMetrics(
                mape=0.06, mae=20000, rmse=25000, bias=-1000, n_samples=50
            ),
        },
        by_confidence_rank={
            "A": AccuracyMetrics(
                mape=0.02, mae=15000, rmse=20000, bias=-500, n_samples=30
            ),
            "B": AccuracyMetrics(
                mape=0.05, mae=35000, rmse=45000, bias=-2000, n_samples=40
            ),
        }
    )


@router.get("/model/status", response_model=ModelStatusResponse)
async def get_model_status():
    """
    モデルステータスを取得

    各階層のモデル情報と最終学習日時を返す
    """
    return ModelStatusResponse(
        status="success",
        models={
            "company_total": {
                "base_model": {
                    "type": "LightGBM",
                    "n_features": 35,
                    "cv_mape": 0.032
                },
                "residual_model": {
                    "type": "LightGBM",
                    "n_features": 18,
                    "cv_mae": 25000
                }
            },
            "store_total": {
                "base_model": {
                    "type": "LightGBM",
                    "n_features": 35,
                    "cv_mape": 0.055
                },
                "residual_model": {
                    "type": "LightGBM",
                    "n_features": 18,
                    "cv_mae": 15000
                }
            }
        },
        last_training=datetime(2024, 1, 15, 3, 0, 0),
        last_forecast=datetime.now()
    )


@router.post("/model/retrain")
async def retrain_models(
    start_date: date = Query(..., description="学習データ開始日"),
    end_date: date = Query(..., description="学習データ終了日"),
    levels: Optional[List[LevelType]] = Query(None, description="再学習する階層")
):
    """
    モデルを再学習

    指定期間のデータでモデルを再学習する
    """
    return {
        "status": "accepted",
        "message": "Model retraining job submitted",
        "job_id": "retrain-20240120-001",
        "parameters": {
            "start_date": start_date,
            "end_date": end_date,
            "levels": levels or ["all"]
        }
    }


@router.get("/stores")
async def get_stores():
    """店舗一覧を取得"""
    return {
        "stores": [
            {"store_id": "S001", "store_name": "店舗A", "area": "東京"},
            {"store_id": "S002", "store_name": "店舗B", "area": "神奈川"},
            {"store_id": "S003", "store_name": "店舗C", "area": "千葉"},
        ]
    }


@router.get("/categories")
async def get_categories():
    """カテゴリ一覧を取得"""
    return {
        "categories": [
            {"category_id": "C01", "category_name": "青果", "level": 1},
            {"category_id": "C02", "category_name": "鮮魚", "level": 1},
            {"category_id": "C03", "category_name": "精肉", "level": 1},
            {"category_id": "C04", "category_name": "惣菜", "level": 1},
            {"category_id": "C05", "category_name": "日配", "level": 1},
        ]
    }


@router.get("/health")
async def health_check():
    """ヘルスチェック"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }
