"""
階層整合モジュール
上位階層を信頼し、下位階層を補正する
"""
import pandas as pd
import numpy as np
from datetime import date
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass


@dataclass
class HierarchyNode:
    """階層ノード"""
    level: str
    store_id: Optional[str]
    category_id: Optional[str]
    forecast: float
    weight: float
    children: List["HierarchyNode"] = None

    def __post_init__(self):
        if self.children is None:
            self.children = []


class HierarchicalReconciliation:
    """
    階層整合クラス

    優先順位（設計思想）:
    1. 全店舗のトータル売上 → 最も信頼度が高い
    2. 店舗別トータル & 全店舗カテゴリー別 → 中程度
    3. 店舗×カテゴリー & 全店舗クラス別 → 下位階層ほど乱れやすい

    「大きな数字を信頼し、小さな数字を補正する」
    """

    # 階層レベルと重み
    DEFAULT_WEIGHTS = {
        "company_total": 1.0,      # 全社トータル
        "store_total": 0.8,        # 店舗別トータル
        "company_category": 0.8,   # 全社カテゴリー別
        "store_category": 0.6,     # 店舗×カテゴリー
        "company_class": 0.6,      # 全社クラス別
        "store_class": 0.4,        # 店舗×クラス
    }

    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
        reconciliation_method: str = "top_down_weighted"
    ):
        """
        Args:
            weights: 各階層の重み
            reconciliation_method: 整合方法
                - "top_down": 完全トップダウン（上位に完全に合わせる）
                - "top_down_weighted": 重み付きトップダウン
                - "middle_out": 中間階層を基準に上下を調整
        """
        self.weights = weights or self.DEFAULT_WEIGHTS
        self.reconciliation_method = reconciliation_method

    def reconcile(
        self,
        forecasts: Dict[str, pd.DataFrame],
        target_date: date
    ) -> Dict[str, pd.DataFrame]:
        """
        階層間の整合を実行

        Args:
            forecasts: 階層別予測データフレーム
                - company_total: [date, forecast]
                - store_total: [date, store_id, forecast]
                - company_category: [date, category_id, forecast]
                - store_category: [date, store_id, category_id, forecast]

        Returns:
            整合後の予測データフレーム（同じ構造）
        """
        if self.reconciliation_method == "top_down":
            return self._top_down_reconciliation(forecasts, target_date)
        elif self.reconciliation_method == "top_down_weighted":
            return self._top_down_weighted_reconciliation(forecasts, target_date)
        elif self.reconciliation_method == "middle_out":
            return self._middle_out_reconciliation(forecasts, target_date)
        else:
            return forecasts

    def _top_down_reconciliation(
        self,
        forecasts: Dict[str, pd.DataFrame],
        target_date: date
    ) -> Dict[str, pd.DataFrame]:
        """
        完全トップダウン整合
        上位の予測値を下位に比例配分
        """
        reconciled = {}

        # 1. 全社トータルはそのまま
        company_total = forecasts.get("company_total", pd.DataFrame())
        if not company_total.empty:
            total_forecast = company_total[
                company_total["date"] == target_date
            ]["forecast"].values
            total_forecast = total_forecast[0] if len(total_forecast) > 0 else 0
        else:
            total_forecast = 0

        reconciled["company_total"] = company_total.copy()

        # 2. 店舗別トータルを比例配分
        store_total = forecasts.get("store_total", pd.DataFrame())
        if not store_total.empty and total_forecast > 0:
            store_df = store_total[store_total["date"] == target_date].copy()
            store_sum = store_df["forecast"].sum()
            if store_sum > 0:
                store_df["forecast"] = store_df["forecast"] / store_sum * total_forecast
            reconciled["store_total"] = store_df
        else:
            reconciled["store_total"] = store_total.copy()

        # 3. 全社カテゴリー別を比例配分
        company_category = forecasts.get("company_category", pd.DataFrame())
        if not company_category.empty and total_forecast > 0:
            cat_df = company_category[company_category["date"] == target_date].copy()
            cat_sum = cat_df["forecast"].sum()
            if cat_sum > 0:
                cat_df["forecast"] = cat_df["forecast"] / cat_sum * total_forecast
            reconciled["company_category"] = cat_df
        else:
            reconciled["company_category"] = company_category.copy()

        # 4. 店舗×カテゴリーを店舗別トータルに合わせる
        store_category = forecasts.get("store_category", pd.DataFrame())
        if not store_category.empty and "store_total" in reconciled:
            sc_df = store_category[store_category["date"] == target_date].copy()
            store_totals = reconciled["store_total"].set_index("store_id")["forecast"]

            for store_id in sc_df["store_id"].unique():
                store_mask = sc_df["store_id"] == store_id
                store_sum = sc_df.loc[store_mask, "forecast"].sum()
                target_total = store_totals.get(store_id, store_sum)

                if store_sum > 0:
                    sc_df.loc[store_mask, "forecast"] = (
                        sc_df.loc[store_mask, "forecast"] / store_sum * target_total
                    )

            reconciled["store_category"] = sc_df
        else:
            reconciled["store_category"] = store_category.copy()

        return reconciled

    def _top_down_weighted_reconciliation(
        self,
        forecasts: Dict[str, pd.DataFrame],
        target_date: date
    ) -> Dict[str, pd.DataFrame]:
        """
        重み付きトップダウン整合
        上位の予測と下位の予測を重み付けで調整
        """
        reconciled = {}

        # 1. 全社トータル（重み1.0）
        company_total = forecasts.get("company_total", pd.DataFrame())
        if not company_total.empty:
            total_df = company_total[company_total["date"] == target_date].copy()
            total_forecast = total_df["forecast"].values[0] if len(total_df) > 0 else 0
        else:
            total_forecast = 0
            total_df = pd.DataFrame()

        reconciled["company_total"] = total_df

        # 2. 店舗別トータル（重み0.8）
        store_total = forecasts.get("store_total", pd.DataFrame())
        if not store_total.empty:
            store_df = store_total[store_total["date"] == target_date].copy()
            store_sum = store_df["forecast"].sum()

            if store_sum > 0 and total_forecast > 0:
                # 調整係数
                adjustment = total_forecast / store_sum
                # 重み付き調整（完全には上位に合わせない）
                weight = self.weights.get("store_total", 0.8)
                weighted_adjustment = 1 + (adjustment - 1) * weight
                store_df["forecast"] = store_df["forecast"] * weighted_adjustment

            reconciled["store_total"] = store_df
        else:
            reconciled["store_total"] = store_total.copy()

        # 3. 全社カテゴリー別（重み0.8）
        company_category = forecasts.get("company_category", pd.DataFrame())
        if not company_category.empty:
            cat_df = company_category[company_category["date"] == target_date].copy()
            cat_sum = cat_df["forecast"].sum()

            if cat_sum > 0 and total_forecast > 0:
                adjustment = total_forecast / cat_sum
                weight = self.weights.get("company_category", 0.8)
                weighted_adjustment = 1 + (adjustment - 1) * weight
                cat_df["forecast"] = cat_df["forecast"] * weighted_adjustment

            reconciled["company_category"] = cat_df
        else:
            reconciled["company_category"] = company_category.copy()

        # 4. 店舗×カテゴリー（重み0.6）
        store_category = forecasts.get("store_category", pd.DataFrame())
        if not store_category.empty and "store_total" in reconciled:
            sc_df = store_category[store_category["date"] == target_date].copy()

            # 店舗別に調整
            if not reconciled["store_total"].empty:
                store_totals = reconciled["store_total"].set_index("store_id")["forecast"]
                weight = self.weights.get("store_category", 0.6)

                for store_id in sc_df["store_id"].unique():
                    store_mask = sc_df["store_id"] == store_id
                    store_sum = sc_df.loc[store_mask, "forecast"].sum()
                    target_total = store_totals.get(store_id, store_sum)

                    if store_sum > 0:
                        adjustment = target_total / store_sum
                        weighted_adjustment = 1 + (adjustment - 1) * weight
                        sc_df.loc[store_mask, "forecast"] = (
                            sc_df.loc[store_mask, "forecast"] * weighted_adjustment
                        )

            reconciled["store_category"] = sc_df
        else:
            reconciled["store_category"] = store_category.copy()

        return reconciled

    def _middle_out_reconciliation(
        self,
        forecasts: Dict[str, pd.DataFrame],
        target_date: date
    ) -> Dict[str, pd.DataFrame]:
        """
        中間階層基準の整合
        店舗別トータルを基準に、上位（全社）と下位（カテゴリ）を調整
        """
        reconciled = {}

        # 1. 店舗別トータルを基準とする
        store_total = forecasts.get("store_total", pd.DataFrame())
        if not store_total.empty:
            store_df = store_total[store_total["date"] == target_date].copy()
            store_sum = store_df["forecast"].sum()
        else:
            store_df = pd.DataFrame()
            store_sum = 0

        reconciled["store_total"] = store_df

        # 2. 全社トータルを店舗合計に合わせる
        company_total = forecasts.get("company_total", pd.DataFrame())
        if not company_total.empty:
            total_df = company_total[company_total["date"] == target_date].copy()
            if not total_df.empty and store_sum > 0:
                original_total = total_df["forecast"].values[0]
                # 上位は部分的に調整（急激な変更を避ける）
                adjusted_total = original_total * 0.3 + store_sum * 0.7
                total_df["forecast"] = adjusted_total

            reconciled["company_total"] = total_df
        else:
            reconciled["company_total"] = pd.DataFrame({
                "date": [target_date],
                "forecast": [store_sum]
            })

        # 3. カテゴリ別は店舗トータルに比例配分
        store_category = forecasts.get("store_category", pd.DataFrame())
        if not store_category.empty and not store_df.empty:
            sc_df = store_category[store_category["date"] == target_date].copy()
            store_totals = store_df.set_index("store_id")["forecast"]

            for store_id in sc_df["store_id"].unique():
                store_mask = sc_df["store_id"] == store_id
                store_sum_cat = sc_df.loc[store_mask, "forecast"].sum()
                target_total = store_totals.get(store_id, store_sum_cat)

                if store_sum_cat > 0:
                    sc_df.loc[store_mask, "forecast"] = (
                        sc_df.loc[store_mask, "forecast"] / store_sum_cat * target_total
                    )

            reconciled["store_category"] = sc_df
        else:
            reconciled["store_category"] = store_category.copy()

        # 4. 全社カテゴリー別は店舗×カテゴリーの合計から算出
        if "store_category" in reconciled and not reconciled["store_category"].empty:
            cat_df = reconciled["store_category"].groupby("category_id").agg({
                "forecast": "sum"
            }).reset_index()
            cat_df["date"] = target_date
            reconciled["company_category"] = cat_df
        else:
            reconciled["company_category"] = forecasts.get(
                "company_category", pd.DataFrame()
            ).copy()

        return reconciled

    def validate_hierarchy(
        self,
        reconciled: Dict[str, pd.DataFrame],
        tolerance: float = 0.01
    ) -> Dict[str, Any]:
        """
        階層整合性を検証

        Args:
            reconciled: 整合後の予測
            tolerance: 許容誤差

        Returns:
            検証結果
        """
        results = {
            "is_valid": True,
            "errors": [],
            "summary": {}
        }

        # 全社トータル
        company_total = reconciled.get("company_total", pd.DataFrame())
        if not company_total.empty:
            total_val = company_total["forecast"].sum()
            results["summary"]["company_total"] = total_val
        else:
            total_val = 0

        # 店舗別合計と全社トータルの比較
        store_total = reconciled.get("store_total", pd.DataFrame())
        if not store_total.empty:
            store_sum = store_total["forecast"].sum()
            results["summary"]["store_total_sum"] = store_sum

            if total_val > 0:
                diff_ratio = abs(store_sum - total_val) / total_val
                if diff_ratio > tolerance:
                    results["is_valid"] = False
                    results["errors"].append(
                        f"Store total sum ({store_sum:.0f}) differs from "
                        f"company total ({total_val:.0f}) by {diff_ratio:.2%}"
                    )

        # カテゴリ別合計と全社トータルの比較
        company_category = reconciled.get("company_category", pd.DataFrame())
        if not company_category.empty:
            cat_sum = company_category["forecast"].sum()
            results["summary"]["company_category_sum"] = cat_sum

            if total_val > 0:
                diff_ratio = abs(cat_sum - total_val) / total_val
                if diff_ratio > tolerance:
                    results["is_valid"] = False
                    results["errors"].append(
                        f"Category sum ({cat_sum:.0f}) differs from "
                        f"company total ({total_val:.0f}) by {diff_ratio:.2%}"
                    )

        return results

    def get_reconciliation_report(
        self,
        original: Dict[str, pd.DataFrame],
        reconciled: Dict[str, pd.DataFrame]
    ) -> pd.DataFrame:
        """
        整合前後の比較レポートを生成

        Args:
            original: 整合前の予測
            reconciled: 整合後の予測

        Returns:
            比較レポート
        """
        report_data = []

        for level in ["company_total", "store_total", "company_category", "store_category"]:
            orig = original.get(level, pd.DataFrame())
            recon = reconciled.get(level, pd.DataFrame())

            if not orig.empty and not recon.empty:
                orig_sum = orig["forecast"].sum()
                recon_sum = recon["forecast"].sum()
                change = recon_sum - orig_sum
                change_pct = (change / orig_sum * 100) if orig_sum > 0 else 0

                report_data.append({
                    "level": level,
                    "original_sum": orig_sum,
                    "reconciled_sum": recon_sum,
                    "change": change,
                    "change_pct": change_pct,
                    "weight": self.weights.get(level, 0),
                })

        return pd.DataFrame(report_data)
