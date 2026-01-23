/**
 * 売上予測ダッシュボード JavaScript
 */

// API ベースURL
const API_BASE = '/api/v1';

// グローバル変数
let hierarchyChart = null;
let forecastActualChart = null;

// ==============================
// 初期化
// ==============================

document.addEventListener('DOMContentLoaded', () => {
    initializeDatePicker();
    initializeCharts();
    loadStores();
    loadCategories();
    updateCurrentDate();

    // 初期予測取得
    fetchForecast();
});

/**
 * 日付ピッカーを初期化
 */
function initializeDatePicker() {
    const datePicker = document.getElementById('forecast-date');
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    datePicker.value = formatDate(tomorrow);
}

/**
 * 現在日時を更新
 */
function updateCurrentDate() {
    const dateEl = document.getElementById('current-date');
    const now = new Date();
    dateEl.textContent = now.toLocaleDateString('ja-JP', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        weekday: 'long'
    });
}

// ==============================
// データ取得
// ==============================

/**
 * 予測を取得
 */
async function fetchForecast() {
    const targetDate = document.getElementById('forecast-date').value;
    const horizon = document.getElementById('horizon').value;
    const storeId = document.getElementById('store-select').value;
    const categoryId = document.getElementById('category-select').value;

    try {
        showLoading(true);

        // 予測API呼び出し
        let url = `${API_BASE}/forecast?target_date=${targetDate}&horizon=${horizon}`;
        if (storeId) url += `&store_id=${storeId}`;
        if (categoryId) url += `&category_id=${categoryId}`;

        const response = await fetch(url);
        const data = await response.json();

        // データ表示
        updateSummary(data);
        updateForecastTable(data.forecasts);
        updateHierarchyChart(data);
        updateFactors(targetDate);

        // 精度情報取得
        await fetchAccuracy();

        showLoading(false);
    } catch (error) {
        console.error('Error fetching forecast:', error);
        showToast('予測データの取得に失敗しました');
        showLoading(false);
    }
}

/**
 * 精度情報を取得
 */
async function fetchAccuracy() {
    const endDate = new Date();
    const startDate = new Date();
    startDate.setDate(startDate.getDate() - 30);

    try {
        const url = `${API_BASE}/accuracy?start_date=${formatDate(startDate)}&end_date=${formatDate(endDate)}`;
        const response = await fetch(url);
        const data = await response.json();

        updateAccuracyMetrics(data);
    } catch (error) {
        console.error('Error fetching accuracy:', error);
    }
}

/**
 * 店舗一覧を取得
 */
async function loadStores() {
    try {
        const response = await fetch(`${API_BASE}/stores`);
        const data = await response.json();

        const select = document.getElementById('store-select');
        data.stores.forEach(store => {
            const option = document.createElement('option');
            option.value = store.store_id;
            option.textContent = store.store_name;
            select.appendChild(option);
        });
    } catch (error) {
        console.error('Error loading stores:', error);
    }
}

/**
 * カテゴリ一覧を取得
 */
async function loadCategories() {
    try {
        const response = await fetch(`${API_BASE}/categories`);
        const data = await response.json();

        const select = document.getElementById('category-select');
        data.categories.forEach(cat => {
            const option = document.createElement('option');
            option.value = cat.category_id;
            option.textContent = cat.category_name;
            select.appendChild(option);
        });
    } catch (error) {
        console.error('Error loading categories:', error);
    }
}

// ==============================
// UI更新
// ==============================

/**
 * サマリーを更新
 */
function updateSummary(data) {
    // 全社予測
    const totalForecast = data.forecasts.find(f => f.level === 'company_total');
    if (totalForecast) {
        document.getElementById('total-forecast').textContent =
            formatCurrency(totalForecast.forecast_value);
        document.getElementById('total-range').textContent =
            `予測区間: ${formatCurrency(totalForecast.forecast_lower)} 〜 ${formatCurrency(totalForecast.forecast_upper)}`;

        const badge = document.getElementById('total-confidence');
        badge.textContent = totalForecast.confidence_rank;
        badge.className = `confidence-badge rank-${totalForecast.confidence_rank.toLowerCase()}`;
    }

    // 信頼度分布
    const confDist = data.summary.confidence_distribution || {};
    document.querySelector('.conf-a').textContent = `A: ${confDist.A || 0}`;
    document.querySelector('.conf-b').textContent = `B: ${confDist.B || 0}`;
    document.querySelector('.conf-c').textContent = `C: ${confDist.C || 0}`;
    document.querySelector('.conf-d').textContent = `D: ${confDist.D || 0}`;
    document.querySelector('.conf-e').textContent = `E: ${confDist.E || 0}`;
}

/**
 * 精度メトリクスを更新
 */
function updateAccuracyMetrics(data) {
    document.getElementById('mape-value').textContent =
        `${(data.overall.mape * 100).toFixed(1)}%`;
    document.getElementById('mae-value').textContent =
        formatCurrency(data.overall.mae);
}

/**
 * 予測テーブルを更新
 */
