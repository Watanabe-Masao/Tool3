"""
信頼度評価モジュール
予測の信頼度をランク評価し、予測区間を算出
"""
import pandas as pd
import numpy as np
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass


@dataclass
class ConfidenceResult:
    """信頼度評価結果"""
    rank: str  # A〜E
    score: float  # 0〜1
    interval_width: float  # 予測区間の幅（割合）
    lower_bound: float  # 下限値
    upper_bound: float  # 上限値
    factors: Dict[str, float]  # 各評価要因のスコア


class ConfidenceEvaluator:
    """
    信頼度評価クラス

    評価要因:
    1. 階層レベル（上位ほど信頼度高）
    2. 過去の予測精度
    3. データの安定性（変動係数）
    4. 外部要因の不確実性（天候予報など）
    5. 予測期間（近いほど信頼度高）
    """

    # 信頼度ランク定義
    RANK_THRESHOLDS = {
        "A": {"min_score": 0.85, "interval_width": 0.05},  # ±5%
        "B": {"min_score": 0.70, "interval_width": 0.10},  # ±10%
        "C": {"min_score": 0.55, "interval_width": 0.15},  # ±15%
        "D": {"min_score": 0.40, "interval_width": 0.20},  # ±20%
        "E": {"min_score": 0.00, "interval_width": 0.30},  # ±30%
    }

    # 階層レベルの基本信頼度
    LEVEL_BASE_CONFIDENCE = {
        "company_total": 0.95,
        "store_total": 0.85,
        "company_category": 0.85,
        "store_category": 0.75,
        "company_class": 0.70,
        "store_class": 0.60,
    }

    # 予測期間の信頼度減衰
    HORIZON_DECAY = {
        "daily": 1.0,    # 翌日予測
        "weekly": 0.90,  # 週次予測
        "monthly": 0.80, # 月次予測
    }

    def __init__(
        self,
        historical_accuracy: Optional[Dict[str, float]] = None,
        custom_thresholds: Optional[Dict] = None
    ):
        """
        Args:
            historical_accuracy: 過去の予測精度（レベル別）
            custom_thresholds: カスタム閾値
        """
        self.historical_accuracy = historical_accuracy or {}
        self.thresholds = custom_thresholds or self.RANK_THRESHOLDS

    def evaluate(
        self,
        forecast_value: float,
        level: str,
        horizon: str = "daily",
        historical_cv: Optional[float] = None,
        weather_uncertainty: Optional[float] = None,
        data_completeness: Optional[float] = None
    ) -> ConfidenceResult:
        """
        予測の信頼度を評価

        Args:
            forecast_value: 予測値
            level: 階層レベル
            horizon: 予測期間
            historical_cv: 過去データの変動係数（標準偏差/平均）
            weather_uncertainty: 天候予報の不確実性（0〜1）
            data_completeness: データ完全性（0〜1）

        Returns:
            ConfidenceResult
        """
        factors = {}

        # 1. 階層レベルスコア
        level_score = self.LEVEL_BASE_CONFIDENCE.get(level, 0.70)
        factors["level"] = level_score

        # 2. 予測期間スコア
        horizon_score = self.HORIZON_DECAY.get(horizon, 0.80)
        factors["horizon"] = horizon_score

        # 3. 過去精度スコア
        if level in self.historical_accuracy:
            # MAPE を信頼度に変換（MAPE 5% → 0.95）
            mape = self.historical_accuracy[level]
            accuracy_score = max(0, 1 - mape)
        else:
            accuracy_score = 0.80  # デフォルト
        factors["historical_accuracy"] = accuracy_score

        # 4. データ安定性スコア
        if historical_cv is not None:
            # CV が低いほど安定（CV 0.1 → 0.9, CV 0.3 → 0.7）
            stability_score = max(0, 1 - historical_cv)
        else:
            stability_score = 0.80
        factors["stability"] = stability_score

        # 5. 外部要因不確実性
        if weather_uncertainty is not None:
            external_score = 1 - weather_uncertainty * 0.3  # 天候不確実性の影響
        else:
            external_score = 0.90
        factors["external"] = external_score

        # 6. データ完全性
        if data_completeness is not None:
            completeness_score = data_completeness
        else:
            completeness_score = 1.0
        factors["completeness"] = completeness_score

        # 総合スコア（重み付き平均）
        weights = {
            "level": 0.25,
            "horizon": 0.15,
            "historical_accuracy": 0.25,
            "stability": 0.15,
            "external": 0.10,
            "completeness": 0.10,
        }

        total_score = sum(
            factors[k] * weights.get(k, 0)
            for k in factors
        )

        # ランク判定
        rank = self._determine_rank(total_score)
        interval_width = self.thresholds[rank]["interval_width"]

        # 予測区間
        lower_bound = forecast_value * (1 - interval_width)
        upper_bound = forecast_value * (1 + interval_width)

        return ConfidenceResult(
            rank=rank,
            score=total_score,
            interval_width=interval_width,
            lower_bound=lower_bound,
            upper_bound=upper_bound,
            factors=factors
        )

    def _determine_rank(self, score: float) -> str:
        """スコアからランクを判定"""
        for rank in ["A", "B", "C", "D", "E"]:
            if score >= self.thresholds[rank]["min_score"]:
                return rank
        return "E"

    def evaluate_batch(
        self,
        forecasts_df: pd.DataFrame,
        historical_stats: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        複数予測の信頼度を一括評価

        Args:
            forecasts_df: 予測データフレーム
                必須: forecast_value, level
                オプション: horizon, store_id, category_id
            historical_stats: 過去の統計情報

        Returns:
            信頼度評価付きデータフレーム
        """
        results = []

        for idx, row in forecasts_df.iterrows():
            forecast_value = row["forecast_value"]
            level = row["level"]
            horizon = row.get("horizon", "daily")

            # 過去の変動係数を取得
            cv = None
            if historical_stats is not None:
                store_id = row.get("store_id")
                category_id = row.get("category_id")
                cv = self._get_historical_cv(
                    historical_stats, level, store_id, category_id
                )

            # 評価
            result = self.evaluate(
                forecast_value=forecast_value,
                level=level,
                horizon=horizon,
                historical_cv=cv
            )

            results.append({
                "index": idx,
                "confidence_rank": result.rank,
                "confidence_score": result.score,
                "interval_width": result.interval_width,
                "forecast_lower": result.lower_bound,
                "forecast_upper": result.upper_bound,
            })

        results_df = pd.DataFrame(results).set_index("index")
        return forecasts_df.join(results_df)

    def _get_historical_cv(
        self,
        stats_df: pd.DataFrame,
        level: str,
        store_id: Optional[str],
        category_id: Optional[str]
    ) -> Optional[float]:
        """過去データの変動係数を取得"""
        mask = stats_df["level"] == level

        if store_id and "store_id" in stats_df.columns:
            mask = mask & (stats_df["store_id"] == store_id)
        if category_id and "category_id" in stats_df.columns:
            mask = mask & (stats_df["category_id"] == category_id)

        filtered = stats_df[mask]
        if not filtered.empty and "cv" in filtered.columns:
            return filtered["cv"].values[0]

        return None

    def calculate_historical_stats(
        self,
        sales_df: pd.DataFrame,
        level: str,
        group_cols: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        過去データの統計情報を計算

        Args:
            sales_df: 売上データ
            level: 階層レベル
            group_cols: グループ化カラム

        Returns:
            統計情報データフレーム
        """
        if group_cols:
            stats = sales_df.groupby(group_cols).agg({
                "sales_amount": ["mean", "std", "count"]
            }).reset_index()
            stats.columns = group_cols + ["mean", "std", "count"]
        else:
            stats = pd.DataFrame([{
                "mean": sales_df["sales_amount"].mean(),
                "std": sales_df["sales_amount"].std(),
                "count": len(sales_df)
            }])

        # 変動係数
        stats["cv"] = stats["std"] / stats["mean"]
        stats["cv"] = stats["cv"].fillna(0)
        stats["level"] = level

        return stats

    def update_historical_accuracy(
        self,
        level: str,
        actual: float,
        predicted: float
    ):
        """
        過去の予測精度を更新

        Args:
            level: 階層レベル
            actual: 実績値
            predicted: 予測値
        """
        if actual > 0:
            mape = abs(actual - predicted) / actual

            # 移動平均で更新
            if level in self.historical_accuracy:
                current = self.historical_accuracy[level]
                self.historical_accuracy[level] = current * 0.9 + mape * 0.1
            else:
                self.historical_accuracy[level] = mape

    def get_confidence_summary(
        self,
        results_df: pd.DataFrame
    ) -> Dict[str, Any]:
        """
        信頼度サマリーを取得

        Args:
            results_df: 評価結果データフレーム

        Returns:
            サマリー辞書
        """
        if "confidence_rank" not in results_df.columns:
            return {}

        rank_counts = results_df["confidence_rank"].value_counts().to_dict()
        total = len(results_df)

        summary = {
            "total_forecasts": total,
            "rank_distribution": rank_counts,
            "rank_percentages": {
                k: v / total * 100 for k, v in rank_counts.items()
            },
            "average_score": results_df["confidence_score"].mean(),
            "high_confidence_ratio": len(
                results_df[results_df["confidence_rank"].isin(["A", "B"])]
            ) / total * 100,
        }

        return summary


class AdaptiveIntervalCalculator:
    """
    適応的予測区間計算
    過去の予測誤差に基づいて区間を動的に調整
    """

    def __init__(self, window_size: int = 30):
        """
        Args:
            window_size: 誤差履歴のウィンドウサイズ
        """
        self.window_size = window_size
        self.error_history: Dict[str, List[float]] = {}

    def add_error(
        self,
        level: str,
        actual: float,
        predicted: float
    ):
        """
        予測誤差を追加

        Args:
            level: 階層レベル
            actual: 実績値
            predicted: 予測値
        """
        if actual > 0:
            error_ratio = (predicted - actual) / actual

            if level not in self.error_history:
                self.error_history[level] = []

            self.error_history[level].append(error_ratio)

            # ウィンドウサイズを超えたら古いデータを削除
            if len(self.error_history[level]) > self.window_size:
                self.error_history[level].pop(0)

    def calculate_interval(
        self,
        level: str,
        forecast: float,
        confidence_level: float = 0.95
    ) -> Tuple[float, float]:
        """
        予測区間を計算

        Args:
            level: 階層レベル
            forecast: 予測値
            confidence_level: 信頼水準（0.95 = 95%）

        Returns:
            (下限, 上限)
        """
        if level not in self.error_history or len(self.error_history[level]) < 5:
            # デフォルト区間（±10%）
            return forecast * 0.90, forecast * 1.10

        errors = np.array(self.error_history[level])

        # パーセンタイルで区間を計算
        alpha = 1 - confidence_level
        lower_pct = alpha / 2 * 100
        upper_pct = (1 - alpha / 2) * 100

        lower_error = np.percentile(errors, lower_pct)
        upper_error = np.percentile(errors, upper_pct)

        lower_bound = forecast * (1 + lower_error)
        upper_bound = forecast * (1 + upper_error)

        return lower_bound, upper_bound

    def get_interval_stats(self, level: str) -> Dict[str, float]:
        """
        区間統計を取得

        Args:
            level: 階層レベル

        Returns:
            統計情報
        """
        if level not in self.error_history:
            return {}

        errors = np.array(self.error_history[level])

        return {
            "mean_error": np.mean(errors),
            "std_error": np.std(errors),
            "bias": np.mean(errors),  # 正ならover-forecast
            "coverage_95": np.percentile(errors, 97.5) - np.percentile(errors, 2.5),
            "n_samples": len(errors),
        }
