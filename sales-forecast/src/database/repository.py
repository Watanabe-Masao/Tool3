"""
データベースリポジトリ
データアクセス層
"""
from sqlalchemy import create_engine, select, func, and_, or_
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from datetime import date, datetime, timedelta
from typing import Optional, List, Dict, Any
import pandas as pd

from .schemas import (
    Base, Store, Category, Sales, Weather,
    EventCalendar, PointPolicy, ForecastResult, ModelMetadata
)


class DatabaseManager:
    """データベース管理クラス"""

    def __init__(self, database_url: str):
        self.database_url = database_url
        self.engine = create_async_engine(database_url, echo=False)
        self.async_session = sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

    async def create_tables(self):
        """テーブル作成"""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def drop_tables(self):
        """テーブル削除"""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)


class SalesRepository:
    """売上データリポジトリ"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_sales_data(
        self,
        start_date: date,
        end_date: date,
        store_id: Optional[str] = None,
        category_id: Optional[str] = None,
        category_level: Optional[int] = None
    ) -> pd.DataFrame:
        """売上データ取得"""
        query = select(
            Sales.sales_date,
            Sales.store_id,
            Sales.category_id,
            Sales.sales_amount,
            Sales.sales_quantity,
            Sales.customer_count,
            Store.store_name,
            Store.area,
            Category.category_name,
            Category.level.label("category_level"),
            Category.parent_id
        ).join(
            Store, Sales.store_id == Store.store_id
        ).join(
            Category, Sales.category_id == Category.category_id
        ).where(
            and_(
                Sales.sales_date >= start_date,
                Sales.sales_date <= end_date
            )
        )

        if store_id:
            query = query.where(Sales.store_id == store_id)
        if category_id:
            query = query.where(Sales.category_id == category_id)
        if category_level:
            query = query.where(Category.level == category_level)

        result = await self.session.execute(query)
        rows = result.fetchall()

        return pd.DataFrame(rows, columns=[
            "sales_date", "store_id", "category_id", "sales_amount",
            "sales_quantity", "customer_count", "store_name", "area",
            "category_name", "category_level", "parent_id"
        ])

    async def get_aggregated_sales(
        self,
        start_date: date,
        end_date: date,
        group_by: List[str]
    ) -> pd.DataFrame:
        """集計売上データ取得"""
        # 動的にグループ化
        group_columns = []
        select_columns = [func.sum(Sales.sales_amount).label("sales_amount")]

        if "date" in group_by:
            group_columns.append(Sales.sales_date)
            select_columns.insert(0, Sales.sales_date)
        if "store" in group_by:
            group_columns.append(Sales.store_id)
            select_columns.insert(-1, Sales.store_id)
        if "category" in group_by:
            group_columns.append(Sales.category_id)
            select_columns.insert(-1, Sales.category_id)

        query = select(*select_columns).where(
            and_(
                Sales.sales_date >= start_date,
                Sales.sales_date <= end_date
            )
        ).group_by(*group_columns)

        result = await self.session.execute(query)
        rows = result.fetchall()

        columns = [c.key if hasattr(c, 'key') else str(c) for c in select_columns]
        return pd.DataFrame(rows, columns=columns)

    async def get_hierarchical_sales(
        self,
        start_date: date,
        end_date: date
    ) -> Dict[str, pd.DataFrame]:
        """階層別売上データ取得"""
        result = {}

        # 全社トータル
        query_total = select(
            Sales.sales_date,
            func.sum(Sales.sales_amount).label("sales_amount")
        ).where(
            and_(Sales.sales_date >= start_date, Sales.sales_date <= end_date)
        ).group_by(Sales.sales_date)
        res = await self.session.execute(query_total)
        result["company_total"] = pd.DataFrame(
            res.fetchall(), columns=["sales_date", "sales_amount"]
        )

        # 店舗別トータル
        query_store = select(
            Sales.sales_date,
            Sales.store_id,
            func.sum(Sales.sales_amount).label("sales_amount")
        ).where(
            and_(Sales.sales_date >= start_date, Sales.sales_date <= end_date)
        ).group_by(Sales.sales_date, Sales.store_id)
        res = await self.session.execute(query_store)
        result["store_total"] = pd.DataFrame(
            res.fetchall(), columns=["sales_date", "store_id", "sales_amount"]
        )

        # 全社カテゴリー別（level=1）
        query_cat = select(
            Sales.sales_date,
            Sales.category_id,
            func.sum(Sales.sales_amount).label("sales_amount")
        ).join(
            Category, Sales.category_id == Category.category_id
        ).where(
            and_(
                Sales.sales_date >= start_date,
                Sales.sales_date <= end_date,
                Category.level == 1
            )
        ).group_by(Sales.sales_date, Sales.category_id)
        res = await self.session.execute(query_cat)
        result["company_category"] = pd.DataFrame(
            res.fetchall(), columns=["sales_date", "category_id", "sales_amount"]
        )

        # 店舗×カテゴリー
        query_store_cat = select(
            Sales.sales_date,
            Sales.store_id,
            Sales.category_id,
            func.sum(Sales.sales_amount).label("sales_amount")
        ).join(
            Category, Sales.category_id == Category.category_id
        ).where(
            and_(
                Sales.sales_date >= start_date,
                Sales.sales_date <= end_date,
                Category.level == 1
            )
        ).group_by(Sales.sales_date, Sales.store_id, Sales.category_id)
        res = await self.session.execute(query_store_cat)
        result["store_category"] = pd.DataFrame(
            res.fetchall(),
            columns=["sales_date", "store_id", "category_id", "sales_amount"]
        )

        return result


class WeatherRepository:
    """天候データリポジトリ"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_weather_data(
        self,
        start_date: date,
        end_date: date,
        area: Optional[str] = None
    ) -> pd.DataFrame:
        """天候データ取得"""
        query = select(Weather).where(
            and_(
                Weather.date >= start_date,
                Weather.date <= end_date
            )
        )
        if area:
            query = query.where(Weather.area == area)

        result = await self.session.execute(query)
        rows = result.scalars().all()

        return pd.DataFrame([{
            "date": r.date,
            "area": r.area,
            "temperature_max": r.temperature_max,
            "temperature_min": r.temperature_min,
            "temperature_avg": r.temperature_avg,
            "precipitation": r.precipitation,
            "humidity": r.humidity,
            "is_rain": r.is_rain,
            "weather_type": r.weather_type
        } for r in rows])

    async def upsert_weather(self, weather_data: Dict[str, Any]):
        """天候データ更新/挿入"""
        existing = await self.session.execute(
            select(Weather).where(
                and_(
                    Weather.date == weather_data["date"],
                    Weather.area == weather_data["area"]
                )
            )
        )
        weather = existing.scalar_one_or_none()

        if weather:
            for key, value in weather_data.items():
                setattr(weather, key, value)
        else:
            weather = Weather(**weather_data)
            self.session.add(weather)

        await self.session.commit()