function updateForecastTable(forecasts) {
    const tbody = document.getElementById('forecast-tbody');
    tbody.innerHTML = '';

    forecasts.forEach(f => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${getLevelName(f.level)}</td>
            <td>${f.store_id || '全店舗'}</td>
            <td>${f.category_id || '全カテゴリ'}</td>
            <td>${formatCurrency(f.forecast_value)}</td>
            <td>${formatCurrency(f.forecast_lower)}</td>
            <td>${formatCurrency(f.forecast_upper)}</td>
            <td>${formatCurrency(f.base_forecast)}</td>
            <td>${formatCurrency(f.residual_forecast)}</td>
            <td><span class="confidence-cell rank-${f.confidence_rank.toLowerCase()}">${f.confidence_rank}</span></td>
        `;
        tbody.appendChild(tr);
    });
}

/**
 * 変動要因を更新
 */
function updateFactors(dateStr) {
    const date = new Date(dateStr);
    const dayNames = ['日', '月', '火', '水', '木', '金', '土'];

    document.getElementById('dow-factor').textContent =
        `${dayNames[date.getDay()]}曜日`;

    // TODO: 実際のAPIから取得
    document.getElementById('weather-factor').textContent = '晴れ（影響度: 1.0）';
    document.getElementById('point-factor').textContent = '通常（1倍）';
    document.getElementById('event-factor').textContent = 'なし';
}

// ==============================
// チャート
// ==============================

/**
 * チャートを初期化
 */
function initializeCharts() {
    // 階層別予測チャート
    const hierarchyCtx = document.getElementById('hierarchy-chart').getContext('2d');
    hierarchyChart = new Chart(hierarchyCtx, {
        type: 'bar',
        data: {
            labels: ['全社', '店舗別計', 'カテゴリ別計', '店舗×カテゴリ計'],
            datasets: [{
                label: '予測値',
                data: [0, 0, 0, 0],
                backgroundColor: [
                    'rgba(37, 99, 235, 0.8)',
                    'rgba(59, 130, 246, 0.8)',
                    'rgba(96, 165, 250, 0.8)',
                    'rgba(147, 197, 253, 0.8)'
                ],
                borderRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        callback: value => formatCurrency(value, true)
                    }
                }
            }
        }
    });

    // 予測vs実績チャート
    const forecastActualCtx = document.getElementById('forecast-actual-chart').getContext('2d');
    forecastActualChart = new Chart(forecastActualCtx, {
        type: 'line',
        data: {
            labels: generateDateLabels(7),
            datasets: [
                {
                    label: '予測',
                    data: [9800000, 10200000, 9500000, 11000000, 10800000, 12500000, 11200000],
                    borderColor: 'rgba(37, 99, 235, 1)',
                    backgroundColor: 'rgba(37, 99, 235, 0.1)',
                    fill: true,
                    tension: 0.4
                },
                {
                    label: '実績',
                    data: [10000000, 10100000, 9700000, 10800000, 11000000, 12300000, 11500000],
                    borderColor: 'rgba(16, 185, 129, 1)',
                    backgroundColor: 'transparent',
                    borderDash: [5, 5],
                    tension: 0.4
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom'
                }
            },
            scales: {
                y: {
                    beginAtZero: false,
                    ticks: {
                        callback: value => formatCurrency(value, true)
                    }
                }
            }
        }
    });
}

/**
 * 階層チャートを更新
 */
function updateHierarchyChart(data) {
    const forecasts = data.forecasts;

    const companyTotal = forecasts.find(f => f.level === 'company_total')?.forecast_value || 0;
    const storeTotal = forecasts.filter(f => f.level === 'store_total')
        .reduce((sum, f) => sum + f.forecast_value, 0) || companyTotal;
    const categoryTotal = forecasts.filter(f => f.level === 'company_category')
        .reduce((sum, f) => sum + f.forecast_value, 0) || companyTotal;
    const storeCategoryTotal = forecasts.filter(f => f.level === 'store_category')
        .reduce((sum, f) => sum + f.forecast_value, 0) || companyTotal;

    hierarchyChart.data.datasets[0].data = [
        companyTotal, storeTotal, categoryTotal, storeCategoryTotal
    ];
    hierarchyChart.update();
}

// ==============================
// ユーティリティ
// ==============================

/**
 * 日付をフォーマット
 */
function formatDate(date) {
    return date.toISOString().split('T')[0];
}

/**
 * 通貨フォーマット
 */
function formatCurrency(value, short = false) {
    if (value === null || value === undefined) return '-';

    if (short && value >= 1000000) {
        return `¥${(value / 1000000).toFixed(1)}M`;
    }

    return new Intl.NumberFormat('ja-JP', {
        style: 'currency',
        currency: 'JPY',
        maximumFractionDigits: 0
    }).format(value);
}

/**
 * 階層レベル名を取得
 */
function getLevelName(level) {
    const names = {
        'company_total': '全社トータル',
        'store_total': '店舗別',
        'company_category': 'カテゴリ別',
        'store_category': '店舗×カテゴリ'
    };
    return names[level] || level;
}

/**
 * 日付ラベルを生成
 */
function generateDateLabels(days) {
    const labels = [];
    for (let i = days - 1; i >= 0; i--) {
        const date = new Date();
        date.setDate(date.getDate() - i);
        labels.push(`${date.getMonth() + 1}/${date.getDate()}`);
    }
    return labels;
}

/**
 * ローディング表示
 */
function showLoading(show) {
    // TODO: ローディングオーバーレイ実装
}

/**
 * トースト表示
 */
function showToast(message) {
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(() => {
        toast.remove();
    }, 3000);
}

/**
 * CSV出力
 */
function exportCSV() {
    const table = document.getElementById('forecast-table');
    const rows = table.querySelectorAll('tr');

    let csv = [];
    rows.forEach(row => {
        const cols = row.querySelectorAll('th, td');
        const rowData = Array.from(cols).map(col => col.textContent);
        csv.push(rowData.join(','));
    });

    const blob = new Blob([csv.join('\n')], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `forecast_${document.getElementById('forecast-date').value}.csv`;
    link.click();
}
