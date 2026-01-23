"""
サンプルデータ生成スクリプト
テスト・デモ用のダミーデータを生成
"""
import pandas as pd
import numpy as np
from datetime import date, datetime, timedelta
import random
import os


def generate_sample_data(
    start_date: date = date(2021, 1, 1),
    end_date: date = date(2023, 12, 31),
    n_stores: int = 10,
    n_categories: int = 5,
    output_dir: str = "."
):
    """
    サンプルデータを生成

    Args:
        start_date: 開始日
        end_date: 終了日
        n_stores: 店舗数
        n_categories: カテゴリ数
        output_dir: 出力ディレクトリ
    """
    np.random.seed(42)
    random.seed(42)

    # 店舗マスタ
    stores = []
    for i in range(n_stores):
        stores.append({
            "store_id": f"S{i+1:03d}",
            "store_name": f"店舗{chr(65+i)}",
            "area": random.choice(["東京", "神奈川", "千葉", "埼玉"]),
            "store_type": random.choice(["大型", "中型", "小型"]),
        })
    stores_df = pd.DataFrame(stores)
    stores_df.to_csv(os.path.join(output_dir, "stores.csv"), index=False)
    print(f"Generated {len(stores_df)} stores")

    # カテゴリマスタ
    categories = [
        {"category_id": "C01", "category_name": "青果", "level": 1},
        {"category_id": "C02", "category_name": "鮮魚", "level": 1},
        {"category_id": "C03", "category_name": "精肉", "level": 1},
        {"category_id": "C04", "category_name": "惣菜", "level": 1},
        {"category_id": "C05", "category_name": "日配", "level": 1},
    ][:n_categories]
    categories_df = pd.DataFrame(categories)
    categories_df.to_csv(os.path.join(output_dir, "categories.csv"), index=False)
    print(f"Generated {len(categories_df)} categories")

    # 売上データ生成
    print("Generating sales data...")
    dates = pd.date_range(start_date, end_date, freq="D")
    sales_data = []

    # 基本パラメータ
    base_sales = {
        "C01": 200000,  # 青果
        "C02": 150000,  # 鮮魚
        "C03": 180000,  # 精肉
        "C04": 120000,  # 惣菜
        "C05": 100000,  # 日配
    }

    # 曜日係数
    dow_effect = {
        0: 0.90,  # 月
        1: 0.85,  # 火
        2: 0.95,  # 水
        3: 0.90,  # 木
        4: 1.05,  # 金
        5: 1.25,  # 土
        6: 1.10,  # 日
    }

    # 月係数
    month_effect = {
        1: 1.10,  # 正月
        2: 0.95,
        3: 1.00,
        4: 1.00,
        5: 1.05,  # GW
        6: 0.95,
        7: 1.00,
        8: 1.05,  # お盆
        9: 0.95,
        10: 1.00,
        11: 1.00,
        12: 1.20,  # 年末
    }

    for d in dates:
        dow = d.weekday()
        month = d.month

        for store in stores:
            store_factor = np.random.normal(1.0, 0.1)  # 店舗差

            for cat in categories:
                cat_id = cat["category_id"]
                base = base_sales.get(cat_id, 100000)

                # 売上計算
                sales = (
                    base
                    * dow_effect[dow]
                    * month_effect[month]
                    * store_factor
                    * np.random.normal(1.0, 0.08)  # ランダム変動
                )

                # 祝日効果
                if d.weekday() >= 5 or is_holiday(d.date()):
                    sales *= np.random.normal(1.1, 0.05)

                # 天候効果（ランダム）
                if np.random.random() < 0.15:  # 15%で雨
                    sales *= np.random.normal(0.92, 0.03)

                sales_data.append({
                    "sales_date": d.date(),
                    "store_id": store["store_id"],
                    "category_id": cat_id,
                    "sales_amount": max(0, int(sales)),
                })

    sales_df = pd.DataFrame(sales_data)
    sales_df.to_csv(os.path.join(output_dir, "sales.csv"), index=False)
    print(f"Generated {len(sales_df)} sales records")

    # 天候データ生成
    print("Generating weather data...")
    weather_data = []
    for d in dates:
        # 季節ごとの基本気温
        month = d.month
        if month in [12, 1, 2]:
            base_temp = 5
        elif month in [3, 4, 5]:
            base_temp = 15
        elif month in [6, 7, 8]:
            base_temp = 28
        else:
            base_temp = 18

        temp = base_temp + np.random.normal(0, 3)
        is_rain = np.random.random() < 0.15
        precip = np.random.exponential(10) if is_rain else 0

        weather_data.append({
            "date": d.date(),
            "area": "関東",
            "temperature_max": temp + 5,
            "temperature_min": temp - 5,
            "temperature_avg": temp,
            "precipitation": round(precip, 1),
            "is_rain": int(is_rain),
            "weather_type": "rain" if is_rain else "sunny",
        })

    weather_df = pd.DataFrame(weather_data)
    weather_df.to_csv(os.path.join(output_dir, "weather.csv"), index=False)
    print(f"Generated {len(weather_df)} weather records")

    # ポイント政策データ
    print("Generating point policies...")
    policies = [
        {
            "policy_id": "P001",
            "policy_name": "毎週火曜ポイント2倍",
            "start_date": start_date,
            "end_date": end_date,
            "point_rate": 2.0,
            "target_day_of_week": 1,  # 火曜日
        },
        {
            "policy_id": "P002",
            "policy_name": "毎週日曜ポイント3倍",
            "start_date": start_date,
            "end_date": end_date,
            "point_rate": 3.0,
            "target_day_of_week": 6,  # 日曜日
        },
    ]
    policies_df = pd.DataFrame(policies)
    policies_df.to_csv(os.path.join(output_dir, "point_policies.csv"), index=False)
    print(f"Generated {len(policies_df)} point policies")

    # イベントカレンダー
    print("Generating events...")
    events = []
    for year in range(start_date.year, end_date.year + 1):
        events.extend([
            {"event_date": date(year, 1, 1), "event_name": "元日", "event_type": "fixed_date", "impact_factor": 1.5},
            {"event_date": date(year, 2, 3), "event_name": "節分", "event_type": "fixed_date", "impact_factor": 1.3},
            {"event_date": date(year, 2, 14), "event_name": "バレンタイン", "event_type": "fixed_date", "impact_factor": 1.4},
            {"event_date": date(year, 3, 14), "event_name": "ホワイトデー", "event_type": "fixed_date", "impact_factor": 1.3},
            {"event_date": date(year, 12, 24), "event_name": "クリスマスイブ", "event_type": "fixed_date", "impact_factor": 1.6},
            {"event_date": date(year, 12, 25), "event_name": "クリスマス", "event_type": "fixed_date", "impact_factor": 1.4},
            {"event_date": date(year, 12, 31), "event_name": "大晦日", "event_type": "fixed_date", "impact_factor": 1.5},
        ])
    events_df = pd.DataFrame(events)
    events_df.to_csv(os.path.join(output_dir, "events.csv"), index=False)
    print(f"Generated {len(events_df)} events")

    print("\nSample data generation complete!")
    return {
        "stores": stores_df,
        "categories": categories_df,
        "sales": sales_df,
        "weather": weather_df,
        "policies": policies_df,
        "events": events_df,
    }


def is_holiday(d: date) -> bool:
    """簡易祝日判定"""
    try:
        import jpholiday
        return jpholiday.is_holiday(d)
    except ImportError:
        # jpholidayがない場合は簡易判定
        holidays = [
            (1, 1), (1, 2), (1, 3),  # 正月
            (2, 11),  # 建国記念日
            (2, 23),  # 天皇誕生日
            (3, 21),  # 春分の日（概算）
            (4, 29),  # 昭和の日
            (5, 3), (5, 4), (5, 5),  # GW
            (7, 20),  # 海の日（概算）
            (8, 11),  # 山の日
            (9, 15),  # 敬老の日（概算）
            (9, 23),  # 秋分の日（概算）
            (10, 10),  # スポーツの日（概算）
            (11, 3),  # 文化の日
            (11, 23),  # 勤労感謝の日
        ]
        return (d.month, d.day) in holidays


if __name__ == "__main__":
    output_dir = os.path.dirname(os.path.abspath(__file__))
    generate_sample_data(output_dir=output_dir)
