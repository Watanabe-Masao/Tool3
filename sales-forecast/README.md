# スーパーマーケット売上予測システム

2段階予測 × 階層整合モデルによる部門売上予測アプリケーション

## 概要

本システムは、スーパーマーケット部門の売上を**全社 → 店舗 → カテゴリ**の階層で整合させながら、翌日・週次・月次の売上予測を提供します。

## 特徴

### 2段階予測モデル

1. **ベース予測（安定成分）**: 曜日・季節・トレンドなどの周期的パターン
2. **残差予測（変動成分）**: 天候・ポイント政策・イベントなどの外部要因

### 階層整合

予測は以下の優先順位で整合されます：

1. **全社トータル** → 最も信頼度が高い（ウエイト: 1.0）
2. **店舗別トータル & 全社カテゴリー別** → 中程度（ウエイト: 0.8）
3. **店舗×カテゴリー** → 下位階層ほど乱れやすい（ウエイト: 0.6）

### 設計思想

- 大きな数字を信頼する
- 小さな数字は補正する
- 当てに行かず、外さない

## システム構成

```
sales-forecast/
├── config/                 # 設定ファイル
│   └── settings.py
├── data/
│   ├── sample/            # サンプルデータ
│   └── models/            # 学習済みモデル
├── src/
│   ├── api/               # FastAPI エンドポイント
│   │   └── routes.py
│   ├── database/          # データベース定義
│   │   ├── schemas.py
│   │   └── repository.py
│   ├── features/          # 特徴量生成
│   │   ├── calendar_features.py
│   │   ├── weather_features.py
│   │   ├── promotion_features.py
│   │   └── feature_pipeline.py
│   ├── models/            # 予測モデル
│   │   ├── base_forecast.py
│   │   ├── residual_forecast.py
│   │   ├── hierarchical_reconciliation.py
│   │   ├── confidence_evaluator.py
│   │   └── forecast_engine.py
│   └── main.py            # アプリケーション
├── frontend/              # ダッシュボード
│   ├── index.html
│   ├── css/
│   └── js/
├── tests/                 # テスト
└── requirements.txt
```

## セットアップ

### 1. 環境構築

```bash
# Python仮想環境作成
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# パッケージインストール
pip install -r requirements.txt
```

### 2. 起動

```bash
# 開発サーバー起動
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. アクセス

- ダッシュボード: http://localhost:8000/
- APIドキュメント: http://localhost:8000/api/docs
- ReDoc: http://localhost:8000/api/redoc

## API仕様

### 予測取得

```
GET /api/v1/forecast
```

**パラメータ:**
- `target_date` (必須): 予測対象日 (YYYY-MM-DD)
- `horizon`: 予測期間 (daily/weekly/monthly)
- `level`: 階層レベル (company_total/store_total/company_category/store_category)
- `store_id`: 店舗ID
- `category_id`: カテゴリID

**レスポンス:**
```json
{
  "status": "success",
  "forecasts": [
    {
      "forecast_date": "2024-01-20",
      "level": "company_total",
      "forecast_value": 10000000,
      "forecast_lower": 9500000,
      "forecast_upper": 10500000,
      "base_forecast": 9800000,
      "residual_forecast": 200000,
      "confidence_rank": "A",
      "confidence_score": 0.92
    }
  ]
}
```

### 精度情報取得

```
GET /api/v1/accuracy
```

**パラメータ:**
- `start_date` (必須): 評価開始日
- `end_date` (必須): 評価終了日
- `level`: 階層レベル

## 特徴量

### ベース予測用特徴量（安定成分）

- **曜日特徴量**: 曜日フラグ、週末フラグ、サイン/コサイン変換
- **月・季節特徴量**: 月初/月末、給料日、季節フラグ
- **祝日特徴量**: 祝日フラグ、連休、ゴールデンウィーク、お盆、年末年始
- **イベント特徴量**: 固定日付イベント、曜日依存イベント
- **ラグ特徴量**: 同曜日ラグ(1〜4週)、移動平均(7/14/28日)、前年同週

### 残差予測用特徴量（変動成分）

- **天候特徴量**: 気温、降水量、天気タイプ、気温変化
- **ポイント政策**: ポイント倍率、ポイントアップフラグ
- **直近ラグ**: 1〜3日前の売上

## 信頼度ランク

| ランク | 精度水準 | 予測区間幅 |
|--------|----------|------------|
| A | 95%以上 | ±5% |
| B | 90%以上 | ±10% |
| C | 85%以上 | ±15% |
| D | 80%以上 | ±20% |
| E | 80%未満 | ±30% |

## データ要件

- **推奨データ期間**: 過去3年間
- **必須データ**: 日次売上（店舗×カテゴリ）
- **オプションデータ**: 天候、ポイント政策、イベント

## 運用

### 日次バッチ

1. 売上実績データ取得
2. 天候予報データ取得
3. 予測実行
4. 結果保存
5. 前日予測精度評価・更新

### 月次モデル再学習

1. 過去3年間データ収集
2. 特徴量再生成
3. モデル再学習
4. 精度検証
5. モデル入れ替え

## ライセンス

MIT License
