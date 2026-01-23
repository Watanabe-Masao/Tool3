"""
特徴量生成モジュールのテスト
"""
import pytest
import pandas as pd
import numpy as np
from datetime import date, timedelta
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.features.calendar_features import CalendarFeatureGenerator
from src.features.weather_features import WeatherFeatureGenerator
from src.features.promotion_features import PromotionFeatureGenerator
from src.features.feature_pipeline import FeaturePipeline


class TestCalendarFeatureGenerator:
    """カレンダー特徴量生成テスト"""

    def setup_method(self):
        self.generator = CalendarFeatureGenerator()

    def test_generate_features_single_date(self):
        """単一日付の特徴量生成"""
        dates = [date(2024, 1, 15)]  # 月曜日
        features = self.generator.generate_features(dates)

        assert len(features) == 1
        assert features.iloc[0]["day_of_week"] == 0  # 月曜日
        assert features.iloc[0]["is_monday"] == 1
        assert features.iloc[0]["is_weekend"] == 0
        assert features.iloc[0]["month"] == 1

    def test_generate_features_weekend(self):
        """週末の特徴量"""
        dates = [date(2024, 1, 13)]  # 土曜日
        features = self.generator.generate_features(dates)

        assert features.iloc[0]["is_weekend"] == 1
        assert features.iloc[0]["is_saturday"] == 1

    def test_generate_features_holiday(self):
        """祝日の特徴量"""
        dates = [date(2024, 1, 1)]  # 元日
        features = self.generator.generate_features(dates)

        assert features.iloc[0]["is_holiday"] == 1
        assert features.iloc[0]["is_new_year"] == 1

    def test_generate_features_golden_week(self):
        """ゴールデンウィークの特徴量"""
        dates = [date(2024, 5, 3)]
        features = self.generator.generate_features(dates)

        assert features.iloc[0]["is_golden_week"] == 1

    def test_cyclical_features(self):
        """周期特徴量のテスト"""
        dates = [date(2024, 1, 1), date(2024, 7, 1)]
        features = self.generator.generate_features(dates)

        # サイン・コサインは-1〜1の範囲
        assert -1 <= features.iloc[0]["dow_sin"] <= 1
        assert -1 <= features.iloc[0]["dow_cos"] <= 1
        assert -1 <= features.iloc[0]["month_sin"] <= 1

    def test_lag_features(self):
        """ラグ特徴量のテスト"""
        # 2週間分のデータ
        dates = pd.date_range("2024-01-01", periods=14, freq="D")
        sales_df = pd.DataFrame({
            "sales_date": dates,
            "sales_amount": range(100, 114)
        })

        result = self.generator.generate_lag_features(sales_df)

        # 7日目（1週間後）にはlag_same_dow_1wが存在
        assert "lag_same_dow_1w" in result.columns
        assert result.iloc[7]["lag_same_dow_1w"] == 100  # 最初の日の値


class TestWeatherFeatureGenerator:
    """天候特徴量生成テスト"""

    def setup_method(self):
        self.generator = WeatherFeatureGenerator()

    def test_generate_features_basic(self):
        """基本天候特徴量"""
        weather_df = pd.DataFrame({
            "date": [date(2024, 1, 15)],
            "temperature_avg": 10.0,
            "precipitation": 0,
        })

        features = self.generator.generate_features(weather_df)

        assert features.iloc[0]["is_rain"] == 0
        assert features.iloc[0]["temperature_avg"] == 10.0

    def test_generate_features_rain(self):
        """雨天時の特徴量"""
        weather_df = pd.DataFrame({
            "date": [date(2024, 1, 15)],
            "temperature_avg": 10.0,
            "precipitation": 15.0,
        })

        features = self.generator.generate_features(weather_df)

        assert features.iloc[0]["is_rain"] == 1
        assert features.iloc[0]["is_heavy_rain"] == 1

    def test_temperature_band(self):
        """気温帯の判定"""
        weather_df = pd.DataFrame({
            "date": [date(2024, 1, 15), date(2024, 8, 15)],
            "temperature_avg": [2.0, 35.0],
            "precipitation": [0, 0],
        })

        features = self.generator.generate_features(weather_df)

        assert features.iloc[0]["is_very_cold"] == 1
        assert features.iloc[1]["is_very_hot"] == 1


