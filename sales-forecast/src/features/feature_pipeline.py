"""
特徴量パイプライン
全ての特徴量を統合・生成するメインパイプライン
"""
import pandas as pd
import numpy as np
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional, Tuple

from .calendar_features import CalendarFeatureGenerator
from .weather_features import WeatherFeatureGenerator
from .promotion_features import PromotionFeatureGenerator, SeasonalPromotionGenerator


class FeaturePipeline:
    """特徴量生成パイプライン"""

    # 予測に使用する特徴量（安定成分用）
    BASE_FEATURES = [
        # 曜日特徴量
        "day_of_week", "is_weekend", "is_monday", "is_friday",
        "is_saturday", "is_sunday",
        # 周期特徴量
        "dow_sin", "dow_cos", "month_sin", "month_cos",
        "doy_sin", "doy_cos",
        # 月特徴量
        "month", "is_month_start", "is_month_end", "is_payday",
        # 季節特徴量
        "is_spring", "is_summer", "is_autumn", "is_winter",
        # 祝日特徴量
        "is_holiday", "is_holiday_eve", "is_holiday_after",
        "is_golden_week", "is_obon", "is_year_end", "is_new_year",
        "is_long_holiday", "consecutive_holiday_days",
        # イベント特徴量
        "fixed_event_impact", "floating_event_impact", "custom_event_impact",
        # 季節キャンペーン
        "seasonal_impact",
        # ラグ特徴量（同曜日）
        "lag_same_dow_1w", "lag_same_dow_2w", "lag_same_dow_3w", "lag_same_dow_4w",
        "ma_same_dow_4w",
        # 移動平均
        "ma_7d", "ma_14d", "ma_28d",
        "std_7d", "std_14d",
        # 前年比
        "yoy_lag",
    ]

    # 予測に使用する特徴量（変動成分用）
    RESIDUAL_FEATURES = [
        # 天候特徴量
        "temperature_avg", "precipitation", "is_rain", "is_heavy_rain",
        "combined_weather_impact",
        "temp_change_1d", "is_temp_spike",
        "rain_to_clear", "clear_to_rain",
        # 気温帯
        "is_very_cold", "is_cold", "is_hot", "is_very_hot",
        # ポイント政策
        "point_rate", "is_point_up", "point_up_level", "point_impact",
        "is_before_point_up", "is_after_point_up",
        # 直近ラグ
        "lag_1d", "lag_2d", "lag_3d",
        # 前週比
        "wow_ratio",
    ]

    def __init__(self):
        self.calendar_gen = CalendarFeatureGenerator()
        self.weather_gen = WeatherFeatureGenerator()
        self.promotion_gen = PromotionFeatureGenerator()
        self.seasonal_gen = SeasonalPromotionGenerator()

    def generate_features(
        self,
        sales_df: pd.DataFrame,
        weather_df: Optional[pd.DataFrame] = None,
        events_df: Optional[pd.DataFrame] = None,
        policies_df: Optional[pd.DataFrame] = None,
        store_id: Optional[str] = None,
        category_id: Optional[str] = None,
        include_target: bool = True
    ) -> pd.DataFrame:
        """
        全特徴量を生成

        Args:
            sales_df: 売上データフレーム
            weather_df: 天候データフレーム
            events_df: イベントデータフレーム
            policies_df: ポイント政策データフレーム
            store_id: 店舗ID
            category_id: カテゴリID
            include_target: 目的変数を含めるか

        Returns:
            特徴量データフレーム
        """
        # 日付リストを取得
        dates = sorted(sales_df["sales_date"].unique())

        # 1. カレンダー特徴量
        calendar_features = self.calendar_gen.generate_features(
            dates,
            events_df if events_df is not None else pd.DataFrame()
        )

        # 2. ラグ特徴量を売上データに追加
        if include_target:
            sales_with_lag = self.calendar_gen.generate_lag_features(
                sales_df,
                target_col="sales_amount"
            )
        else:
            sales_with_lag = sales_df.copy()

        # 3. 天候特徴量
        if weather_df is not None and not weather_df.empty:
            weather_df["date"] = pd.to_datetime(weather_df["date"]).dt.date
            weather_features = self.weather_gen.generate_features(
                weather_df,
                dates
            )
        else:
            weather_features = self.weather_gen._generate_default_features(dates)

        # 4. プロモーション特徴量
        if policies_df is not None and not policies_df.empty:
            promotion_features = self.promotion_gen.generate_features(
                dates,
                policies_df,
                store_id,
                category_id
            )
            promotion_features = self.promotion_gen.add_promotion_lag_features(
                promotion_features
            )
        else:
            promotion_features = pd.DataFrame({
                "date": dates,
                "point_rate": 1.0,
                "is_point_up": 0,
                "point_up_level": 0,
                "point_impact": 1.0,
            })

        # 5. 季節キャンペーン特徴量
        seasonal_features = self.seasonal_gen.generate_seasonal_features(dates)

        # 6. 全特徴量をマージ
        # 売上データをベースに
        result = sales_with_lag.copy()
        result["date"] = pd.to_datetime(result["sales_date"]).dt.date

        # カレンダー特徴量をマージ
        calendar_features["date"] = pd.to_datetime(calendar_features["date"]).dt.date
        result = result.merge(
            calendar_features,
            on="date",
            how="left"
        )

        # 天候特徴量をマージ
        if not weather_features.empty:
            weather_features["date"] = pd.to_datetime(weather_features["date"]).dt.date
            result = result.merge(
                weather_features,
                on="date",
                how="left"
            )

        # プロモーション特徴量をマージ
        promotion_features["date"] = pd.to_datetime(promotion_features["date"]).dt.date
        result = result.merge(
            promotion_features,
            on="date",
            how="left"
        )

        # 季節キャンペーン特徴量をマージ
        seasonal_features["date"] = pd.to_datetime(seasonal_features["date"]).dt.date
        result = result.merge(
            seasonal_features,
            on="date",
            how="left"
        )

        # 欠損値処理
        result = self._handle_missing_values(result)

        return result

    def generate_forecast_features(
        self,
        target_dates: List[date],
        historical_sales_df: pd.DataFrame,
        weather_forecast_df: Optional[pd.DataFrame] = None,
        events_df: Optional[pd.DataFrame] = None,
        policies_df: Optional[pd.DataFrame] = None,
        store_id: Optional[str] = None,
        category_id: Optional[str] = None
    ) -> pd.DataFrame:
        """
        予測用特徴量を生成（未来日付）

        Args:
            target_dates: 予測対象日付リスト
            historical_sales_df: 過去の売上データ
            weather_forecast_df: 天気予報データ
            events_df: イベントデータ
            policies_df: ポイント政策データ
            store_id: 店舗ID
            category_id: カテゴリID

        Returns:
            予測用特徴量データフレーム
        """
        # 1. カレンダー特徴量（未来日付）
        calendar_features = self.calendar_gen.generate_features(
            target_dates,
            events_df if events_df is not None else pd.DataFrame()
        )

        # 2. 過去データからラグ特徴量を計算
        lag_features = self._calculate_forecast_lags(
            target_dates,
            historical_sales_df
        )

        # 3. 天候予報特徴量
        if weather_forecast_df is not None and not weather_forecast_df.empty:
            weather_forecast_df["date"] = pd.to_datetime(
                weather_forecast_df["date"]
            ).dt.date
            weather_features = self.weather_gen.generate_features(
                weather_forecast_df,
                target_dates
            )
        else:
            weather_features = self.weather_gen._generate_default_features(target_dates)

        # 4. プロモーション特徴量
        if policies_df is not None and not policies_df.empty:
            promotion_features = self.promotion_gen.generate_features(
                target_dates,
                policies_df,
                store_id,
                category_id
            )
        else:
            promotion_features = pd.DataFrame({
                "date": target_dates,
                "point_rate": 1.0,
                "is_point_up": 0,
                "point_up_level": 0,
                "point_impact": 1.0,
            })

        # 5. 季節キャンペーン特徴量
        seasonal_features = self.seasonal_gen.generate_seasonal_features(target_dates)

        # 6. マージ
        result = pd.DataFrame({"date": target_dates})
        result["date"] = pd.to_datetime(result["date"]).dt.date

        for df in [calendar_features, lag_features, weather_features,
                   promotion_features, seasonal_features]:
            if df is not None and not df.empty:
                df["date"] = pd.to_datetime(df["date"]).dt.date
                result = result.merge(df, on="date", how="left")

        # 欠損値処理
        result = self._handle_missing_values(result)

        return result

    def _calculate_forecast_lags(
        self,
        target_dates: List[date],
        historical_df: pd.DataFrame
    ) -> pd.DataFrame:
        """予測用ラグ特徴量を計算"""
        historical_df = historical_df.copy()
        historical_df["sales_date"] = pd.to_datetime(historical_df["sales_date"]).dt.date

        lag_features = []

        for target_date in target_dates:
            feat = {"date": target_date}

            # 同曜日ラグ
            for weeks in [1, 2, 3, 4]:
                lag_date = target_date - timedelta(days=weeks * 7)
                lag_value = historical_df[
                    historical_df["sales_date"] == lag_date
                ]["sales_amount"].values
                feat[f"lag_same_dow_{weeks}w"] = lag_value[0] if len(lag_value) > 0 else np.nan

            # 直近ラグ
            for lag in range(1, 8):
                lag_date = target_date - timedelta(days=lag)
                lag_value = historical_df[
                    historical_df["sales_date"] == lag_date
                ]["sales_amount"].values
                feat[f"lag_{lag}d"] = lag_value[0] if len(lag_value) > 0 else np.nan

            # 移動平均
            for window in [7, 14, 28]:
                start_date = target_date - timedelta(days=window)
                end_date = target_date - timedelta(days=1)
                window_data = historical_df[
                    (historical_df["sales_date"] >= start_date) &
                    (historical_df["sales_date"] <= end_date)
                ]["sales_amount"]
                feat[f"ma_{window}d"] = window_data.mean() if len(window_data) > 0 else np.nan
                if window in [7, 14]:
                    feat[f"std_{window}d"] = window_data.std() if len(window_data) > 0 else np.nan

            # 同曜日移動平均
            feat["ma_same_dow_4w"] = np.nanmean([
                feat.get(f"lag_same_dow_{w}w", np.nan) for w in [1, 2, 3, 4]
            ])

            # 前年同週ラグ
            yoy_date = target_date - timedelta(days=364)
            yoy_value = historical_df[
                historical_df["sales_date"] == yoy_date
            ]["sales_amount"].values
            feat["yoy_lag"] = yoy_value[0] if len(yoy_value) > 0 else np.nan

            lag_features.append(feat)

        return pd.DataFrame(lag_features)

    def _handle_missing_values(self, df: pd.DataFrame) -> pd.DataFrame:
        """欠損値処理"""
        # 数値カラムは0で埋める
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        df[numeric_cols] = df[numeric_cols].fillna(0)

        # 文字列カラムは空文字で埋める
        string_cols = df.select_dtypes(include=["object"]).columns
        df[string_cols] = df[string_cols].fillna("")

        return df

    def get_feature_names(
        self,
        feature_type: str = "all"
    ) -> List[str]:
        """
        特徴量名リストを取得

        Args:
            feature_type: "base", "residual", or "all"

        Returns:
            特徴量名リスト
        """
        if feature_type == "base":
            return self.BASE_FEATURES
        elif feature_type == "residual":
            return self.RESIDUAL_FEATURES
        else:
            return list(set(self.BASE_FEATURES + self.RESIDUAL_FEATURES))

    def select_features(
        self,
        df: pd.DataFrame,
        feature_type: str = "all"
    ) -> pd.DataFrame:
        """
        特徴量を選択

        Args:
            df: 特徴量データフレーム
            feature_type: "base", "residual", or "all"

        Returns:
            選択された特徴量のみのデータフレーム
        """
        feature_names = self.get_feature_names(feature_type)
        available_features = [f for f in feature_names if f in df.columns]
        return df[available_features]