class EventRepository:
    """イベントデータリポジトリ"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_events(
        self,
        start_date: date,
        end_date: date,
        store_id: Optional[str] = None
    ) -> pd.DataFrame:
        """イベントデータ取得"""
        query = select(EventCalendar).where(
            and_(
                EventCalendar.event_date >= start_date,
                EventCalendar.event_date <= end_date,
                EventCalendar.is_active == True
            )
        )

        if store_id:
            query = query.where(
                or_(
                    EventCalendar.store_id == store_id,
                    EventCalendar.store_id == None
                )
            )

        result = await self.session.execute(query)
        rows = result.scalars().all()

        return pd.DataFrame([{
            "event_date": r.event_date,
            "event_name": r.event_name,
            "event_type": r.event_type,
            "pre_days_effect": r.pre_days_effect,
            "post_days_effect": r.post_days_effect,
            "impact_factor": r.impact_factor,
            "store_id": r.store_id,
            "category_id": r.category_id
        } for r in rows])


class PointPolicyRepository:
    """ポイント政策リポジトリ"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_active_policies(
        self,
        target_date: date,
        store_id: Optional[str] = None
    ) -> pd.DataFrame:
        """有効なポイント政策取得"""
        query = select(PointPolicy).where(
            and_(
                PointPolicy.start_date <= target_date,
                PointPolicy.end_date >= target_date,
                PointPolicy.is_active == True
            )
        )

        if store_id:
            query = query.where(
                or_(
                    PointPolicy.store_id == store_id,
                    PointPolicy.store_id == None
                )
            )

        result = await self.session.execute(query)
        rows = result.scalars().all()

        return pd.DataFrame([{
            "policy_id": r.policy_id,
            "policy_name": r.policy_name,
            "start_date": r.start_date,
            "end_date": r.end_date,
            "point_rate": r.point_rate,
            "target_day_of_week": r.target_day_of_week,
            "store_id": r.store_id,
            "category_id": r.category_id
        } for r in rows])

    async def get_policies_in_range(
        self,
        start_date: date,
        end_date: date
    ) -> pd.DataFrame:
        """期間内のポイント政策取得"""
        query = select(PointPolicy).where(
            and_(
                PointPolicy.start_date <= end_date,
                PointPolicy.end_date >= start_date,
                PointPolicy.is_active == True
            )
        )

        result = await self.session.execute(query)
        rows = result.scalars().all()

        return pd.DataFrame([{
            "policy_id": r.policy_id,
            "policy_name": r.policy_name,
            "start_date": r.start_date,
            "end_date": r.end_date,
            "point_rate": r.point_rate,
            "target_day_of_week": r.target_day_of_week,
            "store_id": r.store_id,
            "category_id": r.category_id
        } for r in rows])


