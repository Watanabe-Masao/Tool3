"""
ベース予測モデル（段階1）
安定成分：曜日・季節・トレンドなどの周期的パターン
"""
import pandas as pd
import numpy as np
from datetime import date, datetime
from typing import List, Dict, Optional, Tuple, Any
import lightgbm as lgb
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import mean_absolute_percentage_error, mean_squared_error, r2_score
import joblib
import os
import json


class BaseForecastModel:
    """
    ベース予測モデル（安定成分）
    LightGBMを使用して曜日・季節性などの周期的パターンを学習
    """

    # ベース予測に使用する特徴量
    DEFAULT_FEATURES = [
        # 曜日特徴量
        "day_of_week", "is_weekend", "is_monday", "is_friday",
        "is_saturday", "is_sunday",
        # 周期特徴量（サイン・コサイン）
        "dow_sin", "dow_cos", "month_sin", "month_cos",
        "doy_sin", "doy_cos",
        # 月・年特徴量
        "month", "week_of_year", "week_of_month",
        "is_month_start", "is_month_end", "is_payday",
        # 季節特徴量
        "is_spring", "is_summer", "is_autumn", "is_winter",
        # 祝日特徴量
        "is_holiday", "is_holiday_eve", "is_holiday_after",
        "is_golden_week", "is_obon", "is_year_end", "is_new_year",
        "is_long_holiday", "consecutive_holiday_days",
        # イベント影響
        "fixed_event_impact", "floating_event_impact", "custom_event_impact",
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

    # LightGBMパラメータ
    DEFAULT_PARAMS = {
        "objective": "regression",
        "metric": "mape",
        "boosting_type": "gbdt",
        "num_leaves": 31,
        "learning_rate": 0.05,
        "feature_fraction": 0.8,
        "bagging_fraction": 0.8,
        "bagging_freq": 5,
        "min_child_samples": 20,
        "reg_alpha": 0.1,
        "reg_lambda": 0.1,
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

    def train(
        self,
        train_df: pd.DataFrame,
        target_col: str = "sales_amount",
        n_splits: int = 5,
        num_boost_round: int = 1000,
        early_stopping_rounds: int = 50
    ) -> Dict[str, float]:
        """
        モデルを学習

        Args:
            train_df: 学習データ
            target_col: 目的変数カラム名
            n_splits: 時系列交差検証の分割数
            num_boost_round: ブースティング回数
            early_stopping_rounds: 早期停止ラウンド数

        Returns:
            学習メトリクス
        """
        # 特徴量を選択
        available_features = [f for f in self.features if f in train_df.columns]
        X = train_df[available_features]
        y = train_df[target_col]

        # 欠損値チェック
        X = X.fillna(0)

        # 時系列交差検証
        tscv = TimeSeriesSplit(n_splits=n_splits)
        cv_scores = []

        for train_idx, val_idx in tscv.split(X):
            X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
            y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]

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
            mape = mean_absolute_percentage_error(y_val, y_pred)
            cv_scores.append(mape)

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
            "cv_mape_mean": np.mean(cv_scores),
            "cv_mape_std": np.std(cv_scores),
            "train_mape": mean_absolute_percentage_error(y, y_pred_final),
            "train_rmse": np.sqrt(mean_squared_error(y, y_pred_final)),
            "train_r2": r2_score(y, y_pred_final),
            "n_features": len(available_features),
            "n_samples": len(y),
        }

        return self.training_metrics

    def predict(
        self,
        X: pd.DataFrame
    ) -> np.ndarray:
        """
        予測を実行

        Args:
            X: 特徴量データフレーム

        Returns:
            予測値配列
        """
        if self.model is None:
            raise ValueError("Model not trained. Call train() first.")

        # 特徴量を選択
        available_features = [f for f in self.features if f in X.columns]
        X_pred = X[available_features].fillna(0)

        return self.model.predict(X_pred)

    def save(self, path: str):
        """
        モデルを保存

        Args:
            path: 保存ディレクトリパス
        """
        os.makedirs(path, exist_ok=True)

        # モデル名を生成
        model_name = f"base_{self.level}"
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
        }
        meta_path = os.path.join(path, f"{model_name}_meta.json")
        with open(meta_path, "w") as f:
            json.dump(metadata, f, indent=2, default=str)

        # 特徴量重要度保存
        if self.feature_importance is not None:
            fi_path = os.path.join(path, f"{model_name}_importance.csv")
            self.feature_importance.to_csv(fi_path, index=False)

    @classmethod
    def load(cls, path: str, model_name: str) -> "BaseForecastModel":
        """
        モデルを読み込み

        Args:
            path: 保存ディレクトリパス
            model_name: モデル名

        Returns:
            BaseForecastModelインスタンス
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

        # 特徴量重要度読み込み
        fi_path = os.path.join(path, f"{model_name}_importance.csv")
        if os.path.exists(fi_path):
            instance.feature_importance = pd.read_csv(fi_path)

        return instance

    def get_feature_importance(
        self,
        top_n: int = 20
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
