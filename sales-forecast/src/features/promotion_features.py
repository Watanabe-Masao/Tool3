"""
プロモーション特徴量生成
ポイント政策、セール、キャンペーンなどの特徴量
"""
import pandas as pd
import numpy as np
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional


class PromotionFeatureGenerator:
    """プロモーション特徴量生成クラス"""

    # ポイント倍率の売上影響度推定
    POINT_RATE_IMPACT = {
        1.0: 1.00,   # 通常
        2.0: 1.15,   # 2倍
        3.0: 1.25,   # 3倍
        5.0: 1.40,   # 5倍
        10.0: 1.60,  # 10倍
    }

    def __init__(self):
        pass

    def generate_features(
        self,
        dates: List[date],
        point_policies_df: pd.DataFrame,
        store_id: Optional[str] = None,
        category_id: Optional[str] = None
    ) -> pd.DataFrame:
        """
        ポイント政策特徴量を生成

        Args:
            dates: 対象日付リスト
            point_policies_df: ポイント政策データフレーム
            store_id: 店舗ID（フィルタリング用）
            category_id: カテゴリID（フィルタリング用）

        Returns:
            特徴量データフレーム
        """
        features = []

        for d in dates:
            feat = self._generate_date_features(
                d, point_policies_df, store_id, category_id
            )
            features.append(feat)

        return pd.DataFrame(features)

    def _generate_date_features(
        self,
        d: date,
        policies_df: pd.DataFrame,
        store_id: Optional[str] = None,
        category_id: Optional[str] = None
    ) -> Dict:
        """単一日付のポイント政策特徴量"""
        features = {
            "date": d,
            "point_rate": 1.0,  # デフォルト（通常ポイント）
            "is_point_up": 0,
            "point_up_level": 0,  # 0=通常, 1=2倍, 2=3倍以上, 3=5倍以上
            "point_impact": 1.0,
            "policy_count": 0,
        }

        if policies_df.empty:
            return features

        # 対象日に有効な政策をフィルタリング
        active_policies = policies_df[
            (policies_df["start_date"] <= d) &
            (policies_df["end_date"] >= d)
        ]

        # 店舗フィルタ
        if store_id:
            active_policies = active_policies[
                (active_policies["store_id"].isna()) |
                (active_policies["store_id"] == store_id)
            ]

        # カテゴリフィルタ
        if category_id:
            active_policies = active_policies[
                (active_policies["category_id"].isna()) |
                (active_policies["category_id"] == category_id)
            ]

        # 曜日フィルタ
        day_of_week = d.weekday()
        active_policies = active_policies[
            (active_policies["target_day_of_week"].isna()) |
            (active_policies["target_day_of_week"] == day_of_week)
        ]

        if active_policies.empty:
            return features

        # 最大ポイント倍率を取得
        max_rate = active_policies["point_rate"].max()
        features["point_rate"] = max_rate
        features["is_point_up"] = int(max_rate > 1.0)
        features["policy_count"] = len(active_policies)

        # ポイントアップレベル
        if max_rate >= 5.0:
            features["point_up_level"] = 3
        elif max_rate >= 3.0:
            features["point_up_level"] = 2
        elif max_rate >= 2.0:
            features["point_up_level"] = 1

        # 影響度推定
        features["point_impact"] = self._estimate_point_impact(max_rate)

        return features

    def _estimate_point_impact(self, point_rate: float) -> float:
        """ポイント倍率から売上影響度を推定"""
        # 線形補間
        if point_rate <= 1.0:
            return 1.0

        rates = sorted(self.POINT_RATE_IMPACT.keys())
        impacts = [self.POINT_RATE_IMPACT[r] for r in rates]

        # 補間
        for i in range(len(rates) - 1):
            if rates[i] <= point_rate <= rates[i + 1]:
                ratio = (point_rate - rates[i]) / (rates[i + 1] - rates[i])
                return impacts[i] + ratio * (impacts[i + 1] - impacts[i])

        # 最大を超える場合
        return impacts[-1] * (1 + (point_rate - rates[-1]) * 0.05)

    def generate_promotion_calendar(
        self,
        start_date: date,
        end_date: date,
        policies_df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        期間全体のプロモーションカレンダーを生成

        Args:
            start_date: 開始日
            end_date: 終了日
            policies_df: ポイント政策データフレーム

        Returns:
            プロモーションカレンダーデータフレーム
        """
        dates = pd.date_range(start_date, end_date, freq="D").date.tolist()

        calendar = []
        for d in dates:
            row = {
                "date": d,
                "day_of_week": d.weekday(),
                "is_point_day": 0,
                "max_point_rate": 1.0,
                "policy_names": [],
            }

            # 有効な政策を検索
            for _, policy in policies_df.iterrows():
                if policy["start_date"] <= d <= policy["end_date"]:
                    # 曜日チェック
                    target_dow = policy.get("target_day_of_week")
                    if pd.isna(target_dow) or target_dow == d.weekday():
                        row["is_point_day"] = 1
                        row["max_point_rate"] = max(
                            row["max_point_rate"],
                            policy["point_rate"]
                        )
                        row["policy_names"].append(policy["policy_name"])

            row["policy_names"] = ", ".join(row["policy_names"])
            calendar.append(row)

        return pd.DataFrame(calendar)

    def add_promotion_lag_features(
        self,
        df: pd.DataFrame,
        point_col: str = "point_rate"
    ) -> pd.DataFrame:
        """
        プロモーションラグ特徴量を追加

        Args:
            df: データフレーム（date, point_rate含む）
            point_col: ポイント倍率カラム名

        Returns:
            ラグ特徴量付きデータフレーム
        """
        df = df.sort_values("date")

        # 前日のポイント状況
        df["point_rate_lag_1d"] = df[point_col].shift(1)

        # ポイントアップ前日フラグ（駆け込み需要）
        df["is_before_point_up"] = (
            (df[point_col] > 1.0) &
            (df[point_col].shift(1) == 1.0)
        ).astype(int).shift(-1).fillna(0).astype(int)

        # ポイントアップ翌日フラグ（反動減）
        df["is_after_point_up"] = (
            (df[point_col] == 1.0) &
            (df[point_col].shift(1) > 1.0)
        ).astype(int)

        # 連続ポイントアップ日数
        point_up = (df[point_col] > 1.0).astype(int)
        df["consecutive_point_days"] = point_up.groupby(
            (point_up != point_up.shift()).cumsum()
        ).cumsum() * point_up

        # 過去7日間のポイントアップ日数
        df["point_up_days_7d"] = (df[point_col] > 1.0).rolling(
            window=7, min_periods=1
        ).sum()

        return df


class SeasonalPromotionGenerator:
    """季節・シーズンプロモーション特徴量"""

    # シーズンごとのキャンペーン傾向
    SEASONAL_CAMPAIGNS = {
        "new_year_sale": {
            "start": (1, 1),
            "end": (1, 7),
            "impact": 1.3
        },
        "spring_sale": {
            "start": (3, 15),
            "end": (4, 15),
            "impact": 1.15
        },
        "golden_week_sale": {
            "start": (4, 29),
            "end": (5, 7),
            "impact": 1.2
        },
        "summer_sale": {
            "start": (7, 1),
            "end": (8, 31),
            "impact": 1.1
        },
        "autumn_sale": {
            "start": (10, 1),
            "end": (10, 31),
            "impact": 1.1
        },
        "year_end_sale": {
            "start": (12, 20),
            "end": (12, 31),
            "impact": 1.25
        },
    }

    def generate_seasonal_features(
        self,
        dates: List[date]
    ) -> pd.DataFrame:
        """
        季節キャンペーン特徴量を生成

        Args:
            dates: 対象日付リスト

        Returns:
            特徴量データフレーム
        """
        features = []

        for d in dates:
            feat = {
                "date": d,
                "seasonal_campaign": "",
                "seasonal_impact": 1.0,
            }

            for campaign_name, config in self.SEASONAL_CAMPAIGNS.items():
                start_month, start_day = config["start"]
                end_month, end_day = config["end"]

                # 年をまたぐキャンペーンの処理
                if start_month > end_month:
                    in_campaign = (
                        (d.month >= start_month and d.day >= start_day) or
                        (d.month <= end_month and d.day <= end_day)
                    )
                else:
                    start_date = date(d.year, start_month, start_day)
                    end_date = date(d.year, end_month, end_day)
                    in_campaign = start_date <= d <= end_date

                if in_campaign:
                    feat["seasonal_campaign"] = campaign_name
                    feat["seasonal_impact"] = max(
                        feat["seasonal_impact"],
                        config["impact"]
                    )

            features.append(feat)

        return pd.DataFrame(features)
