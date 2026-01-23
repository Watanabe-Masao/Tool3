"""
予測エンジン
全てのコンポーネントを統合して予測を実行
"""
import pandas as pd
import numpy as np
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any
import os
import json
from dataclasses import dataclass, asdict

from .base_forecast import BaseForecastModel
from .residual_forecast import ResidualForecastModel
from .hierarchical_reconciliation import HierarchicalReconciliation
from .confidence_evaluator import ConfidenceEvaluator, AdaptiveIntervalCalculator
from ..features.feature_pipeline import FeaturePipeline


@dataclass
class ForecastOutput:
    """予測出力"""
    forecast_date: date
    level: str
    store_id: Optional[str]
    category_id: Optional[str]
    horizon: str
    forecast_value: float
    forecast_lower: float
    forecast_upper: float
    base_forecast: float
    residual_forecast: float
    confidence_rank: str
    confidence_score: float


class ForecastEngine:
    """
    予測エンジン

    2段階予測 + 階層整合:
    1. ベース予測（安定成分）
    2. 残差予測（変動成分）
    3. 階層整合
    4. 信頼度評価
    """

    def __init__(
        self,
        model_path: str = "./data/models",
        reconciliation_method: str = "top_down_weighted"
    ):
        """
        Args:
            model_path: モデル保存パス
            reconciliation_method: 階層整合方法
        """
        self.model_path = model_path
        self.feature_pipeline = FeaturePipeline()
        self.reconciliation = HierarchicalReconciliation(
            reconciliation_method=reconciliation_method
        )
        self.confidence_evaluator = ConfidenceEvaluator()
        self.interval_calculator = AdaptiveIntervalCalculator()

        # モデル格納
        self.base_models: Dict[str, BaseForecastModel] = {}
        self.residual_models: Dict[str, ResidualForecastModel] = {}

    def train_all_models(
        self,
        sales_data: Dict[str, pd.DataFrame],
        weather_df: Optional[pd.DataFrame] = None,
        events_df: Optional[pd.DataFrame] = None,
        policies_df: Optional[pd.DataFrame] = None
    ) -> Dict[str, Any]:
        """
        全階層のモデルを学習

        Args:
            sales_data: 階層別売上データ
                - company_total: [sales_date, sales_amount]
                - store_total: [sales_date, store_id, sales_amount]
                - company_category: [sales_date, category_id, sales_amount]
                - store_category: [sales_date, store_id, category_id, sales_amount]
            weather_df: 天候データ
            events_df: イベントデータ
            policies_df: ポイント政策データ

        Returns:
            学習結果サマリー
        """
        training_results = {}

        for level, df in sales_data.items():
            print(f"Training models for {level}...")

            # 特徴量生成
            features_df = self.feature_pipeline.generate_features(
                df.rename(columns={"sales_date": "sales_date"}),
                weather_df=weather_df,
                events_df=events_df,
                policies_df=policies_df
            )

            # ベースモデル学習
            base_model = BaseForecastModel(level=level)
            base_metrics = base_model.train(features_df)
            self.base_models[level] = base_model
            training_results[f"{level}_base"] = base_metrics

            # ベース予測
            base_predictions = base_model.predict(features_df)

            # 残差モデル学習
            residual_model = ResidualForecastModel(level=level)
            residual_metrics = residual_model.train(
                features_df,
                base_predictions
            )
            self.residual_models[level] = residual_model
            training_results[f"{level}_residual"] = residual_metrics

            print(f"  Base MAPE: {base_metrics['cv_mape_mean']:.4f}")
            print(f"  Residual MAE: {residual_metrics['cv_mae_mean']:.2f}")

        # モデル保存
        self.save_models()

        return training_results

    def forecast(
        self,
        target_date: date,
        horizon: str = "daily",
        historical_sales: Dict[str, pd.DataFrame] = None,
        weather_forecast: Optional[pd.DataFrame] = None,
        events_df: Optional[pd.DataFrame] = None,
        policies_df: Optional[pd.DataFrame] = None,
        apply_reconciliation: bool = True
    ) -> List[ForecastOutput]:
        """
        予測を実行

        Args:
            target_date: 予測対象日
            horizon: 予測期間（daily/weekly/monthly）
            historical_sales: 過去の売上データ（特徴量計算用）
            weather_forecast: 天気予報データ
            events_df: イベントデータ
            policies_df: ポイント政策データ
            apply_reconciliation: 階層整合を適用するか

        Returns:
            予測結果リスト
        """
        if horizon == "weekly":
            target_dates = [
                target_date + timedelta(days=i) for i in range(7)
            ]
        elif horizon == "monthly":
            # 当月の残り日数
            next_month = (target_date.replace(day=1) + timedelta(days=32)).replace(day=1)
            target_dates = pd.date_range(target_date, next_month - timedelta(days=1)).date.tolist()
        else:
            target_dates = [target_date]

        all_forecasts = []

        for t_date in target_dates:
            forecasts = self._forecast_single_date(
                t_date,
                horizon,
                historical_sales,
                weather_forecast,
                events_df,
                policies_df,
                apply_reconciliation
            )
            all_forecasts.extend(forecasts)

        return all_forecasts

    def _forecast_single_date(
        self,
        target_date: date,
        horizon: str,
        historical_sales: Dict[str, pd.DataFrame],
        weather_forecast: Optional[pd.DataFrame],
        events_df: Optional[pd.DataFrame],
        policies_df: Optional[pd.DataFrame],
        apply_reconciliation: bool
    ) -> List[ForecastOutput]:
        """単一日付の予測"""
        raw_forecasts = {}
        forecast_details = {}

        # 各階層で予測
        for level in self.base_models.keys():
            hist_df = historical_sales.get(level, pd.DataFrame())
            if hist_df.empty:
                continue

            # 予測用特徴量生成
            features = self.feature_pipeline.generate_forecast_features(
                [target_date],
                hist_df,
                weather_forecast_df=weather_forecast,
                events_df=events_df,
                policies_df=policies_df
            )

            # ベース予測
            base_pred = self.base_models[level].predict(features)[0]

            # 残差予測
            if level in self.residual_models:
                residual_pred = self.residual_models[level].predict(features)[0]
            else:
                residual_pred = 0

            # 合計予測
            total_pred = base_pred + residual_pred

            # 結果格納
            forecast_details[level] = {
                "base": base_pred,
                "residual": residual_pred,
                "total": total_pred
            }

            # 階層整合用データ
            if level == "company_total":
                raw_forecasts[level] = pd.DataFrame({
                    "date": [target_date],
                    "forecast": [total_pred]
                })
            elif level == "store_total":
                # 店舗別の場合
                stores = hist_df["store_id"].unique()
                store_forecasts = []
                for store_id in stores:
                    store_features = self.feature_pipeline.generate_forecast_features(
                        [target_date],
                        hist_df[hist_df["store_id"] == store_id],
                        weather_forecast_df=weather_forecast,
                        events_df=events_df,
                        policies_df=policies_df
                    )
                    store_base = self.base_models[level].predict(store_features)[0]
                    store_residual = self.residual_models[level].predict(store_features)[0] if level in self.residual_models else 0
                    store_forecasts.append({
                        "date": target_date,
                        "store_id": store_id,
                        "forecast": store_base + store_residual,
                        "base": store_base,
                        "residual": store_residual
                    })
                raw_forecasts[level] = pd.DataFrame(store_forecasts)

        # 階層整合
        if apply_reconciliation and raw_forecasts:
            reconciled = self.reconciliation.reconcile(raw_forecasts, target_date)
        else:
            reconciled = raw_forecasts

        # 結果をForecastOutputに変換
        outputs = []

        for level, df in reconciled.items():
            if df.empty:
                continue

            for _, row in df.iterrows():
                store_id = row.get("store_id")
                category_id = row.get("category_id")
                forecast_value = row["forecast"]

                # 信頼度評価
                confidence = self.confidence_evaluator.evaluate(
                    forecast_value=forecast_value,
                    level=level,
                    horizon=horizon
                )

                # ベース・残差の詳細（利用可能な場合）
                base_val = row.get("base", forecast_value)
                residual_val = row.get("residual", 0)

                outputs.append(ForecastOutput(
                    forecast_date=target_date,
                    level=level,
                    store_id=store_id,
                    category_id=category_id,
                    horizon=horizon,
                    forecast_value=forecast_value,
                    forecast_lower=confidence.lower_bound,
                    forecast_upper=confidence.upper_bound,
                    base_forecast=base_val,
                    residual_forecast=residual_val,
                    confidence_rank=confidence.rank,
                    confidence_score=confidence.score
                ))

        return outputs

    def forecast_to_dataframe(
        self,
        forecasts: List[ForecastOutput]
    ) -> pd.DataFrame:
        """予測結果をDataFrameに変換"""
        return pd.DataFrame([asdict(f) for f in forecasts])

    def save_models(self):
        """全モデルを保存"""
        os.makedirs(self.model_path, exist_ok=True)

        for level, model in self.base_models.items():
            model.save(self.model_path)

        for level, model in self.residual_models.items():
            model.save(self.model_path)

        # メタ情報保存
        meta = {
            "levels": list(self.base_models.keys()),
            "saved_at": datetime.now().isoformat()
        }
        with open(os.path.join(self.model_path, "engine_meta.json"), "w") as f:
            json.dump(meta, f, indent=2)

    def load_models(self):
        """全モデルを読み込み"""
        meta_path = os.path.join(self.model_path, "engine_meta.json")
        if not os.path.exists(meta_path):
            raise FileNotFoundError(f"Model metadata not found: {meta_path}")

        with open(meta_path, "r") as f:
            meta = json.load(f)

        for level in meta["levels"]:
            base_name = f"base_{level}"
            if os.path.exists(os.path.join(self.model_path, f"{base_name}.lgb")):
                self.base_models[level] = BaseForecastModel.load(
                    self.model_path, base_name
                )

            residual_name = f"residual_{level}"
            if os.path.exists(os.path.join(self.model_path, f"{residual_name}.lgb")):
                self.residual_models[level] = ResidualForecastModel.load(
                    self.model_path, residual_name
                )

    def evaluate_accuracy(
        self,
        forecasts_df: pd.DataFrame,
        actuals_df: pd.DataFrame
    ) -> Dict[str, Any]:
        """
        予測精度を評価

        Args:
            forecasts_df: 予測結果
            actuals_df: 実績データ

        Returns:
            精度評価結果
        """
        # マージ
        merged = forecasts_df.merge(
            actuals_df,
            on=["forecast_date", "level", "store_id", "category_id"],
            how="inner",
            suffixes=("", "_actual")
        )

        if merged.empty:
            return {"error": "No matching data"}

        # 精度指標
        merged["error"] = merged["forecast_value"] - merged["actual_value"]
        merged["abs_error"] = abs(merged["error"])
        merged["pct_error"] = merged["abs_error"] / merged["actual_value"]

        results = {
            "overall": {
                "mape": merged["pct_error"].mean(),
                "mae": merged["abs_error"].mean(),
                "rmse": np.sqrt((merged["error"] ** 2).mean()),
                "bias": merged["error"].mean(),
                "n_samples": len(merged)
            },
            "by_level": {},
            "by_rank": {}
        }

        # レベル別
        for level in merged["level"].unique():
            level_df = merged[merged["level"] == level]
            results["by_level"][level] = {
                "mape": level_df["pct_error"].mean(),
                "mae": level_df["abs_error"].mean(),
                "n_samples": len(level_df)
            }

        # ランク別
        for rank in merged["confidence_rank"].unique():
            rank_df = merged[merged["confidence_rank"] == rank]
            results["by_rank"][rank] = {
                "mape": rank_df["pct_error"].mean(),
                "mae": rank_df["abs_error"].mean(),
                "n_samples": len(rank_df)
            }

        # 信頼度評価の更新
        for _, row in merged.iterrows():
            self.confidence_evaluator.update_historical_accuracy(
                row["level"],
                row["actual_value"],
                row["forecast_value"]
            )
            self.interval_calculator.add_error(
                row["level"],
                row["actual_value"],
                row["forecast_value"]
            )

        return results
