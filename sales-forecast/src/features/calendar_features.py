"""
カレンダー特徴量生成
曜日、祝日、イベントなどの時間的特徴量
"""
import pandas as pd
import numpy as np
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional, Tuple
import jpholiday


class CalendarFeatureGenerator:
    """カレンダー特徴量生成クラス"""

    # 日本の主要イベント（固定日付型）
    FIXED_DATE_EVENTS = {
        (1, 1): ("new_year", 2.0),  # 元日
        (2, 3): ("setsubun", 1.3),  # 節分
        (2, 14): ("valentine", 1.5),  # バレンタイン
        (3, 3): ("hinamatsuri", 1.2),  # ひな祭り
        (3, 14): ("white_day", 1.3),  # ホワイトデー
        (5, 5): ("kodomo_no_hi", 1.2),  # こどもの日
        (7, 7): ("tanabata", 1.1),  # 七夕
        (10, 31): ("halloween", 1.4),  # ハロウィン
        (12, 24): ("christmas_eve", 1.8),  # クリスマスイブ
        (12, 25): ("christmas", 1.5),  # クリスマス
        (12, 31): ("new_years_eve", 1.6),  # 大晦日
    }

    # 曜日依存イベント（第n週の曜日）
    # (月, 週, 曜日): (イベント名, 影響度)
    FLOATING_EVENTS = {
        (1, 2, 0): ("coming_of_age", 1.2),  # 成人の日（1月第2月曜）
        (7, 3, 0): ("marine_day", 1.1),  # 海の日（7月第3月曜）
        (9, 3, 0): ("respect_for_aged", 1.1),  # 敬老の日（9月第3月曜）
        (10, 2, 0): ("sports_day", 1.1),  # スポーツの日（10月第2月曜）
        (11, 3, 6): ("shichi_go_san", 1.2),  # 七五三に近い週末
    }

    # 季節
    SEASONS = {
        (12, 1, 2): "winter",
        (3, 4, 5): "spring",
        (6, 7, 8): "summer",
        (9, 10, 11): "autumn",
    }

    def __init__(self):
        pass

    def generate_features(
        self,
        dates: List[date],
        events_df: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        カレンダー特徴量を生成

        Args:
            dates: 対象日付リスト
            events_df: イベントデータフレーム（オプション）

        Returns:
            特徴量データフレーム
        """
        features = []

        for d in dates:
            feat = self._generate_date_features(d)

            # カスタムイベント
            if events_df is not None and not events_df.empty:
                event_feat = self._get_event_features(d, events_df)
                feat.update(event_feat)

            features.append(feat)

        return pd.DataFrame(features)

    def _generate_date_features(self, d: date) -> Dict:
        """単一日付の特徴量生成"""
        features = {
            "date": d,
            # 基本日付特徴量
            "year": d.year,
            "month": d.month,
            "day": d.day,
            "day_of_week": d.weekday(),  # 0=月曜日, 6=日曜日
            "day_of_year": d.timetuple().tm_yday,
            "week_of_year": d.isocalendar()[1],
            "week_of_month": (d.day - 1) // 7 + 1,

            # 曜日フラグ
            "is_monday": int(d.weekday() == 0),
            "is_tuesday": int(d.weekday() == 1),
            "is_wednesday": int(d.weekday() == 2),
            "is_thursday": int(d.weekday() == 3),
            "is_friday": int(d.weekday() == 4),
            "is_saturday": int(d.weekday() == 5),
            "is_sunday": int(d.weekday() == 6),
            "is_weekend": int(d.weekday() >= 5),

            # 月初・月末
            "is_month_start": int(d.day <= 3),
            "is_month_end": int(d.day >= 28),
            "is_payday": int(d.day == 25 or (d.day >= 23 and d.weekday() == 4)),

            # 季節
            "season": self._get_season(d.month),
            "is_spring": int(d.month in (3, 4, 5)),
            "is_summer": int(d.month in (6, 7, 8)),
            "is_autumn": int(d.month in (9, 10, 11)),
            "is_winter": int(d.month in (12, 1, 2)),
        }

        # 祝日判定
        holiday_name = jpholiday.is_holiday_name(d)
        features["is_holiday"] = int(holiday_name is not None)
        features["holiday_name"] = holiday_name if holiday_name else ""

        # 連休判定
        features.update(self._get_consecutive_holiday_features(d))

        # 固定日付イベント
        features.update(self._get_fixed_date_event_features(d))

        # 曜日依存イベント
        features.update(self._get_floating_event_features(d))

        # 周期特徴量（サイン・コサイン変換）
        features.update(self._get_cyclical_features(d))

        return features

    def _get_season(self, month: int) -> str:
        """季節判定"""
        if month in (12, 1, 2):
            return "winter"
        elif month in (3, 4, 5):
            return "spring"
        elif month in (6, 7, 8):
            return "summer"
        else:
            return "autumn"

    def _get_consecutive_holiday_features(self, d: date) -> Dict:
        """連休特徴量"""
        # 前後の日が休日かどうか
        prev_holiday = jpholiday.is_holiday(d - timedelta(days=1)) or (d - timedelta(days=1)).weekday() >= 5
        next_holiday = jpholiday.is_holiday(d + timedelta(days=1)) or (d + timedelta(days=1)).weekday() >= 5
        current_holiday = jpholiday.is_holiday(d) or d.weekday() >= 5

        # 連休の長さを計算
        consecutive_days = 0
        if current_holiday:
            # 前方カウント
            temp_date = d
            while jpholiday.is_holiday(temp_date) or temp_date.weekday() >= 5:
                consecutive_days += 1
                temp_date -= timedelta(days=1)
                if consecutive_days > 10:
                    break
            # 後方カウント
            temp_date = d + timedelta(days=1)
            while jpholiday.is_holiday(temp_date) or temp_date.weekday() >= 5:
                consecutive_days += 1
                temp_date += timedelta(days=1)
                if consecutive_days > 10:
                    break

        return {
            "is_holiday_eve": int(not current_holiday and next_holiday),
            "is_holiday_after": int(not current_holiday and prev_holiday),
            "is_golden_week": int(d.month == 5 and d.day <= 7),
            "is_obon": int(d.month == 8 and 10 <= d.day <= 16),
            "is_year_end": int(d.month == 12 and d.day >= 28),
            "is_new_year": int(d.month == 1 and d.day <= 3),
            "consecutive_holiday_days": consecutive_days,
            "is_long_holiday": int(consecutive_days >= 3),
        }

    def _get_fixed_date_event_features(self, d: date) -> Dict:
        """固定日付イベント特徴量"""
        features = {
            "fixed_event_name": "",
            "fixed_event_impact": 1.0,
        }

        key = (d.month, d.day)
        if key in self.FIXED_DATE_EVENTS:
            event_name, impact = self.FIXED_DATE_EVENTS[key]
            features["fixed_event_name"] = event_name
            features["fixed_event_impact"] = impact

        # イベント前後の影響
        for delta in [-3, -2, -1, 1, 2, 3]:
            check_date = d + timedelta(days=delta)
            check_key = (check_date.month, check_date.day)
            if check_key in self.FIXED_DATE_EVENTS:
                event_name, impact = self.FIXED_DATE_EVENTS[check_key]
                # 前後の影響は減衰
                decay = 1.0 - abs(delta) * 0.2
                features[f"event_effect_day{delta:+d}"] = impact * decay

        return features

    def _get_floating_event_features(self, d: date) -> Dict:
        """曜日依存イベント特徴量"""
        features = {
            "floating_event_name": "",
            "floating_event_impact": 1.0,
        }

        # 第n週を計算
        week_of_month = (d.day - 1) // 7 + 1
        key = (d.month, week_of_month, d.weekday())

        if key in self.FLOATING_EVENTS:
            event_name, impact = self.FLOATING_EVENTS[key]
            features["floating_event_name"] = event_name
            features["floating_event_impact"] = impact

        return features

    def _get_cyclical_features(self, d: date) -> Dict:
        """周期的特徴量（サイン・コサイン変換）"""
        day_of_week = d.weekday()
        day_of_month = d.day
        month = d.month
        day_of_year = d.timetuple().tm_yday

        return {
            # 週の周期（7日）
            "dow_sin": np.sin(2 * np.pi * day_of_week / 7),
            "dow_cos": np.cos(2 * np.pi * day_of_week / 7),
            # 月の周期（約30日）
            "dom_sin": np.sin(2 * np.pi * day_of_month / 31),
            "dom_cos": np.cos(2 * np.pi * day_of_month / 31),
            # 年の周期（12ヶ月）
            "month_sin": np.sin(2 * np.pi * month / 12),
            "month_cos": np.cos(2 * np.pi * month / 12),
            # 年の周期（365日）
            "doy_sin": np.sin(2 * np.pi * day_of_year / 365),
            "doy_cos": np.cos(2 * np.pi * day_of_year / 365),
        }

    def _get_event_features(
        self,
        d: date,
        events_df: pd.DataFrame
    ) -> Dict:
        """カスタムイベント特徴量"""
        features = {
            "custom_event_count": 0,
            "custom_event_impact": 1.0,
        }

        # 対象日のイベント
        day_events = events_df[events_df["event_date"] == d]

        if not day_events.empty:
            features["custom_event_count"] = len(day_events)
            features["custom_event_impact"] = day_events["impact_factor"].max()

        # 前後の影響を考慮
        for _, event in events_df.iterrows():
            event_date = event["event_date"]
            pre_effect = event.get("pre_days_effect", 0)
            post_effect = event.get("post_days_effect", 0)

            # イベント前
            if pre_effect > 0:
                for delta in range(1, pre_effect + 1):
                    if event_date - timedelta(days=delta) == d:
                        decay = 1.0 - delta * 0.15
                        features["custom_event_impact"] = max(
                            features["custom_event_impact"],
                            event["impact_factor"] * decay
                        )

            # イベント後
            if post_effect > 0:
                for delta in range(1, post_effect + 1):
                    if event_date + timedelta(days=delta) == d:
                        decay = 1.0 - delta * 0.15
                        features["custom_event_impact"] = max(
                            features["custom_event_impact"],
                            event["impact_factor"] * decay
                        )

        return features

    def generate_lag_features(
        self,
        sales_df: pd.DataFrame,
        target_col: str = "sales_amount",
        group_cols: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        ラグ特徴量・移動平均特徴量を生成

        Args:
            sales_df: 売上データフレーム（sales_date, sales_amount含む）
            target_col: 対象カラム
            group_cols: グループ化カラム（店舗、カテゴリなど）

        Returns:
            ラグ特徴量付きデータフレーム
        """
        df = sales_df.copy()
        df = df.sort_values("sales_date")

        if group_cols:
            grouped = df.groupby(group_cols)
        else:
            grouped = df

        # 同曜日ラグ（1週間前、2週間前、3週間前、4週間前）
        for weeks in [1, 2, 3, 4]:
            lag_days = weeks * 7
            col_name = f"lag_same_dow_{weeks}w"
            if group_cols:
                df[col_name] = grouped[target_col].shift(lag_days)
            else:
                df[col_name] = df[target_col].shift(lag_days)

        # 直近ラグ（1日前〜7日前）
        for lag in range(1, 8):
            col_name = f"lag_{lag}d"
            if group_cols:
                df[col_name] = grouped[target_col].shift(lag)
            else:
                df[col_name] = df[target_col].shift(lag)

        # 移動平均
        for window in [7, 14, 28]:
            col_name = f"ma_{window}d"
            if group_cols:
                df[col_name] = grouped[target_col].transform(
                    lambda x: x.shift(1).rolling(window=window, min_periods=1).mean()
                )
            else:
                df[col_name] = df[target_col].shift(1).rolling(
                    window=window, min_periods=1
                ).mean()

        # 移動標準偏差
        for window in [7, 14, 28]:
            col_name = f"std_{window}d"
            if group_cols:
                df[col_name] = grouped[target_col].transform(
                    lambda x: x.shift(1).rolling(window=window, min_periods=1).std()
                )
            else:
                df[col_name] = df[target_col].shift(1).rolling(
                    window=window, min_periods=1
                ).std()

        # 同曜日移動平均（4週間）
        col_name = "ma_same_dow_4w"
        df[col_name] = (
            df["lag_same_dow_1w"].fillna(0) +
            df["lag_same_dow_2w"].fillna(0) +
            df["lag_same_dow_3w"].fillna(0) +
            df["lag_same_dow_4w"].fillna(0)
        ) / 4

        # 前週比
        df["wow_ratio"] = df[target_col] / df["lag_same_dow_1w"].replace(0, np.nan)

        # 前年同週比（52週前）
        if group_cols:
            df["yoy_lag"] = grouped[target_col].shift(364)
        else:
            df["yoy_lag"] = df[target_col].shift(364)
        df["yoy_ratio"] = df[target_col] / df["yoy_lag"].replace(0, np.nan)

        return df