class ForecastRepository:
    """予測結果リポジトリ"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_forecast(self, forecast_data: Dict[str, Any]):
        """予測結果保存"""
        forecast = ForecastResult(**forecast_data)
        self.session.add(forecast)
        await self.session.commit()
        return forecast

    async def save_forecasts_bulk(self, forecasts: List[Dict[str, Any]]):
        """予測結果一括保存"""
        forecast_objects = [ForecastResult(**f) for f in forecasts]
        self.session.add_all(forecast_objects)
        await self.session.commit()

    async def get_forecasts(
        self,
        forecast_date: date,
        horizon: str,
        level: Optional[str] = None,
        store_id: Optional[str] = None,
        category_id: Optional[str] = None
    ) -> pd.DataFrame:
        """予測結果取得"""
        query = select(ForecastResult).where(
            and_(
                ForecastResult.forecast_date == forecast_date,
                ForecastResult.horizon == horizon
            )
        )

        if level:
            query = query.where(ForecastResult.level == level)
        if store_id:
            query = query.where(ForecastResult.store_id == store_id)
        if category_id:
            query = query.where(ForecastResult.category_id == category_id)

        result = await self.session.execute(query)
        rows = result.scalars().all()

        return pd.DataFrame([{
            "forecast_date": r.forecast_date,
            "created_date": r.created_date,
            "horizon": r.horizon,
            "level": r.level,
            "store_id": r.store_id,
            "category_id": r.category_id,
            "forecast_value": r.forecast_value,
            "forecast_lower": r.forecast_lower,
            "forecast_upper": r.forecast_upper,
            "base_forecast": r.base_forecast,
            "residual_forecast": r.residual_forecast,
            "confidence_rank": r.confidence_rank,
            "confidence_score": r.confidence_score,
            "actual_value": r.actual_value,
            "forecast_error": r.forecast_error
        } for r in rows])

    async def update_actual_value(
        self,
        forecast_date: date,
        level: str,
        store_id: Optional[str],
        category_id: Optional[str],
        actual_value: float
    ):
        """実績値更新"""
        query = select(ForecastResult).where(
            and_(
                ForecastResult.forecast_date == forecast_date,
                ForecastResult.level == level
            )
        )

        if store_id:
            query = query.where(ForecastResult.store_id == store_id)
        else:
            query = query.where(ForecastResult.store_id == None)

        if category_id:
            query = query.where(ForecastResult.category_id == category_id)
        else:
            query = query.where(ForecastResult.category_id == None)

        result = await self.session.execute(query)
        forecast = result.scalar_one_or_none()

        if forecast:
            forecast.actual_value = actual_value
            if forecast.forecast_value:
                forecast.forecast_error = abs(
                    actual_value - forecast.forecast_value
                ) / actual_value if actual_value != 0 else None
            await self.session.commit()
