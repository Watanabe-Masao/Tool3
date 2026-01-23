"""
天候特徴量生成
気温、降水量、天気タイプなどの天候関連特徴量
"""
import pandas as pd
import numpy as np
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional
import httpx
import asyncio


class WeatherFeatureGenerator:
    """天候特徴量生成クラス"""

    # 天気タイプの売上影響度（基準値）
    WEATHER_IMPACT = {
        "sunny": 1.0,
        "cloudy": 0.98,
        "rain": 0.90,
        "heavy_rain": 0.80,
        "snow": 0.85,
        "typhoon": 0.60,
    }

    # 気温帯の定義
    TEMPERATURE_BANDS = {
        "very_cold": (-np.inf, 5),   # 極寒
        "cold": (5, 10),             # 寒い
        "cool": (10, 15),            # 涼しい
        "comfortable": (15, 25),      # 快適
        "warm": (25, 30),            # 暖かい
        "hot": (30, 35),             # 暑い
        "very_hot": (35, np.inf),    # 猛暑
    }

    def __init__(self, api_key: Optional[str] = None, api_url: Optional[str] = None):
        """
        Args:
            api_key: 天気API キー（OpenWeatherMap等）
            api_url: 天気API URL
        """
        self.api_key = api_key
        self.api_url = api_url

    def generate_features(
        self,
        weather_df: pd.DataFrame,
        dates: Optional[List[date]] = None
    ) -> pd.DataFrame:
        """
        天候特徴量を生成

        Args:
            weather_df: 天候データフレーム
            dates: 対象日付リスト（オプション）

        Returns:
            特徴量データフレーム
        """
        if weather_df.empty:
            return self._generate_default_features(dates)

        df = weather_df.copy()

        # 基本特徴量
        df = self._add_basic_features(df)

        # 気温帯特徴量
        df = self._add_temperature_band_features(df)

        # 天候影響度
        df = self._add_weather_impact_features(df)

        # ラグ特徴量
        df = self._add_lag_features(df)

        # 変化量特徴量
        df = self._add_change_features(df)

        if dates:
            df = df[df["date"].isin(dates)]

        return df

    def _add_basic_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """基本天候特徴量"""
        # 雨フラグがない場合は降水量から判定
        if "is_rain" not in df.columns:
            df["is_rain"] = (df["precipitation"] > 0).astype(int)

        # 大雨フラグ
        df["is_heavy_rain"] = (df["precipitation"] > 10).astype(int)

        # 降水量カテゴリ
        df["precipitation_category"] = pd.cut(
            df["precipitation"],
            bins=[-np.inf, 0, 5, 10, 30, np.inf],
            labels=["none", "light", "moderate", "heavy", "very_heavy"]
        )

        # 気温差
        if "temperature_max" in df.columns and "temperature_min" in df.columns:
            df["temperature_range"] = df["temperature_max"] - df["temperature_min"]

        # 平均気温（なければ計算）
        if "temperature_avg" not in df.columns:
            if "temperature_max" in df.columns and "temperature_min" in df.columns:
                df["temperature_avg"] = (
                    df["temperature_max"] + df["temperature_min"]
                ) / 2

        return df

    def _add_temperature_band_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """気温帯特徴量"""
        temp_col = "temperature_avg"
        if temp_col not in df.columns:
            return df

        # 気温帯判定
        def get_temp_band(temp):
            for band_name, (low, high) in self.TEMPERATURE_BANDS.items():
                if low <= temp < high:
                    return band_name
            return "comfortable"

        df["temperature_band"] = df[temp_col].apply(get_temp_band)

        # 各気温帯のフラグ
        for band_name in self.TEMPERATURE_BANDS.keys():
            df[f"is_{band_name}"] = (df["temperature_band"] == band_name).astype(int)

        # 季節に対する異常気温
        # （簡易的に月ごとの平均気温との差を計算）
        monthly_avg = df.groupby(df["date"].dt.month)[temp_col].transform("mean")
        df["temp_anomaly"] = df[temp_col] - monthly_avg

        return df

    def _add_weather_impact_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """天候影響度特徴量"""
        # 天気タイプから影響度を計算
        if "weather_type" in df.columns:
            df["weather_impact"] = df["weather_type"].map(
                self.WEATHER_IMPACT
            ).fillna(1.0)
        else:
            # 降水量ベースで推定
            def estimate_impact(row):
                if row.get("precipitation", 0) > 30:
                    return 0.75
                elif row.get("precipitation", 0) > 10:
                    return 0.85
                elif row.get("precipitation", 0) > 0:
                    return 0.92
                return 1.0

            df["weather_impact"] = df.apply(estimate_impact, axis=1)

        # 気温による影響度調整
        if "temperature_avg" in df.columns:
            # 極端な気温は来店を減らす
            def temp_impact(temp):
                if temp < 0 or temp > 35:
                    return 0.90
                elif temp < 5 or temp > 32:
                    return 0.95
                return 1.0

            df["temp_impact"] = df["temperature_avg"].apply(temp_impact)
            df["combined_weather_impact"] = df["weather_impact"] * df["temp_impact"]
        else:
            df["combined_weather_impact"] = df["weather_impact"]

        return df

    def _add_lag_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """天候ラグ特徴量"""
        df = df.sort_values("date")

        # 気温のラグ
        if "temperature_avg" in df.columns:
            for lag in [1, 2, 3, 7]:
                df[f"temp_lag_{lag}d"] = df["temperature_avg"].shift(lag)

            # 気温の移動平均
            df["temp_ma_3d"] = df["temperature_avg"].shift(1).rolling(
                window=3, min_periods=1
            ).mean()
            df["temp_ma_7d"] = df["temperature_avg"].shift(1).rolling(
                window=7, min_periods=1
            ).mean()

        # 降水量のラグ
        if "precipitation" in df.columns:
            for lag in [1, 2, 3]:
                df[f"precip_lag_{lag}d"] = df["precipitation"].shift(lag)

            # 過去1週間の累積降水量
            df["precip_sum_7d"] = df["precipitation"].shift(1).rolling(
                window=7, min_periods=1
            ).sum()

        return df

    def _add_change_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """天候変化特徴量"""
        df = df.sort_values("date")

        if "temperature_avg" in df.columns:
            # 前日比
            df["temp_change_1d"] = df["temperature_avg"] - df["temperature_avg"].shift(1)

            # 急激な気温変化フラグ
            df["is_temp_spike"] = (abs(df["temp_change_1d"]) > 5).astype(int)

            # 前週同曜日比
            df["temp_change_7d"] = df["temperature_avg"] - df["temperature_avg"].shift(7)

        if "precipitation" in df.columns:
            # 雨→晴れの変化（買い物が増える傾向）
            df["rain_to_clear"] = (
                (df["precipitation"].shift(1) > 5) &
                (df["precipitation"] == 0)
            ).astype(int)

            # 晴れ→雨の変化（買いだめ傾向）
            df["clear_to_rain"] = (
                (df["precipitation"].shift(1) == 0) &
                (df["precipitation"] > 5)
            ).astype(int)

        return df

    def _generate_default_features(
        self,
        dates: Optional[List[date]]
    ) -> pd.DataFrame:
        """デフォルト特徴量（天候データがない場合）"""
        if not dates:
            return pd.DataFrame()

        return pd.DataFrame({
            "date": dates,
            "is_rain": 0,
            "is_heavy_rain": 0,
            "precipitation": 0,
            "temperature_avg": 20,  # デフォルト値
            "weather_impact": 1.0,
            "combined_weather_impact": 1.0,
        })

    async def fetch_weather_forecast(
        self,
        lat: float,
        lon: float,
        days: int = 7
    ) -> pd.DataFrame:
        """
        天気予報API から予報データを取得

        Args:
            lat: 緯度
            lon: 経度
            days: 予報日数

        Returns:
            天気予報データフレーム
        """
        if not self.api_key or not self.api_url:
            return pd.DataFrame()

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.api_url}/forecast",
                    params={
                        "lat": lat,
                        "lon": lon,
                        "appid": self.api_key,
                        "units": "metric",
                        "cnt": days * 8  # 3時間ごとのデータ
                    },
                    timeout=30.0
                )

                if response.status_code == 200:
                    data = response.json()
                    return self._parse_forecast_response(data)

        except Exception as e:
            print(f"Weather API error: {e}")

        return pd.DataFrame()

    def _parse_forecast_response(self, data: dict) -> pd.DataFrame:
        """天気予報APIレスポンスをパース"""
        forecasts = []

        for item in data.get("list", []):
            dt = datetime.fromtimestamp(item["dt"])
            forecasts.append({
                "date": dt.date(),
                "datetime": dt,
                "temperature": item["main"]["temp"],
                "temperature_min": item["main"]["temp_min"],
                "temperature_max": item["main"]["temp_max"],
                "humidity": item["main"]["humidity"],
                "weather_type": item["weather"][0]["main"].lower(),
                "precipitation": item.get("rain", {}).get("3h", 0) +
                                item.get("snow", {}).get("3h", 0),
            })

        df = pd.DataFrame(forecasts)

        # 日次に集約
        if not df.empty:
            daily = df.groupby("date").agg({
                "temperature": "mean",
                "temperature_min": "min",
                "temperature_max": "max",
                "humidity": "mean",
                "precipitation": "sum",
                "weather_type": lambda x: x.mode()[0] if len(x.mode()) > 0 else "cloudy"
            }).reset_index()

            daily.columns = [
                "date", "temperature_avg", "temperature_min",
                "temperature_max", "humidity", "precipitation", "weather_type"
            ]
            daily["is_rain"] = (daily["precipitation"] > 0).astype(int)

            return daily

        return pd.DataFrame()