class TestPromotionFeatureGenerator:
    """プロモーション特徴量生成テスト"""

    def setup_method(self):
        self.generator = PromotionFeatureGenerator()

    def test_generate_features_no_policy(self):
        """ポイント政策なしの場合"""
        dates = [date(2024, 1, 15)]
        policies_df = pd.DataFrame()

        features = self.generator.generate_features(dates, policies_df)

        assert features.iloc[0]["point_rate"] == 1.0
        assert features.iloc[0]["is_point_up"] == 0

    def test_generate_features_with_policy(self):
        """ポイント政策ありの場合"""
        dates = [date(2024, 1, 16)]  # 火曜日
        policies_df = pd.DataFrame([{
            "policy_id": "P001",
            "policy_name": "火曜ポイント2倍",
            "start_date": date(2024, 1, 1),
            "end_date": date(2024, 12, 31),
            "point_rate": 2.0,
            "target_day_of_week": 1,  # 火曜日
        }])

        features = self.generator.generate_features(dates, policies_df)

        assert features.iloc[0]["point_rate"] == 2.0
        assert features.iloc[0]["is_point_up"] == 1
        assert features.iloc[0]["point_up_level"] == 1


class TestFeaturePipeline:
    """特徴量パイプラインテスト"""

    def setup_method(self):
        self.pipeline = FeaturePipeline()

    def test_feature_names(self):
        """特徴量名リストの取得"""
        base_features = self.pipeline.get_feature_names("base")
        residual_features = self.pipeline.get_feature_names("residual")
        all_features = self.pipeline.get_feature_names("all")

        assert len(base_features) > 0
        assert len(residual_features) > 0
        assert len(all_features) >= len(base_features)

    def test_generate_features_minimal(self):
        """最小限のデータでの特徴量生成"""
        sales_df = pd.DataFrame({
            "sales_date": pd.date_range("2024-01-01", periods=30, freq="D"),
            "sales_amount": np.random.randint(100000, 200000, 30)
        })

        features = self.pipeline.generate_features(sales_df)

        assert len(features) == 30
        assert "day_of_week" in features.columns
        assert "month" in features.columns


class TestHierarchicalReconciliation:
    """階層整合テスト"""

    def test_top_down_reconciliation(self):
        """トップダウン整合のテスト"""
        from src.models.hierarchical_reconciliation import HierarchicalReconciliation

        reconciliation = HierarchicalReconciliation(reconciliation_method="top_down")

        target_date = date(2024, 1, 15)
        forecasts = {
            "company_total": pd.DataFrame({
                "date": [target_date],
                "forecast": [1000000]
            }),
            "store_total": pd.DataFrame({
                "date": [target_date, target_date],
                "store_id": ["S001", "S002"],
                "forecast": [600000, 500000]  # 合計1,100,000
            })
        }

        reconciled = reconciliation.reconcile(forecasts, target_date)

        # 店舗合計が全社トータルに合うように調整される
        store_sum = reconciled["store_total"]["forecast"].sum()
        assert abs(store_sum - 1000000) < 1  # 許容誤差


class TestConfidenceEvaluator:
    """信頼度評価テスト"""

    def test_evaluate_high_confidence(self):
        """高信頼度の評価"""
        from src.models.confidence_evaluator import ConfidenceEvaluator

        evaluator = ConfidenceEvaluator()

        result = evaluator.evaluate(
            forecast_value=1000000,
            level="company_total",
            horizon="daily"
        )

        assert result.rank in ["A", "B"]
        assert 0 <= result.score <= 1
        assert result.lower_bound < result.upper_bound

    def test_evaluate_low_confidence(self):
        """低信頼度の評価"""
        from src.models.confidence_evaluator import ConfidenceEvaluator

        evaluator = ConfidenceEvaluator()

        result = evaluator.evaluate(
            forecast_value=1000000,
            level="store_class",  # 最下位階層
            horizon="monthly",
            historical_cv=0.5  # 高い変動係数
        )

        # 下位階層・月次・高変動 = 低信頼度
        assert result.rank in ["C", "D", "E"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
