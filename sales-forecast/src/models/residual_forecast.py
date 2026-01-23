"""
残差予測モデル（段階2）
変動成分：天候・ポイント政策などの外部要因
"""
import pandas as pd
import numpy as np
from datetime import date, datetime
from typing import List, Dict, Optional, Tuple, Any
import lightgbm as lgb
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import joblib
import os
import json


class ResidualForecastModel:
    """
    残差予測モデル（変動成分）
    ベース予測との残差を、天候・ポイント政策などの外部要因で予測
    """

    # 残差予測に使用する特徴量
    DEFAULT_FEATURES = [
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
        # 直近ラグ（短期変動）
        "lag_1d", "lag_2d", "lag_3d",
        # 前週比
        "wow_ratio",
        # イベント影響（短期）
        "custom_event_impact",
    ]

    # LightGBMパラメータ（残差予測用）
    DEFAULT_PARAMS = {
        "objective": "regression",
        "metric": "mae",
        "boosting_type": "gbdt",
        "num_leaves": 15,  # より単純なモデル
        "learning_rate": 0.03,
        "feature_fraction": 0.7,
        "bagging_fraction": 0.7,
        "bagging_freq": 5,
        "min_child_samples": 30,
        "reg_alpha": 0.2,
        "reg_lambda": 0.2,
        "verbose": -1,
        "n_jobs": -1,
        "random_state": 42,
    }

    def __init__(
        self,
        level: str,
        store_id: Optional[str] = None,
        category_id: Optional[str] = None,
        features: Optional[List[str]] = None,
        params: Optional[Dict] = None
    ):
        """
        Args:
            level: 階層レベル
            store_id: 店舗ID
            category_id: カテゴリID
            features: 使用する特徴量リスト
            params: LightGBMパラメータ
        """
        self.level = level
        self.store_id = store_id
        self.category_id = category_id
        self.features = features or self.DEFAULT_FEATURES
        self.params = {**self.DEFAULT_PARAMS, **(params or {})}

        self.model: Optional[lgb.Booster] = None
        self.feature_importance: Optional[pd.DataFrame] = None
        self.training_metrics: Dict[str, float] = {}

        # 残差の統計情報
        self.residual_stats: Dict[str, float] = {}

    def train(
        self,
        train_df: pd.DataFrame,
        base_predictions: np.ndarray,
        target_col: str = "sales_amount",
        n_splits: int = 5,
        num_boost_round: int = 500,
        early_stopping_rounds: int = 30
    ) -> Dict[str, float]:
        """
        残差モデルを学習

        Args:
            train_df: 学習データ
            base_predictions: ベース予測値
            target_col: 目的変数カラム名
            n_splits: 時系列交差検証の分割数
            num_boost_round: ブースティング回数
            early_stopping_rounds: 早期停止ラウンド数

        Returns:
            学習メトリクス
        """
        # 残差を計算
        y_actual = train_df[target_col].values
        residuals = y_actual - base_predictions

        # 残差の統計情報を保存
        self.residual_stats = {
            "mean": float(np.mean(residuals)),
            "std": float(np.std(residuals)),
            "min": float(np.min(residuals)),
            "max": float(np.max(residuals)),
            "percentile_5": float(np.percentile(residuals, 5)),
            "percentile_95": float(np.percentile(residuals, 95)),
        }

        # 特徴量を選択
        available_features = [f for f in self.features if f in train_df.columns]
        X = train_df[available_features].fillna(0)
        y = residuals

        # 時系列交差検証
        tscv = TimeSeriesSplit(n_splits=n_splits)
        cv_scores = []

        for train_idx, val_idx in tscv.split(X):
            X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
            y_train, y_val = y[train_idx], y[val_idx]

            train_data = lgb.Dataset(X_train, label=y_train)
            val_data = lgb.Dataset(X_val, label=y_val, reference=train_data)

            model = lgb.train(
                self.params,
                train_data,
                num_boost_round=num_boost_round,
                valid_sets=[train_data, val_data],
                valid_names=["train", "valid"],
                callbacks=[
                    lgb.early_stopping(early_stopping_rounds),
                    lgb.log_evaluation(period=0)
                ]
            )

            # 検証スコア
            y_pred = model.predict(X_val)
            mae = mean_absolute_error(y_val, y_pred)
            cv_scores.append(mae)

        # 最終モデルを全データで学習
        train_data = lgb.Dataset(X, label=y)
        self.model = lgb.train(
            self.params,
            train_data,
            num_boost_round=num_boost_round
        )

        # 特徴量重要度
        self.feature_importance = pd.DataFrame({
            "feature": available_features,
            "importance": self.model.feature_importance(importance_type="gain")
        }).sort_values("importance", ascending=False)

        # メトリクス
        y_pred_final = self.model.predict(X)
        self.training_metrics = {
            "cv_mae_mean": np.mean(cv_scores),
            "cv_mae_std": np.std(cv_scores),
            "train_mae": mean_absolute_error(y, y_pred_final),
            "train_rmse": np.sqrt(mean_squared_error(y, y_pred_final)),
            "train_r2": r2_score(y, y_pred_final),
            "residual_mean": self.residual_stats["mean"],
            "residual_std": self.residual_stats["std"],
            "n_features": len(available_features),
            "n_samples": len(y),
        }

        return self.training_metrics

    def predict(
        self,
        X: pd.DataFrame,
        clip_residual: bool = True
    ) -> np.ndarray:
        """
        残差予測を実行

        Args:
            X: 特徴量データフレーム
            clip_residual: 異常な残差をクリップするか

        Returns:
            残差予測値配列
        """
        if self.model is None:
            raise ValueError("Model not trained. Call train() first.")

        # 特徴量を選択
        available_features = [f for f in self.features if f in X.columns]
        X_pred = X[available_features].fillna(0)

        predictions = self.model.predict(X_pred)

        # 異常な残差をクリップ
        if clip_residual and self.residual_stats:
            lower = self.residual_stats.get("percentile_5", -np.inf)
            upper = self.residual_stats.get("percentile_95", np.inf)
            predictions = np.clip(predictions, lower, upper)

        return predictions

    def get_adjustment_factors(
        self,
        X: pd.DataFrame
    ) -> pd.DataFrame:
        """
        各変動要因による調整係数を取得

        Args:
            X: 特徴量データフレーム

        Returns:
            調整係数データフレーム
        """
        factors = pd.DataFrame(index=X.index)

        # 天候影響
        if "combined_weather_impact" in X.columns:
            factors["weather_factor"] = X["combined_weather_impact"]
        else:
            factors["weather_factor"] = 1.0

        # ポイント影響
        if "point_impact" in X.columns:
            factors["point_factor"] = X["point_impact"]
        else:
            factors["point_factor"] = 1.0

        # 総合調整係数
        factors["combined_factor"] = (
            factors["weather_factor"] * factors["point_factor"]
        )

        return factors

    def save(self, path: str):
        """
        モデルを保存

        Args:
            path: 保存ディレクトリパス
        """
        os.makedirs(path, exist_ok=True)

        # モデル名を生成
        model_name = f"residual_{self.level}"
        if self.store_id:
            model_name += f"_{self.store_id}"
        if self.category_id:
            model_name += f"_{self.category_id}"

        # LightGBMモデル保存
        model_path = os.path.join(path, f"{model_name}.lgb")
        self.model.save_model(model_path)

        # メタデータ保存
        metadata = {
            "level": self.level,
            "store_id": self.store_id,
            "category_id": self.category_id,
            "features": self.features,
            "params": self.params,
            "training_metrics": self.training_metrics,
            "residual_stats": self.residual_stats,
        }
        meta_path = os.path.join(path, f"{model_name}_meta.json")
        with open(meta_path, "w") as f:
            json.dump(metadata, f, indent=2, default=str)

        # 特徴量重要度保存
        if self.feature_importance is not None:
            fi_path = os.path.join(path, f"{model_name}_importance.csv")
            self.feature_importance.to_csv(fi_path, index=False)

    @classmethod
    def load(cls, path: str, model_name: str) -> "ResidualForecastModel":
        """
        モデルを読み込み

        Args:
            path: 保存ディレクトリパス
            model_name: モデル名

        Returns:
            ResidualForecastModelインスタンス
        """
        # メタデータ読み込み
        meta_path = os.path.join(path, f"{model_name}_meta.json")
        with open(meta_path, "r") as f:
            metadata = json.load(f)

        # インスタンス作成
        instance = cls(
            level=metadata["level"],
            store_id=metadata.get("store_id"),
            category_id=metadata.get("category_id"),
            features=metadata.get("features"),
            params=metadata.get("params")
        )

        # モデル読み込み
        model_path = os.path.join(path, f"{model_name}.lgb")
        instance.model = lgb.Booster(model_file=model_path)
        instance.training_metrics = metadata.get("training_metrics", {})
        instance.residual_stats = metadata.get("residual_stats", {})

        # 特徴量重要度読み込み
        fi_path = os.path.join(path, f"{model_name}_importance.csv")
        if os.path.exists(fi_path):
            instance.feature_importance = pd.read_csv(fi_path)

        return instance

    def get_feature_importance(
        self,
        top_n: int = 15
    ) -> pd.DataFrame:
        """
        特徴量重要度を取得

        Args:
            top_n: 上位N件

        Returns:
            特徴量重要度データフレーム
        """
        if self.feature_importance is None:
            return pd.DataFrame()
        return self.feature_importance.head(top_n)
