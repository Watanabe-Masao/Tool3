// Firebase imports
import * as FirebaseSync from './firebase';
// Database constants
const DB_NAME = 'VegetableOrderDB';
const DB_VERSION = 3;
const STORE_NAME = 'savedData';
// Database connection
let db = null;
// Long-press duration for cell range selection (ms)
const LONG_PRESS_DURATION = 300;
/**
 * Initialize IndexedDB database
 */
async function initDatabase() {
    return new Promise((resolve, reject) => {
        const req = indexedDB.open(DB_NAME, DB_VERSION);
        req.onerror = () => reject(req.error);
        req.onsuccess = () => {
            db = req.result;
            resolve(db);
        };
        req.onupgradeneeded = (e) => {
            const target = e.target;
            const database = target.result;
            if (!database.objectStoreNames.contains(STORE_NAME)) {
                database.createObjectStore(STORE_NAME, { keyPath: 'id', autoIncrement: true });
            }
        };
    });
}
/**
 * Get all saved data from IndexedDB
 */
async function getSavedList() {
    return new Promise((resolve, reject) => {
        if (!db) {
            reject(new Error('Database not initialized'));
            return;
        }
        const transaction = db.transaction(STORE_NAME, 'readonly');
        const store = transaction.objectStore(STORE_NAME);
        const request = store.getAll();
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
    });
}
/**
 * Save data to IndexedDB
 */
async function saveData(name, data) {
    return new Promise((resolve, reject) => {
        if (!db) {
            reject(new Error('Database not initialized'));
            return;
        }
        const transaction = db.transaction(STORE_NAME, 'readwrite');
        const store = transaction.objectStore(STORE_NAME);
        const request = store.add({
            name,
            savedAt: new Date().toISOString(),
            ...data
        });
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
    });
}
/**
 * Load data from IndexedDB
 */
async function loadData(id) {
    return new Promise((resolve, reject) => {
        if (!db) {
            reject(new Error('Database not initialized'));
            return;
        }
        const transaction = db.transaction(STORE_NAME, 'readonly');
        const store = transaction.objectStore(STORE_NAME);
        const request = store.get(id);
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
    });
}
/**
 * Delete data from IndexedDB
 */
async function deleteData(id) {
    return new Promise((resolve, reject) => {
        if (!db) {
            reject(new Error('Database not initialized'));
            return;
        }
        const transaction = db.transaction(STORE_NAME, 'readwrite');
        const store = transaction.objectStore(STORE_NAME);
        const request = store.delete(id);
        request.onsuccess = () => resolve();
        request.onerror = () => reject(request.error);
    });
}
/**
 * Render saved data list
 * @returns {Promise<void>}
 */
async function renderSavedList() {
    try {
        const list = await getSavedList();
        const el = document.getElementById('saved-list');
        if (!el)
            return;
        if (list.length === 0) {
            el.innerHTML = '<div class="no-saved">保存データなし</div>';
            return;
        }
        el.innerHTML = list.map(item => {
            const d = new Date(item.savedAt);
            const dateStr = `${d.getMonth() + 1}/${d.getDate()} ${d.getHours()}:${String(d.getMinutes()).padStart(2, '0')}`;
            return `<div class="saved-item" onclick="loadFromDB(${item.id})">
        <span class="name">${escapeHtml(item.name)}</span>
        <span class="meta">${dateStr}</span>
        <span class="del-btn" onclick="event.stopPropagation();deleteFromDB(${item.id})">✕</span>
      </div>`;
        }).join('');
    }
    catch (error) {
        console.error('Failed to render saved list:', error);
    }
}
function toggleSavedList() { const l = document.getElementById('saved-list'), t = document.getElementById('saved-toggle'); l.classList.toggle('show'); t.textContent = l.classList.contains('show') ? '▲' : '▼'; }
function toggleTagStats() { const b = document.getElementById('tag-stats-body'), t = document.getElementById('tag-stats-toggle'); b.classList.toggle('show'); t.textContent = b.classList.contains('show') ? '▲' : '▼'; }
function toggleFilesBar() { const b = document.getElementById('files-bar-body'), t = document.getElementById('files-bar-toggle'); b.classList.toggle('show'); t.textContent = b.classList.contains('show') ? '▲' : '▼'; }
function showSaveModal() {
    if (loadedFiles.length === 0) {
        showToast('データがありません');
        return;
    }
    document.getElementById('save-name').value = loadedFiles.map(f => f.name.replace(/\.[^.]+$/, '')).join(', ');
    document.getElementById('save-modal').classList.add('show');
}
function closeSaveModal() { document.getElementById('save-modal').classList.remove('show'); }
function showAddProductModal() {
    document.getElementById('add-product-name').value = '';
    document.getElementById('add-product-cost').value = '';
    document.getElementById('add-product-price').value = '';
    document.getElementById('add-product-unit').value = '';
    document.getElementById('add-product-tag1').value = '';
    document.getElementById('add-product-tag2').value = '';
    document.getElementById('add-product-tag3').value = '';
    updateTagDatalist();
    // Initialize calendar to current month or first available date
    const today = new Date();
    if (currentDates.length > 0) {
        const firstDate = new Date(currentDates[0]);
        calendarYear = firstDate.getFullYear();
        calendarMonth = firstDate.getMonth();
    }
    else {
        calendarYear = today.getFullYear();
        calendarMonth = today.getMonth();
    }
    calendarQuantities = {};
    renderCalendar();
    document.getElementById('add-product-modal').classList.add('show');
    document.getElementById('add-product-name').focus();
}
function closeAddProductModal() {
    document.getElementById('add-product-modal').classList.remove('show');
    calendarQuantities = {};
}
/**
 * Show help modal
 */
function showHelpModal() {
    document.getElementById('help-modal').classList.add('show');
}
/**
 * Close help modal
 */
function closeHelpModal() {
    document.getElementById('help-modal').classList.remove('show');
}
/**
 * Render calendar for add product modal
 */
function renderCalendar() {
    const monthYear = document.getElementById('calendar-month-year');
    const daysContainer = document.getElementById('calendar-days');
    // Month/year header
    const monthNames = ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月'];
    monthYear.textContent = `${calendarYear}年 ${monthNames[calendarMonth]}`;
    // Get first day of month and total days
    const firstDay = new Date(calendarYear, calendarMonth, 1);
    const lastDay = new Date(calendarYear, calendarMonth + 1, 0);
    const daysInMonth = lastDay.getDate();
    const startDayOfWeek = firstDay.getDay(); // 0 = Sunday
    // Get previous month's last days
    const prevMonthLastDay = new Date(calendarYear, calendarMonth, 0);
    const prevMonthDays = prevMonthLastDay.getDate();
    // Today for highlighting
    const today = new Date();
    const todayStr = formatDate(today);
    daysContainer.innerHTML = '';
    // Previous month's trailing days
    for (let i = startDayOfWeek - 1; i >= 0; i--) {
        const day = prevMonthDays - i;
        const cell = createCalendarDayCell(day, true, -1);
        daysContainer.appendChild(cell);
    }
    // Current month days
    for (let day = 1; day <= daysInMonth; day++) {
        const date = new Date(calendarYear, calendarMonth, day);
        const dateStr = formatDate(date);
        const dayOfWeek = date.getDay();
        const isToday = dateStr === todayStr;
        const cell = createCalendarDayCell(day, false, dayOfWeek, dateStr, isToday);
        daysContainer.appendChild(cell);
    }
    // Next month's leading days
    const totalCells = daysContainer.children.length;
    const remainingCells = 42 - totalCells; // 6 rows * 7 days
    for (let day = 1; day <= remainingCells && day <= 14; day++) {
        const cell = createCalendarDayCell(day, true, 1);
        daysContainer.appendChild(cell);
    }
}
/**
 * Format date as YYYY/MM/DD
 */
function formatDate(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}/${month}/${day}`;
}
/**
 * Create a single calendar day cell
 */
function createCalendarDayCell(day, isOtherMonth, dayOfWeek, dateStr, isToday) {
    const cell = document.createElement('div');
    cell.className = 'calendar-day';
    if (isOtherMonth) {
        cell.classList.add('other-month');
    }
    if (isToday) {
        cell.classList.add('today');
    }
    if (dayOfWeek === 0) {
        cell.classList.add('sunday');
    }
    else if (dayOfWeek === 6) {
        cell.classList.add('saturday');
    }
    // Day number
    const dayNumber = document.createElement('div');
    dayNumber.className = 'calendar-day-number';
    dayNumber.textContent = String(day);
    cell.appendChild(dayNumber);
    // Quantity input (only for current month)
    if (!isOtherMonth && dateStr) {
        const input = document.createElement('input');
        input.type = 'number';
        input.className = 'calendar-day-input';
        input.placeholder = '-';
        input.min = '0';
        input.step = '1';
        input.dataset.date = dateStr;
        // Restore value if exists
        if (calendarQuantities[dateStr]) {
            input.value = String(calendarQuantities[dateStr]);
        }
        // Save on input
        input.addEventListener('input', function () {
            const qty = parseInt(input.value);
            if (qty > 0) {
                calendarQuantities[dateStr] = qty;
            }
            else {
                delete calendarQuantities[dateStr];
            }
        });
        // Enter key moves to next cell
        input.addEventListener('keydown', function (e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                const allInputs = Array.from(document.querySelectorAll('.calendar-day-input:not([disabled])'));
                const currentIndex = allInputs.indexOf(input);
                if (currentIndex >= 0 && currentIndex < allInputs.length - 1) {
                    allInputs[currentIndex + 1].focus();
                    allInputs[currentIndex + 1].select();
                }
            }
        });
        cell.appendChild(input);
    }
    return cell;
}
/**
 * Navigate to previous month
 */
function prevMonth() {
    calendarMonth--;
    if (calendarMonth < 0) {
        calendarMonth = 11;
        calendarYear--;
    }
    renderCalendar();
}
/**
 * Navigate to next month
 */
function nextMonth() {
    calendarMonth++;
    if (calendarMonth > 11) {
        calendarMonth = 0;
        calendarYear++;
    }
    renderCalendar();
}
/**
 * Add product with calendar quantities
 */
function addProductWithCalendar() {
    const name = document.getElementById('add-product-name').value.trim();
    if (!name) {
        showToast('❌ 品目名を入力してください');
        return;
    }
    if (allProducts.indexOf(name) >= 0) {
        showToast('❌ 同名の商品が既に存在します');
        return;
    }
    const cost = parseInt(document.getElementById('add-product-cost').value) || null;
    const price = parseInt(document.getElementById('add-product-price').value) || null;
    const unit = parseInt(document.getElementById('add-product-unit').value) || null;
    const tag1 = document.getElementById('add-product-tag1').value.trim();
    const tag2 = document.getElementById('add-product-tag2').value.trim();
    const tag3 = document.getElementById('add-product-tag3').value.trim();
    // Check if any quantities were entered
    const quantityCount = Object.keys(calendarQuantities).length;
    if (quantityCount === 0) {
        if (!confirm('数量が入力されていませんが、商品情報のみ追加しますか？')) {
            return;
        }
    }
    // Add to products list
    allProducts.push(name);
    allProducts.sort();
    // Save product info
    productInfo[name] = { cost: cost, price: price, unit: unit };
    // Save tags
    if (tag1 || tag2 || tag3) {
        productTags[name] = {};
        if (tag1)
            productTags[name].tag1 = tag1;
        if (tag2)
            productTags[name].tag2 = tag2;
        if (tag3)
            productTags[name].tag3 = tag3;
    }
    // Add data entries for each date with quantity
    if (quantityCount > 0 && loadedFiles.length > 0) {
        const store = rawData.stores[0] || '手動追加';
        const supplier = rawData.suppliers[0] || '手動追加';
        const fileName = loadedFiles[0].name;
        Object.keys(calendarQuantities).forEach(function (date) {
            const qty = calendarQuantities[date];
            if (qty > 0) {
                rawData.data.push({
                    product: name,
                    date: date,
                    quantity: qty,
                    store: store,
                    supplier: supplier,
                    fileName: fileName
                });
            }
        });
    }
    closeAddProductModal();
    showToast(`✅ 商品を追加しました（${quantityCount}日分のデータ）`);
    updateTable();
}
function updateTagDatalist() {
    var tag1Set = new Set(), tag2Set = new Set(), tag3Set = new Set();
    Object.keys(productTags).forEach(function (p) {
        if (productTags[p].tag1)
            tag1Set.add(productTags[p].tag1);
        if (productTags[p].tag2)
            tag2Set.add(productTags[p].tag2);
        if (productTags[p].tag3)
            tag3Set.add(productTags[p].tag3);
    });
    document.getElementById('tag1-list').innerHTML = Array.from(tag1Set).sort().map(function (t) { return '<option value="' + escapeHtml(t) + '">'; }).join('');
    document.getElementById('tag2-list').innerHTML = Array.from(tag2Set).sort().map(function (t) { return '<option value="' + escapeHtml(t) + '">'; }).join('');
    document.getElementById('tag3-list').innerHTML = Array.from(tag3Set).sort().map(function (t) { return '<option value="' + escapeHtml(t) + '">'; }).join('');
}
function addProduct() {
    var name = document.getElementById('add-product-name').value.trim();
    if (!name) {
        showToast('❌ 品目名を入力してください');
        return;
    }
    if (allProducts.indexOf(name) >= 0) {
        showToast('❌ 同名の商品が既に存在します');
        return;
    }
    var cost = parseInt(document.getElementById('add-product-cost').value) || null;
    var price = parseInt(document.getElementById('add-product-price').value) || null;
    var unit = parseInt(document.getElementById('add-product-unit').value) || null;
    var tag1 = document.getElementById('add-product-tag1').value.trim();
    var tag2 = document.getElementById('add-product-tag2').value.trim();
    var tag3 = document.getElementById('add-product-tag3').value.trim();
    var date = document.getElementById('add-product-date').value;
    var qty = parseInt(document.getElementById('add-product-qty').value) || 0;
    allProducts.push(name);
    allProducts.sort();
    productInfo[name] = { cost: cost, price: price, unit: unit };
    if (tag1 || tag2 || tag3) {
        productTags[name] = {};
        if (tag1)
            productTags[name].tag1 = tag1;
        if (tag2)
            productTags[name].tag2 = tag2;
        if (tag3)
            productTags[name].tag3 = tag3;
    }
    if (date && qty > 0 && loadedFiles.length > 0) {
        var store = rawData.stores[0] || '手動追加';
        var supplier = rawData.suppliers[0] || '手動追加';
        rawData.data.push({
            product: name,
            date: date,
            quantity: qty,
            store: store,
            supplier: supplier,
            fileName: loadedFiles[0].name
        });
    }
    closeAddProductModal();
    showToast('✅ 商品を追加しました');
    updateTable();
}
function toggleFullscreen() {
    if (!document.fullscreenElement) {
        document.documentElement.requestFullscreen();
        document.body.classList.add('fullscreen');
    }
    else {
        document.exitFullscreen();
        document.body.classList.remove('fullscreen');
    }
}
document.addEventListener('fullscreenchange', function () {
    if (!document.fullscreenElement) {
        document.body.classList.remove('fullscreen');
    }
});
function deleteProduct(product) {
    if (!confirm('「' + product + '」を削除しますか？'))
        return;
    var idx = allProducts.indexOf(product);
    if (idx >= 0)
        allProducts.splice(idx, 1);
    delete productInfo[product];
    delete productTags[product];
    rawData.data = rawData.data.filter(function (d) { return d.product !== product; });
    showToast('🗑️ 商品を削除しました');
    updateTable();
}
function canEditCells() {
    return selectedStores.size === 1;
}
function editCell(product, date, currentVal, td) {
    if (!canEditCells()) {
        showToast('⚠️ 複数店舗選択時は編集できません');
        return;
    }
    if (td.querySelector('input'))
        return;
    var input = document.createElement('input');
    input.type = 'number';
    input.value = currentVal || '';
    input.min = '0';
    td.innerHTML = '';
    td.appendChild(input);
    input.focus();
    input.select();
    input.onblur = function () { saveCellEdit(product, date, input.value, td, currentVal); };
    input.onkeydown = function (e) {
        if (e.key === 'Enter') {
            input.blur();
        }
        if (e.key === 'Escape') {
            updateTable();
        }
    };
}
/**
 * Save cell edit to data
 * @param {string} product - Product name
 * @param {string} date - Date string
 * @param {string} newVal - New value
 * @param {HTMLElement} td - Table cell element
 * @param {number} originalVal - Original value
 */
function saveCellEdit(product, date, newVal, td, originalVal) {
    const qty = parseInt(newVal) || 0;
    const store = Array.from(selectedStores)[0];
    if (!store) {
        showToast('⚠️ 店舗が選択されていません');
        return;
    }
    const cellKey = createCellKey(product, date, store);
    // 元の値と異なる場合のみ編集履歴に記録
    if (qty !== originalVal) {
        if (!cellEdits[cellKey]) {
            cellEdits[cellKey] = { original: originalVal, edited: qty };
        }
        else {
            cellEdits[cellKey].edited = qty;
        }
    }
    else {
        // 元の値に戻した場合は編集履歴から削除
        delete cellEdits[cellKey];
    }
    var found = false;
    rawData.data.forEach(function (d) {
        if (d.product === product && d.date === date && d.store === store) {
            d.quantity = qty;
            found = true;
        }
    });
    if (!found && qty > 0) {
        rawData.data.push({
            product: product,
            date: date,
            quantity: qty,
            store: store,
            supplier: rawData.suppliers[0] || '手動追加',
            fileName: loadedFiles[0] ? loadedFiles[0].name : '手動追加'
        });
    }
    updateTable();
}
async function saveToDatabase() {
    const name = document.getElementById('save-name').value.trim();
    if (!name) {
        showToast('名前を入力してください');
        return;
    }
    try {
        await saveData(name, { loadedFiles, productInfo, allProducts, productTags });
        closeSaveModal();
        showToast('✅ 保存しました');
        renderSavedList();
    }
    catch (e) {
        showToast('❌ 保存に失敗しました');
    }
}
async function loadFromDB(id) {
    try {
        const data = await loadData(id);
        if (!data) {
            showToast('データが見つかりません');
            return;
        }
        loadedFiles = data.loadedFiles || [];
        productInfo = data.productInfo || {};
        allProducts = data.allProducts || [];
        productTags = data.productTags || {};
        mergeAllData();
        selectedFiles = new Set(loadedFiles.map(f => f.id));
        updateFileChips();
        initUI();
        dropZone.style.display = 'none';
        document.getElementById('files-bar').classList.add('show');
        document.getElementById('main-content').classList.add('show');
        document.getElementById('file-filter-panel').style.display = loadedFiles.length > 1 ? 'block' : 'none';
        showToast('✅ 読み込みました');
    }
    catch (e) {
        showToast('❌ 読み込みに失敗しました');
    }
}
async function deleteFromDB(id) {
    if (!confirm('削除しますか？'))
        return;
    try {
        await deleteData(id);
        showToast('🗑️ 削除しました');
        renderSavedList();
    }
    catch (e) {
        showToast('❌ 削除に失敗しました');
    }
}
function showToast(msg) { const t = document.getElementById('toast'); t.textContent = msg; t.classList.remove('show'); void t.offsetWidth; t.classList.add('show'); setTimeout(() => t.classList.remove('show'), 2000); }
// ============================================================================
// Application State
// ============================================================================
/** Loaded Excel files */
let loadedFiles = [];
/** Raw data from all files */
let rawData = {
    data: [],
    stores: [],
    products: [],
    dates: [],
    suppliers: []
};
/** Product information (cost, price, unit) */
let productInfo = {};
/** Product tags (tag1, tag2, tag3) */
let productTags = {};
/** Selected stores */
let selectedStores = new Set();
/** Selected suppliers */
let selectedSuppliers = new Set();
/** Selected file IDs */
let selectedFiles = new Set();
/** All dates from loaded data */
let allDatesRaw = [];
/** All product names */
let allProducts = [];
/** Selected column indices */
let selectedCols = new Set();
/** Selected row indices */
let selectedRows = new Set();
/** Column drag state */
let isDraggingCol = false;
/** Row drag state */
let isDraggingRow = false;
/** Drag start column index */
let dragStartCol = -1;
/** Drag start row index */
let dragStartRow = -1;
/** Currently displayed dates */
let currentDates = [];
/** Currently displayed products */
let currentProducts = [];
/** Pivot table data */
let currentPivot = {};
/** Date range slider start index */
let sliderFromIdx = 0;
/** Date range slider end index */
let sliderToIdx = 0;
/** Cell edit history: {product-date-store: {original: value, edited: value}} */
let cellEdits = {};
/** Selected cell range (row-col format) */
let selectedCells = new Set();
/** Cell range drag state */
let isDraggingCells = false;
/** Cell drag start position {row, col} */
let cellDragStart = null;
/** Cell drag timer ID */
let cellDragTimer = null;
/** Calendar current year and month for add product modal */
let calendarYear = new Date().getFullYear();
let calendarMonth = new Date().getMonth(); // 0-11
/** Calendar quantity inputs: {date: quantity} */
let calendarQuantities = {};
// DOM elements
const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');
const fileInputMini = document.getElementById('file-input-mini');
const tooltip = document.getElementById('selection-tooltip');
// ============================================================================
// Helper Functions
// ============================================================================
/**
 * Create a cell key from product, date, and store
 */
function createCellKey(product, date, store) {
    return `${product}-${date}-${store}`;
}
/**
 * Parse a cell key into components
 */
function parseCellKey(cellKey) {
    const lastDash = cellKey.lastIndexOf('-');
    const secondLastDash = cellKey.lastIndexOf('-', lastDash - 1);
    return {
        product: cellKey.substring(0, secondLastDash),
        date: cellKey.substring(secondLastDash + 1, lastDash),
        store: cellKey.substring(lastDash + 1)
    };
}
/**
 * Escape HTML special characters
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
function setupDropZone(zone, input) {
    zone.addEventListener('click', (e) => { if (e.target.tagName !== 'INPUT')
        input.click(); });
    zone.addEventListener('dragover', (e) => { e.preventDefault(); zone.classList.add('drag-over'); });
    zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
    zone.addEventListener('drop', (e) => { e.preventDefault(); zone.classList.remove('drag-over'); handleFiles(e.dataTransfer.files); });
    input.addEventListener('change', (e) => { if (e.target.files.length > 0) {
        handleFiles(e.target.files);
        input.value = '';
    } });
}
setupDropZone(dropZone, fileInput);
fileInputMini.addEventListener('change', (e) => { if (e.target.files.length > 0) {
    handleFiles(e.target.files);
    e.target.value = '';
} });
function handleFiles(files) {
    const valid = Array.from(files).filter((f) => ['.xls', '.xlsx'].includes(f.name.substring(f.name.lastIndexOf('.')).toLowerCase()));
    if (valid.length === 0) {
        alert('Excelファイル（.xls, .xlsx）を選択してください');
        return;
    }
    dropZone.style.display = 'none';
    document.getElementById('loading').classList.add('show');
    let done = 0;
    valid.forEach((file) => {
        if (loadedFiles.some(f => f.name === file.name)) {
            done++;
            if (done === valid.length)
                finishLoading();
            return;
        }
        const reader = new FileReader();
        reader.onload = (e) => {
            try {
                const result = e.target?.result;
                const wb = XLSX.read(new Uint8Array(result), { type: 'array' });
                const fd = parseWorkbook(wb, file.name);
                loadedFiles.push({ id: Date.now() + Math.random(), name: file.name, size: file.size, ...fd });
            }
            catch (err) {
                alert(file.name + ' の読み込みに失敗しました');
            }
            done++;
            if (done === valid.length)
                finishLoading();
        };
        reader.readAsArrayBuffer(file);
    });
}
function finishLoading() {
    document.getElementById('loading').classList.remove('show');
    if (loadedFiles.length === 0) {
        dropZone.style.display = 'flex';
        return;
    }
    mergeAllData();
    selectedFiles = new Set(loadedFiles.map(f => f.id));
    updateFileChips();
    initUI();
    document.getElementById('files-bar').classList.add('show');
    document.getElementById('files-bar-body').classList.add('show');
    document.getElementById('main-content').classList.add('show');
    document.getElementById('file-filter-panel').style.display = loadedFiles.length > 1 ? 'flex' : 'none';
    // フィードバック: 読み込んだデータ件数を通知
    const totalRecords = rawData.data.length;
    const totalProducts = rawData.products.length;
    showToast(`✅ ${loadedFiles.length}ファイル読込完了 (${totalProducts}品目、${totalRecords}件のデータ)`);
}
function parseWorkbook(wb, fileName) {
    const data = [];
    const sheets = [];
    const pInfo = {};
    const prods = new Set();
    wb.SheetNames.forEach((sn) => {
        const json = window.XLSX.utils.sheet_to_json(wb.Sheets[sn], { header: 1, defval: '' });
        if (json.length < 8)
            return;
        sheets.push(sn);
        const hdr = json[6] || [];
        const storeCols = [];
        for (let c = 6; c < hdr.length; c++) {
            const code = hdr[c];
            if (code !== '' && code !== null) {
                storeCols.push({
                    col: c,
                    code: String(Math.floor(Number(code)) || code)
                });
            }
        }
        let curProd = null;
        let curCost = null;
        let curPrice = null;
        let curUnit = null;
        for (let r = 7; r < json.length; r++) {
            const row = json[r];
            if (!row || row.length === 0)
                continue;
            const c0 = String(row[0] || '').trim();
            if (c0.length > 0) {
                curProd = extractProductName(c0);
                prods.add(curProd);
                const pm = String(row[3] || '').match(/(\d+)[^\d]+(\d+)/);
                if (pm) {
                    curCost = parseInt(pm[1]);
                    curPrice = parseInt(pm[2]);
                }
                else {
                    curCost = curPrice = null;
                }
                const um = String(row[4] || '').match(/(\d+)\s*$/);
                curUnit = um ? parseInt(um[1]) : null;
                if (curProd && !pInfo[curProd]) {
                    pInfo[curProd] = {
                        cost: curCost,
                        price: curPrice,
                        unit: curUnit
                    };
                }
            }
            const dm = String(row[2] || '').trim().match(/(\d+)\/(\d+)/);
            if (!dm)
                continue;
            const ds = parseInt(dm[1]) + '/' + parseInt(dm[2]);
            if (curProd) {
                storeCols.forEach(sc => {
                    const q = Number(row[sc.col]);
                    if (q > 0) {
                        data.push({
                            fileName,
                            supplier: sn,
                            product: curProd,
                            date: ds,
                            store: sc.code,
                            quantity: q
                        });
                    }
                });
            }
        }
    });
    return {
        data,
        sheets,
        productInfo: pInfo,
        products: Array.from(prods)
    };
}
function mergeAllData() {
    const allData = [], allStores = new Set(), allDates = new Set(), allSuppliers = new Set(), allProds = new Set();
    productInfo = {};
    loadedFiles.forEach(f => {
        f.data.forEach(i => { allData.push(i); allStores.add(i.store); allDates.add(i.date); allSuppliers.add(i.supplier); });
        if (f.products)
            f.products.forEach(p => allProds.add(p));
        if (f.productInfo)
            Object.assign(productInfo, f.productInfo);
    });
    allDatesRaw = Array.from(allDates).sort((a, b) => { const ap = a.split('/').map(Number), bp = b.split('/').map(Number); return (ap[0] === 12 ? 0 : 1) - (bp[0] === 12 ? 0 : 1) || ap[1] - bp[1]; });
    allProducts = Array.from(allProds).sort();
    rawData = { data: allData, stores: Array.from(allStores).sort((a, b) => Number(a) - Number(b)), products: [...new Set(allData.map(d => d.product))].sort(), dates: allDatesRaw, suppliers: Array.from(allSuppliers).sort() };
    selectedStores = new Set(rawData.stores);
    selectedSuppliers = new Set(rawData.suppliers);
    initSlider();
}
function initSlider() {
    if (allDatesRaw.length === 0)
        return;
    const sf = document.getElementById('slider-from'), st = document.getElementById('slider-to');
    const maxVal = Math.max(0, allDatesRaw.length - 1);
    sf.max = st.max = maxVal;
    sf.value = 0;
    st.value = maxVal;
    sliderFromIdx = 0;
    sliderToIdx = maxVal;
    updateSliderUI();
    sf.oninput = function (e) {
        const target = e.target;
        const val = parseInt(target.value);
        sliderFromIdx = Math.min(val, sliderToIdx);
        target.value = String(sliderFromIdx);
        updateSliderUI();
        updateTable();
    };
    st.oninput = function (e) {
        const target = e.target;
        const val = parseInt(target.value);
        sliderToIdx = Math.max(val, sliderFromIdx);
        target.value = String(sliderToIdx);
        updateSliderUI();
        updateTable();
    };
}
function updateSliderUI() {
    document.getElementById('slider-from-label').textContent = allDatesRaw[sliderFromIdx] || '-';
    document.getElementById('slider-to-label').textContent = allDatesRaw[sliderToIdx] || '-';
    const maxVal = Math.max(1, allDatesRaw.length - 1);
    const pct1 = (sliderFromIdx / maxVal) * 100;
    const pct2 = (sliderToIdx / maxVal) * 100;
    const range = document.getElementById('slider-range');
    range.style.left = 'calc(10px + ' + pct1 + '% * (100% - 20px) / 100)';
    range.style.width = 'calc(' + (pct2 - pct1) + '% * (100% - 20px) / 100)';
}
function getFilteredDates() { return allDatesRaw.slice(sliderFromIdx, sliderToIdx + 1); }
function updateFileChips() {
    document.getElementById('file-chips').innerHTML = loadedFiles.map(f => '<div class="file-chip"><span class="name" title="' + escapeHtml(f.name) + '">' + escapeHtml(f.name) + '</span><span class="remove" onclick="removeFile(\'' + f.id + '\')">✕</span></div>').join('');
    document.getElementById('files-count').textContent = String(loadedFiles.length);
    updateFileFilterList();
}
function updateFileFilterList() {
    document.getElementById('file-filter-list').innerHTML = loadedFiles.map(f => '<label class="checkbox-item ' + (selectedFiles.has(f.id) ? 'selected' : '') + '"><input type="checkbox" ' + (selectedFiles.has(f.id) ? 'checked' : '') + ' onchange="toggleFileFilter(\'' + f.id + '\',this)"> ' + escapeHtml(f.name) + '</label>').join('');
}
function removeFile(id) { loadedFiles = loadedFiles.filter(f => f.id != id); selectedFiles.delete(id); if (loadedFiles.length === 0) {
    clearAllFiles();
    return;
} mergeAllData(); updateFileChips(); initUI(); document.getElementById('file-filter-panel').style.display = loadedFiles.length > 1 ? 'block' : 'none'; }
function clearAllFiles() {
    loadedFiles = [];
    rawData = { data: [], stores: [], products: [], dates: [], suppliers: [] };
    productInfo = {};
    productTags = {};
    selectedStores = new Set();
    selectedSuppliers = new Set();
    selectedFiles = new Set();
    allDatesRaw = [];
    allProducts = [];
    dropZone.style.display = 'block';
    document.getElementById('files-bar').classList.remove('show');
    document.getElementById('main-content').classList.remove('show');
}
function toggleFileFilter(id, cb) { cb.checked ? selectedFiles.add(id) : selectedFiles.delete(id); cb.parentElement.classList.toggle('selected', cb.checked); updateTable(); }
function selectAllFiles() { selectedFiles = new Set(loadedFiles.map(f => f.id)); document.querySelectorAll('#file-filter-list input').forEach(cb => { cb.checked = true; cb.parentElement.classList.add('selected'); }); updateTable(); }
function clearAllFileFilters() { selectedFiles = new Set(); document.querySelectorAll('#file-filter-list input').forEach(cb => { cb.checked = false; cb.parentElement.classList.remove('selected'); }); updateTable(); }
function extractProductName(raw) {
    if (raw.indexOf('\t') >= 0) {
        const parts = raw.split('\t');
        if (parts.length >= 2) {
            const np = parts[parts.length - 1].split(/[\u3000\s]+/).filter(p => p.trim());
            if (np.length > 0 && /^0\d+$/.test(np[0]))
                np.shift();
            if (np.length > 0)
                return np.slice(0, 4).join(' ');
        }
    }
    const parts = raw.split(/[\u3000\s]+/).filter(p => p.trim());
    if (parts.length > 3) {
        const idx = parts.findIndex(p => !/^\d+$/.test(p) && p.length > 1);
        if (idx >= 0)
            return parts.slice(idx, idx + 4).join(' ');
    }
    return raw.substring(0, 50);
}
function initUI() {
    document.getElementById('store-list').innerHTML = rawData.stores.map(s => '<label class="checkbox-item selected"><input type="checkbox" checked onchange="toggleStore(\'' + s + '\',this)"> ' + s + '</label>').join('');
    document.getElementById('supplier-list').innerHTML = rawData.suppliers.map(s => '<label class="checkbox-item selected"><input type="checkbox" checked onchange="toggleSupplier(\'' + s + '\',this)"> ' + s + '</label>').join('');
    document.getElementById('search-input').value = '';
    updateTable();
}
function toggleDropdown(type) { const dd = document.getElementById(type + '-dropdown'), isOpen = dd.classList.contains('show'); document.querySelectorAll('.dropdown-menu').forEach(d => d.classList.remove('show')); if (!isOpen)
    dd.classList.add('show'); }
function toggleStore(s, cb) { cb.checked ? selectedStores.add(s) : selectedStores.delete(s); cb.parentElement.classList.toggle('selected', cb.checked); updateTable(); }
function toggleSupplier(s, cb) { cb.checked ? selectedSuppliers.add(s) : selectedSuppliers.delete(s); cb.parentElement.classList.toggle('selected', cb.checked); updateTable(); }
function selectAllStores() { selectedStores = new Set(rawData.stores); document.querySelectorAll('#store-list input').forEach(cb => { cb.checked = true; cb.parentElement.classList.add('selected'); }); updateTable(); }
function clearAllStores() { selectedStores = new Set(); document.querySelectorAll('#store-list input').forEach(cb => { cb.checked = false; cb.parentElement.classList.remove('selected'); }); updateTable(); }
function selectAllSuppliers() { selectedSuppliers = new Set(rawData.suppliers); document.querySelectorAll('#supplier-list input').forEach(cb => { cb.checked = true; cb.parentElement.classList.add('selected'); }); updateTable(); }
function clearAllSuppliers() { selectedSuppliers = new Set(); document.querySelectorAll('#supplier-list input').forEach(cb => { cb.checked = false; cb.parentElement.classList.remove('selected'); }); updateTable(); }
function getFilteredData() {
    const st = document.getElementById('search-input').value;
    const fns = new Set(loadedFiles.filter(f => selectedFiles.has(f.id)).map(f => f.name));
    const fd = new Set(getFilteredDates());
    return rawData.data.filter(i => fns.has(i.fileName) && selectedStores.has(i.store) && selectedSuppliers.has(i.supplier) && fd.has(i.date) && (st === '' || i.product.indexOf(st) >= 0));
}
function setTag(product, tagNum, value) {
    if (!productTags[product])
        productTags[product] = {};
    productTags[product]['tag' + tagNum] = value.trim();
    updateTagStats();
}
function getTag(product, tagNum) {
    return productTags[product] ? (productTags[product]['tag' + tagNum] || '') : '';
}
function importTags(input) {
    const file = input.files[0];
    if (!file)
        return;
    const reader = new FileReader();
    reader.onload = function (e) {
        try {
            var data;
            if (file.name.endsWith('.csv')) {
                const text = e.target?.result;
                const lines = text.split(/\r?\n/).filter(l => l.trim());
                data = lines.map(l => l.split(',').map(c => c.replace(/^"|"$/g, '').trim()));
            }
            else {
                const result = e.target?.result;
                const wb = XLSX.read(new Uint8Array(result), { type: 'array' });
                data = XLSX.utils.sheet_to_json(wb.Sheets[wb.SheetNames[0]], { header: 1, defval: '' });
            }
            var headerIdx = 0;
            for (var i = 0; i < Math.min(5, data.length); i++) {
                const row = data[i].map(c => String(c).toLowerCase());
                if (row.some(c => c.indexOf('品目') >= 0 || c.indexOf('商品') >= 0 || c.indexOf('product') >= 0)) {
                    headerIdx = i;
                    break;
                }
            }
            const header = data[headerIdx].map(c => String(c).toLowerCase());
            const prodCol = header.findIndex(c => c.indexOf('品目') >= 0 || c.indexOf('商品') >= 0 || c.indexOf('product') >= 0);
            const tag1Col = header.findIndex(c => c.indexOf('大分類') >= 0 || c.indexOf('親') >= 0 || c.indexOf('tag1') >= 0);
            const tag2Col = header.findIndex(c => c.indexOf('中分類') >= 0 || c.indexOf('子') >= 0 || c.indexOf('tag2') >= 0);
            const tag3Col = header.findIndex(c => c.indexOf('小分類') >= 0 || c.indexOf('孫') >= 0 || c.indexOf('tag3') >= 0);
            if (prodCol === -1) {
                showToast('❌ 品目名列が見つかりません');
                return;
            }
            var count = 0, updatedCount = 0, changes = [];
            for (var i = headerIdx + 1; i < data.length; i++) {
                const row = data[i];
                const prod = String(row[prodCol] || '').trim();
                if (!prod)
                    continue;
                const matchedProd = allProducts.find(p => p.indexOf(prod) >= 0 || prod.indexOf(p) >= 0);
                if (matchedProd) {
                    if (!productTags[matchedProd])
                        productTags[matchedProd] = {};
                    var hasChange = false;
                    if (tag1Col >= 0) {
                        const newVal = String(row[tag1Col] || '').trim();
                        const oldVal = productTags[matchedProd].tag1 || '';
                        if (newVal && oldVal && newVal !== oldVal) {
                            changes.push(matchedProd.substring(0, 15) + ': 大分類「' + oldVal + '」→「' + newVal + '」');
                            hasChange = true;
                        }
                        if (newVal)
                            productTags[matchedProd].tag1 = newVal;
                    }
                    if (tag2Col >= 0) {
                        const newVal = String(row[tag2Col] || '').trim();
                        const oldVal = productTags[matchedProd].tag2 || '';
                        if (newVal && oldVal && newVal !== oldVal) {
                            changes.push(matchedProd.substring(0, 15) + ': 中分類「' + oldVal + '」→「' + newVal + '」');
                            hasChange = true;
                        }
                        if (newVal)
                            productTags[matchedProd].tag2 = newVal;
                    }
                    if (tag3Col >= 0) {
                        const newVal = String(row[tag3Col] || '').trim();
                        const oldVal = productTags[matchedProd].tag3 || '';
                        if (newVal && oldVal && newVal !== oldVal) {
                            changes.push(matchedProd.substring(0, 15) + ': 小分類「' + oldVal + '」→「' + newVal + '」');
                            hasChange = true;
                        }
                        if (newVal)
                            productTags[matchedProd].tag3 = newVal;
                    }
                    count++;
                    if (hasChange)
                        updatedCount++;
                }
            }
            if (changes.length > 0) {
                var msg = '以下のタグが上書きされました:\n\n' + changes.slice(0, 10).join('\n');
                if (changes.length > 10)
                    msg += '\n... 他' + (changes.length - 10) + '件';
                alert(msg);
            }
            showToast('✅ ' + count + '件取込（' + updatedCount + '件上書き）');
            updateTable();
        }
        catch (err) {
            console.error(err);
            showToast('❌ ファイルの読み込みに失敗しました');
        }
    };
    if (file.name.endsWith('.csv')) {
        reader.readAsText(file, 'UTF-8');
    }
    else {
        reader.readAsArrayBuffer(file);
    }
    input.value = '';
}
function updateTagStats() {
    const hierarchy = {};
    const noTag1 = { tag2s: {}, noTag2: {} };
    currentProducts.forEach(function (p) {
        const t1 = getTag(p, 1), t2 = getTag(p, 2), t3 = getTag(p, 3);
        const info = (productInfo[p] || {});
        const qty = currentPivot[p] ? (currentPivot[p].total || 0) : 0;
        const unit = info.unit || 1;
        const cost = (info.cost || 0) * qty * unit;
        const price = (info.price || 0) * qty * unit;
        if (t1) {
            if (!hierarchy[t1])
                hierarchy[t1] = { _total: { qty: 0, cost: 0, price: 0 }, _children: {} };
            hierarchy[t1]._total.qty += qty;
            hierarchy[t1]._total.cost += cost;
            hierarchy[t1]._total.price += price;
            if (t2) {
                if (!hierarchy[t1]._children[t2])
                    hierarchy[t1]._children[t2] = { _total: { qty: 0, cost: 0, price: 0 }, _children: {} };
                hierarchy[t1]._children[t2]._total.qty += qty;
                hierarchy[t1]._children[t2]._total.cost += cost;
                hierarchy[t1]._children[t2]._total.price += price;
                if (t3) {
                    if (!hierarchy[t1]._children[t2]._children[t3])
                        hierarchy[t1]._children[t2]._children[t3] = { qty: 0, cost: 0, price: 0 };
                    hierarchy[t1]._children[t2]._children[t3].qty += qty;
                    hierarchy[t1]._children[t2]._children[t3].cost += cost;
                    hierarchy[t1]._children[t2]._children[t3].price += price;
                }
            }
        }
        else if (t2) {
            if (!noTag1.tag2s[t2])
                noTag1.tag2s[t2] = { _total: { qty: 0, cost: 0, price: 0 }, _children: {} };
            noTag1.tag2s[t2]._total.qty += qty;
            noTag1.tag2s[t2]._total.cost += cost;
            noTag1.tag2s[t2]._total.price += price;
            if (t3) {
                if (!noTag1.tag2s[t2]._children[t3])
                    noTag1.tag2s[t2]._children[t3] = { qty: 0, cost: 0, price: 0 };
                noTag1.tag2s[t2]._children[t3].qty += qty;
                noTag1.tag2s[t2]._children[t3].cost += cost;
                noTag1.tag2s[t2]._children[t3].price += price;
            }
        }
        else if (t3) {
            if (!noTag1.noTag2[t3])
                noTag1.noTag2[t3] = { qty: 0, cost: 0, price: 0 };
            noTag1.noTag2[t3].qty += qty;
            noTag1.noTag2[t3].cost += cost;
            noTag1.noTag2[t3].price += price;
        }
    });
    const tbody = document.getElementById('tag-stats-tbody');
    const t1s = Object.keys(hierarchy).sort();
    const hasOrphans = Object.keys(noTag1.tag2s).length > 0 || Object.keys(noTag1.noTag2).length > 0;
    if (t1s.length === 0 && !hasOrphans) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;opacity:0.5;">タグが設定されていません</td></tr>';
        return;
    }
    function calcMargin(d) { return d.price > 0 ? ((d.price - d.cost) / d.price * 100).toFixed(1) : 0; }
    var html = '';
    t1s.forEach(function (t1) {
        const d1 = hierarchy[t1]._total;
        html += '<tr class="parent-row"><td><span class="tag-label tag1">📁 ' + escapeHtml(t1) + '</span></td><td class="num">' + d1.qty.toLocaleString() + '</td><td class="num">¥' + d1.cost.toLocaleString() + '</td><td class="num">¥' + d1.price.toLocaleString() + '</td><td class="num">' + calcMargin(d1) + '%</td></tr>';
        Object.keys(hierarchy[t1]._children).sort().forEach(function (t2) {
            const d2 = hierarchy[t1]._children[t2]._total;
            html += '<tr class="child-row"><td>├ ' + escapeHtml(t2) + '</td><td class="num">' + d2.qty.toLocaleString() + '</td><td class="num">¥' + d2.cost.toLocaleString() + '</td><td class="num">¥' + d2.price.toLocaleString() + '</td><td class="num">' + calcMargin(d2) + '%</td></tr>';
            Object.keys(hierarchy[t1]._children[t2]._children).sort().forEach(function (t3) {
                const d3 = hierarchy[t1]._children[t2]._children[t3];
                html += '<tr class="grandchild-row"><td>│ └ ' + escapeHtml(t3) + '</td><td class="num">' + d3.qty.toLocaleString() + '</td><td class="num">¥' + d3.cost.toLocaleString() + '</td><td class="num">¥' + d3.price.toLocaleString() + '</td><td class="num">' + calcMargin(d3) + '%</td></tr>';
            });
        });
    });
    if (hasOrphans) {
        html += '<tr class="parent-row"><td><span class="tag-no-parent">📂 (未分類)</span></td><td class="num">-</td><td class="num">-</td><td class="num">-</td><td class="num">-</td></tr>';
        Object.keys(noTag1.tag2s).sort().forEach(function (t2) {
            const d2 = noTag1.tag2s[t2]._total;
            html += '<tr class="child-row"><td>├ ' + escapeHtml(t2) + '</td><td class="num">' + d2.qty.toLocaleString() + '</td><td class="num">¥' + d2.cost.toLocaleString() + '</td><td class="num">¥' + d2.price.toLocaleString() + '</td><td class="num">' + calcMargin(d2) + '%</td></tr>';
            Object.keys(noTag1.tag2s[t2]._children).sort().forEach(function (t3) {
                const d3 = noTag1.tag2s[t2]._children[t3];
                html += '<tr class="grandchild-row"><td>│ └ ' + escapeHtml(t3) + '</td><td class="num">' + d3.qty.toLocaleString() + '</td><td class="num">¥' + d3.cost.toLocaleString() + '</td><td class="num">¥' + d3.price.toLocaleString() + '</td><td class="num">' + calcMargin(d3) + '%</td></tr>';
            });
        });
        Object.keys(noTag1.noTag2).sort().forEach(function (t3) {
            const d3 = noTag1.noTag2[t3];
            html += '<tr class="grandchild-row"><td>└ ' + escapeHtml(t3) + '</td><td class="num">' + d3.qty.toLocaleString() + '</td><td class="num">¥' + d3.cost.toLocaleString() + '</td><td class="num">¥' + d3.price.toLocaleString() + '</td><td class="num">' + calcMargin(d3) + '%</td></tr>';
        });
    }
    tbody.innerHTML = html;
}
function updateTable() {
    if (rawData.data.length === 0)
        return;
    const filtered = getFilteredData(), dates = getFilteredDates();
    currentDates = dates;
    const showZero = document.getElementById('show-zero').checked;
    const showCost = document.getElementById('show-cost').checked;
    const showPrice = document.getElementById('show-price').checked;
    const showUnit = document.getElementById('show-unit').checked;
    const showTag1 = document.getElementById('show-tag1').checked;
    const showTag2 = document.getElementById('show-tag2').checked;
    const showTag3 = document.getElementById('show-tag3').checked;
    const st = document.getElementById('search-input').value;
    const pivot = {}, dateTotals = {};
    dates.forEach(function (d) { dateTotals[d] = 0; });
    const relProds = showZero ? allProducts.filter(function (p) { return st === '' || p.indexOf(st) >= 0; }) : [];
    relProds.forEach(function (p) { pivot[p] = { total: 0 }; dates.forEach(function (d) { pivot[p][d] = 0; }); });
    filtered.forEach(function (i) {
        if (!pivot[i.product]) {
            pivot[i.product] = { total: 0 };
            dates.forEach(function (d) { pivot[i.product][d] = 0; });
        }
        pivot[i.product][i.date] += i.quantity;
        pivot[i.product].total += i.quantity;
        dateTotals[i.date] += i.quantity;
    });
    currentPivot = pivot;
    var products = Object.keys(pivot);
    const sortOrder = document.getElementById('sort-order').value;
    if (sortOrder === 'tag') {
        products.sort(function (a, b) {
            const t1a = getTag(a, 1) || '\uffff', t1b = getTag(b, 1) || '\uffff';
            if (t1a !== t1b)
                return t1a.localeCompare(t1b, 'ja');
            const t2a = getTag(a, 2) || '\uffff', t2b = getTag(b, 2) || '\uffff';
            if (t2a !== t2b)
                return t2a.localeCompare(t2b, 'ja');
            const t3a = getTag(a, 3) || '\uffff', t3b = getTag(b, 3) || '\uffff';
            if (t3a !== t3b)
                return t3a.localeCompare(t3b, 'ja');
            return a.localeCompare(b, 'ja');
        });
    }
    else if (sortOrder === 'qty-desc') {
        products.sort(function (a, b) { return (pivot[b].total || 0) - (pivot[a].total || 0); });
    }
    else if (sortOrder === 'qty-asc') {
        products.sort(function (a, b) { return (pivot[a].total || 0) - (pivot[b].total || 0); });
    }
    else {
        products.sort(function (a, b) { return a.localeCompare(b, 'ja'); });
    }
    if (!showZero)
        products = products.filter(function (p) { return pivot[p].total > 0; });
    currentProducts = products;
    var totalCost = 0, totalPrice = 0;
    products.forEach(function (p) {
        const info = (productInfo[p] || {}), qty = pivot[p].total;
        const unit = info.unit || 1;
        if (info.cost)
            totalCost += qty * unit * info.cost;
        if (info.price)
            totalPrice += qty * unit * info.price;
    });
    const marginRate = totalPrice > 0 ? ((totalPrice - totalCost) / totalPrice * 100).toFixed(1) : 0;
    document.getElementById('stat-cost').textContent = totalCost.toLocaleString();
    document.getElementById('stat-price').textContent = totalPrice.toLocaleString();
    document.getElementById('stat-margin').textContent = String(marginRate);
    document.getElementById('store-count').textContent = selectedStores.size + '/' + rawData.stores.length;
    document.getElementById('supplier-count').textContent = selectedSuppliers.size + '/' + rawData.suppliers.length;
    document.getElementById('file-filter-count').textContent = selectedFiles.size + '/' + loadedFiles.length;
    document.getElementById('store-btn-text').textContent = selectedStores.size === rawData.stores.length ? '全選択' : selectedStores.size + '件';
    document.getElementById('supplier-btn-text').textContent = selectedSuppliers.size === rawData.suppliers.length ? '全選択' : selectedSuppliers.size + '件';
    document.getElementById('file-btn-text').textContent = selectedFiles.size === loadedFiles.length ? '全選択' : selectedFiles.size + '件';
    const thead = document.querySelector('#data-table thead');
    var hdr = '<tr><th class="product">品目名</th>';
    if (showTag1)
        hdr += '<th class="tag tag1">#大分類</th>';
    if (showTag2)
        hdr += '<th class="tag tag2">#中分類</th>';
    if (showTag3)
        hdr += '<th class="tag tag3">#小分類</th>';
    if (showCost)
        hdr += '<th class="info-cost">原価</th>';
    if (showPrice)
        hdr += '<th class="info-price">売価</th>';
    if (showUnit)
        hdr += '<th class="info">入数</th>';
    dates.forEach(function (d, i) { hdr += '<th class="date-col" data-col="' + i + '">' + d + '</th>'; });
    hdr += '<th class="total">計</th><th class="del-col">削除</th></tr>';
    thead.innerHTML = hdr;
    const tbody = document.querySelector('#data-table tbody');
    if (products.length === 0) {
        tbody.innerHTML = '';
        document.getElementById('no-data').style.display = 'block';
        updateTagStats();
        return;
    }
    document.getElementById('no-data').style.display = 'none';
    var canEdit = canEditCells();
    var html = '';
    products.forEach(function (p, ri) {
        const row = pivot[p], info = (productInfo[p] || {});
        const pEsc = p.replace(/'/g, "\\'").replace(/"/g, '&quot;');
        html += '<tr data-row="' + ri + '" data-product="' + pEsc + '"><td class="product" data-row="' + ri + '">' + escapeHtml(p) + '</td>';
        if (showTag1)
            html += '<td class="tag tag1"><input type="text" value="' + escapeHtml(getTag(p, 1)) + '" onchange="setTag(\'' + pEsc + '\', 1, this.value)" placeholder="大"></td>';
        if (showTag2)
            html += '<td class="tag tag2"><input type="text" value="' + escapeHtml(getTag(p, 2)) + '" onchange="setTag(\'' + pEsc + '\', 2, this.value)" placeholder="中"></td>';
        if (showTag3)
            html += '<td class="tag tag3"><input type="text" value="' + escapeHtml(getTag(p, 3)) + '" onchange="setTag(\'' + pEsc + '\', 3, this.value)" placeholder="小"></td>';
        if (showCost)
            html += '<td class="info info-cost">' + (info.cost || '-') + '</td>';
        if (showPrice)
            html += '<td class="info info-price">' + (info.price || '-') + '</td>';
        if (showUnit)
            html += '<td class="info">' + (info.unit || '-') + '</td>';
        dates.forEach(function (d, ci) {
            const v = row[d] || 0;
            const store = Array.from(selectedStores)[0];
            const cellKey = store ? createCellKey(p, d, store) : null;
            const isEdited = cellKey ? cellEdits[cellKey] : null;
            var editAttr = canEdit ? ' onclick="editCell(\'' + pEsc + '\', \'' + d + '\', ' + v + ', this)"' : '';
            var cellClass = 'value';
            if (v > 0)
                cellClass += ' has-value';
            if (isEdited)
                cellClass += ' edited';
            if (canEdit)
                cellClass += ' editable';
            var cellContent = v > 0 ? v : '-';
            if (isEdited) {
                cellContent = v + '<span class="original-value">元: ' + isEdited.original + '</span>';
            }
            html += '<td class="' + cellClass + '" data-row="' + ri + '" data-col="' + ci + '" data-date="' + d + '"' + editAttr + '>' + cellContent + '</td>';
        });
        html += '<td class="total-cell">' + row.total + '</td>';
        html += '<td class="del-cell"><button class="del-row-btn" onclick="deleteProduct(\'' + pEsc + '\')">✕</button></td></tr>';
    });
    var grandTotal = 0;
    Object.keys(dateTotals).forEach(function (k) { grandTotal += dateTotals[k]; });
    html += '<tr class="total-row"><td class="product">合計</td>';
    if (showTag1)
        html += '<td></td>';
    if (showTag2)
        html += '<td></td>';
    if (showTag3)
        html += '<td></td>';
    if (showCost)
        html += '<td></td>';
    if (showPrice)
        html += '<td></td>';
    if (showUnit)
        html += '<td></td>';
    dates.forEach(function (d, i) { html += '<td data-col="' + i + '">' + dateTotals[d] + '</td>'; });
    html += '<td>' + grandTotal + '</td><td></td></tr>';
    tbody.innerHTML = html;
    setupSelection();
    setupColumnResize();
    applySelectionHighlight();
    updateTagStats();
}
function setupSelection() {
    document.querySelectorAll('th.date-col').forEach(function (th) {
        th.onmousedown = function (e) {
            e.preventDefault();
            const c = parseInt(th.dataset.col);
            if (e.ctrlKey || e.metaKey) {
                // Ctrlキーで複数選択
                toggleCol(c);
            }
            else {
                // 通常クリックは選択を外さない（トグルのみ）
                if (!selectedCols.has(c)) {
                    isDraggingCol = true;
                    isDraggingRow = false;
                    dragStartCol = c;
                }
                toggleCol(c);
            }
            applySelectionHighlight();
        };
        th.onmouseenter = function () { if (isDraggingCol) {
            const c = parseInt(th.dataset.col);
            for (var i = Math.min(dragStartCol, c); i <= Math.max(dragStartCol, c); i++)
                selectedCols.add(i);
            applySelectionHighlight();
        } };
    });
    document.querySelectorAll('td.product').forEach(function (td) {
        if (td.closest('.total-row'))
            return;
        td.onmousedown = function (e) {
            e.preventDefault();
            const r = parseInt(td.dataset.row);
            if (e.ctrlKey || e.metaKey) {
                // Ctrlキーで複数選択
                toggleRow(r);
            }
            else {
                // 通常クリックは選択を外さない（トグルのみ）
                if (!selectedRows.has(r)) {
                    isDraggingRow = true;
                    isDraggingCol = false;
                    dragStartRow = r;
                }
                toggleRow(r);
            }
            applySelectionHighlight();
        };
        td.onmouseenter = function () { if (isDraggingRow) {
            const r = parseInt(td.dataset.row);
            for (var i = Math.min(dragStartRow, r); i <= Math.max(dragStartRow, r); i++)
                selectedRows.add(i);
            applySelectionHighlight();
        } };
    });
    // セル範囲選択機能
    document.querySelectorAll('td.value').forEach(function (td) {
        td.onmousedown = function (e) {
            if (e.target.tagName === 'INPUT')
                return; // 編集中は無視
            if (e.button !== 0)
                return; // 左クリックのみ
            cellDragTimer = window.setTimeout(function () {
                isDraggingCells = true;
                selectedCells.clear();
                cellDragStart = { row: parseInt(td.dataset.row), col: parseInt(td.dataset.col) };
                const cellKey = td.dataset.row + '-' + td.dataset.col;
                selectedCells.add(cellKey);
                applyCellSelection();
            }, LONG_PRESS_DURATION);
        };
        td.onmouseenter = function (e) {
            if (isDraggingCells && cellDragStart) {
                const currentRow = parseInt(td.dataset.row);
                const currentCol = parseInt(td.dataset.col);
                selectedCells.clear();
                const minRow = Math.min(cellDragStart.row, currentRow);
                const maxRow = Math.max(cellDragStart.row, currentRow);
                const minCol = Math.min(cellDragStart.col, currentCol);
                const maxCol = Math.max(cellDragStart.col, currentCol);
                for (var r = minRow; r <= maxRow; r++) {
                    for (var c = minCol; c <= maxCol; c++) {
                        selectedCells.add(r + '-' + c);
                    }
                }
                applyCellSelection();
            }
        };
        td.onmouseup = function (e) {
            if (cellDragTimer) {
                clearTimeout(cellDragTimer);
                cellDragTimer = null;
            }
        };
    });
}
var resizingCol = null, resizeStartX = 0, resizeStartWidth = 0;
function setupColumnResize() {
    document.querySelectorAll('#data-table th').forEach(function (th) {
        if (th.querySelector('.resizer'))
            return;
        var resizer = document.createElement('div');
        resizer.className = 'resizer';
        resizer.onmousedown = function (e) {
            e.preventDefault();
            e.stopPropagation();
            resizingCol = th;
            resizeStartX = e.pageX;
            resizeStartWidth = th.offsetWidth;
            resizer.classList.add('resizing');
            document.body.style.cursor = 'col-resize';
        };
        th.appendChild(resizer);
    });
}
document.addEventListener('mousemove', function (e) {
    if (resizingCol) {
        var newWidth = Math.max(30, resizeStartWidth + (e.pageX - resizeStartX));
        resizingCol.style.width = newWidth + 'px';
        var colIndex = Array.from(resizingCol.parentNode.children).indexOf(resizingCol);
        document.querySelectorAll('#data-table tbody tr').forEach(function (row) {
            var cell = row.children[colIndex];
            if (cell)
                cell.style.width = newWidth + 'px';
        });
    }
});
document.addEventListener('mouseup', function () {
    if (resizingCol) {
        var resizer = resizingCol.querySelector('.resizer');
        if (resizer)
            resizer.classList.remove('resizing');
        resizingCol = null;
        document.body.style.cursor = '';
    }
});
document.getElementById('table-scroll').onmouseup = function () { isDraggingCol = isDraggingRow = isDraggingCells = false; if (cellDragTimer) {
    clearTimeout(cellDragTimer);
    cellDragTimer = null;
} };
document.onmousemove = function (e) { if ((hasSelection() || selectedCells.size > 0) && !e.target.closest('.date-slider-track'))
    updateTooltip(e); };
function toggleCol(c) { selectedCols.has(c) ? selectedCols.delete(c) : selectedCols.add(c); }
function toggleRow(r) { selectedRows.has(r) ? selectedRows.delete(r) : selectedRows.add(r); }
function hasSelection() { return selectedCols.size > 0 || selectedRows.size > 0; }
function applyCellSelection() {
    document.querySelectorAll('td.value').forEach(function (td) {
        const cellKey = td.dataset.row + '-' + td.dataset.col;
        td.classList.toggle('cell-selected', selectedCells.has(cellKey));
    });
}
function applySelectionHighlight() {
    document.querySelectorAll('th.date-col').forEach(function (th) { th.classList.toggle('selected', selectedCols.has(parseInt(th.dataset.col))); });
    document.querySelectorAll('td.product').forEach(function (td) { const r = parseInt(td.dataset.row); if (!isNaN(r))
        td.classList.toggle('selected-row', selectedRows.has(r)); });
    document.querySelectorAll('td.value').forEach(function (td) {
        const c = parseInt(td.dataset.col), r = parseInt(td.dataset.row);
        td.classList.remove('selected-col', 'selected-cell');
        if (selectedCols.size > 0 && selectedRows.size > 0) {
            if (selectedCols.has(c) && selectedRows.has(r))
                td.classList.add('selected-cell');
        }
        else if (selectedCols.size > 0) {
            if (selectedCols.has(c))
                td.classList.add('selected-col');
        }
        else if (selectedRows.size > 0) {
            if (selectedRows.has(r))
                td.classList.add('selected-cell');
        }
    });
    const hint = document.getElementById('selection-hint'), info = document.getElementById('selection-info');
    if (!hasSelection()) {
        hint.classList.remove('show');
        return;
    }
    hint.classList.add('show');
    var parts = [];
    if (selectedCols.size > 0)
        parts.push('📅 ' + selectedCols.size + '日');
    if (selectedRows.size > 0)
        parts.push('📦 ' + selectedRows.size + '品目');
    info.textContent = parts.join(' × ');
}
function updateTooltip(e) {
    if (!hasSelection() && selectedCells.size === 0) {
        tooltip.classList.remove('show');
        return;
    }
    var tQty = 0, tCost = 0, tPrice = 0;
    var hdr, sub, dateStrs, prodNames;
    // セル範囲選択がある場合
    if (selectedCells.size > 0) {
        hdr = '📋 セル範囲集計';
        var cellRows = new Set(), cellCols = new Set();
        selectedCells.forEach(function (cellKey) {
            const parts = cellKey.split('-');
            const ri = parseInt(parts[0]);
            const ci = parseInt(parts[1]);
            cellRows.add(ri);
            cellCols.add(ci);
            const p = currentProducts[ri];
            const d = currentDates[ci];
            if (!p || !d)
                return;
            const info = (productInfo[p] || {});
            const q = currentPivot[p] ? (currentPivot[p][d] || 0) : 0;
            tQty += q;
            if (info.cost)
                tCost += q * info.cost;
            if (info.price)
                tPrice += q * info.price;
        });
        dateStrs = Array.from(cellCols).sort(function (a, b) { return a - b; }).map(function (c) { return currentDates[c]; }).filter(Boolean);
        prodNames = Array.from(cellRows).sort(function (a, b) { return a - b; }).map(function (r) { return currentProducts[r]; }).filter(Boolean);
        sub = (dateStrs[0] || '') + '〜' + (dateStrs[dateStrs.length - 1] || '') + ' / ' + cellRows.size + '品目 × ' + cellCols.size + '日';
    }
    else {
        // 通常の行・列選択
        const cols = selectedCols.size > 0 ? Array.from(selectedCols) : currentDates.map(function (_, i) { return i; });
        const rows = selectedRows.size > 0 ? Array.from(selectedRows) : currentProducts.map(function (_, i) { return i; });
        rows.forEach(function (ri) {
            const p = currentProducts[ri];
            if (!p)
                return;
            const info = (productInfo[p] || {});
            cols.forEach(function (ci) {
                const d = currentDates[ci];
                if (!d)
                    return;
                const q = currentPivot[p] ? (currentPivot[p][d] || 0) : 0;
                tQty += q;
                if (info.cost)
                    tCost += q * info.cost;
                if (info.price)
                    tPrice += q * info.price;
            });
        });
        hdr = selectedCols.size > 0 && selectedRows.size > 0 ? '📊 交点集計' : selectedCols.size > 0 ? '📅 期間集計' : '📦 品目集計';
        dateStrs = (selectedCols.size > 0 ? Array.from(selectedCols).sort(function (a, b) { return a - b; }).map(function (c) { return currentDates[c]; }) : currentDates).filter(Boolean);
        prodNames = (selectedRows.size > 0 ? Array.from(selectedRows).sort(function (a, b) { return a - b; }).map(function (r) { return currentProducts[r]; }) : currentProducts).filter(Boolean);
        sub = (dateStrs[0] || '') + '〜' + (dateStrs[dateStrs.length - 1] || '') + ' / ' + (prodNames.length <= 2 ? prodNames.join(', ') : prodNames[0] + ' 他' + (prodNames.length - 1) + '件');
    }
    const margin = tPrice > 0 ? ((tPrice - tCost) / tPrice * 100).toFixed(1) : 0;
    document.getElementById('tooltip-header').textContent = hdr;
    document.getElementById('tooltip-sub').textContent = sub;
    document.getElementById('tooltip-qty').textContent = tQty.toLocaleString();
    document.getElementById('tooltip-cost').textContent = '¥' + tCost.toLocaleString();
    document.getElementById('tooltip-price').textContent = '¥' + tPrice.toLocaleString();
    document.getElementById('tooltip-profit').textContent = '¥' + (tPrice - tCost).toLocaleString();
    document.getElementById('tooltip-margin').textContent = margin + '%';
    var left = e.clientX + 12, top = e.clientY + 12;
    if (left + 220 > window.innerWidth)
        left = e.clientX - 220;
    if (top + 180 > window.innerHeight)
        top = e.clientY - 180;
    tooltip.style.left = left + 'px';
    tooltip.style.top = top + 'px';
    tooltip.classList.add('show');
}
function clearSelection() { selectedCols.clear(); selectedRows.clear(); selectedCells.clear(); applySelectionHighlight(); applyCellSelection(); tooltip.classList.remove('show'); }
function printTable() {
    const dates = getFilteredDates();
    const meta = '期間: ' + (dates[0] || '-') + ' 〜 ' + (dates[dates.length - 1] || '-') + ' / 出力日時: ' + new Date().toLocaleString('ja-JP');
    document.getElementById('print-meta').textContent = meta;
    window.print();
}
function exportToExcel() {
    const filtered = getFilteredData();
    if (filtered.length === 0) {
        alert('データがありません');
        return;
    }
    const dates = getFilteredDates();
    const showTag1 = document.getElementById('show-tag1').checked;
    const showTag2 = document.getElementById('show-tag2').checked;
    const showTag3 = document.getElementById('show-tag3').checked;
    const pivot = {};
    filtered.forEach(function (i) { if (!pivot[i.product]) {
        pivot[i.product] = { total: 0 };
        dates.forEach(function (d) { pivot[i.product][d] = 0; });
    } pivot[i.product][i.date] += i.quantity; pivot[i.product].total += i.quantity; });
    const wsData = [], hdr = ['品目名'];
    if (showTag1)
        hdr.push('#大分類');
    if (showTag2)
        hdr.push('#中分類');
    if (showTag3)
        hdr.push('#小分類');
    hdr.push('原価', '売価');
    dates.forEach(function (d) { hdr.push(d); });
    hdr.push('合計');
    wsData.push(hdr);
    Object.keys(pivot).sort().forEach(function (p) {
        const info = (productInfo[p] || {}), row = [p];
        if (showTag1)
            row.push(getTag(p, 1));
        if (showTag2)
            row.push(getTag(p, 2));
        if (showTag3)
            row.push(getTag(p, 3));
        row.push(info.cost || '', info.price || '');
        dates.forEach(function (d) { row.push(pivot[p][d] || 0); });
        row.push(pivot[p].total);
        wsData.push(row);
    });
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(wsData), '発注データ');
    XLSX.writeFile(wb, '発注データ_' + new Date().toISOString().slice(0, 10) + '.xlsx');
}
function exportToCSV() {
    const filtered = getFilteredData();
    if (filtered.length === 0) {
        alert('データがありません');
        return;
    }
    const dates = getFilteredDates();
    const showTag1 = document.getElementById('show-tag1').checked;
    const showTag2 = document.getElementById('show-tag2').checked;
    const showTag3 = document.getElementById('show-tag3').checked;
    const pivot = {};
    filtered.forEach(function (i) { if (!pivot[i.product]) {
        pivot[i.product] = { total: 0 };
        dates.forEach(function (d) { pivot[i.product][d] = 0; });
    } pivot[i.product][i.date] += i.quantity; pivot[i.product].total += i.quantity; });
    var csv = '\uFEFF品目名';
    if (showTag1)
        csv += ',#大分類';
    if (showTag2)
        csv += ',#中分類';
    if (showTag3)
        csv += ',#小分類';
    csv += ',原価,売価,' + dates.join(',') + ',合計\n';
    Object.keys(pivot).sort().forEach(function (p) {
        const info = (productInfo[p] || {});
        csv += '"' + p + '"';
        if (showTag1)
            csv += ',"' + getTag(p, 1) + '"';
        if (showTag2)
            csv += ',"' + getTag(p, 2) + '"';
        if (showTag3)
            csv += ',"' + getTag(p, 3) + '"';
        csv += ',' + (info.cost || '') + ',' + (info.price || '');
        dates.forEach(function (d) { csv += ',' + (pivot[p][d] || 0); });
        csv += ',' + pivot[p].total + '\n';
    });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8;' }));
    link.download = '発注データ_' + new Date().toISOString().slice(0, 10) + '.csv';
    link.click();
}
function exportTagStats() {
    const wsData = [['大分類', '中分類', '小分類', '数量', '原価計', '売価計', '粗利', '値入率']];
    currentProducts.forEach(function (p) {
        const t1 = getTag(p, 1) || '', t2 = getTag(p, 2) || '', t3 = getTag(p, 3) || '';
        if (!t1 && !t2 && !t3)
            return;
        const info = (productInfo[p] || {});
        const qty = currentPivot[p] ? (currentPivot[p].total || 0) : 0;
        const cost = (info.cost || 0) * qty;
        const price = (info.price || 0) * qty;
        const profit = price - cost;
        const margin = price > 0 ? ((profit / price) * 100).toFixed(1) + '%' : '0%';
        wsData.push([t1, t2, t3, qty, cost, price, profit, margin]);
    });
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(wsData), 'タグ別集計');
    XLSX.writeFile(wb, 'タグ別集計_' + new Date().toISOString().slice(0, 10) + '.xlsx');
}
function exportTagTemplate() {
    if (currentProducts.length === 0) {
        showToast('データがありません');
        return;
    }
    const wsData = [['品目名', '#大分類', '#中分類', '#小分類', '原価', '売価', '入数']];
    currentProducts.forEach(function (p) {
        const info = (productInfo[p] || {});
        wsData.push([
            p,
            getTag(p, 1) || '',
            getTag(p, 2) || '',
            getTag(p, 3) || '',
            info.cost || '',
            info.price || '',
            info.unit || ''
        ]);
    });
    const wb = XLSX.utils.book_new();
    const ws = XLSX.utils.aoa_to_sheet(wsData);
    ws['!cols'] = [{ wch: 30 }, { wch: 15 }, { wch: 15 }, { wch: 15 }, { wch: 8 }, { wch: 8 }, { wch: 8 }];
    XLSX.utils.book_append_sheet(wb, ws, 'タグ設定');
    XLSX.writeFile(wb, 'タグ設定テンプレート_' + new Date().toISOString().slice(0, 10) + '.xlsx');
    showToast('📤 テンプレートを出力しました');
}
document.onclick = function (e) {
    if (!e.target.closest('.dropdown'))
        document.querySelectorAll('.dropdown-menu').forEach(function (d) { d.classList.remove('show'); });
    if (!e.target.closest('.table-wrap') && !e.target.closest('.selection-tooltip') && !e.target.closest('.selection-hint'))
        clearSelection();
};
// Keyboard shortcuts
document.addEventListener('keydown', function (e) {
    // Esc: Close modals or clear selection
    if (e.key === 'Escape') {
        const modals = document.querySelectorAll('.modal.show');
        if (modals.length > 0) {
            modals.forEach(m => m.classList.remove('show'));
            calendarQuantities = {};
        }
        else {
            clearSelection();
        }
    }
    // Ctrl+S: Save data (prevent default browser save)
    if (e.ctrlKey && e.key === 's') {
        e.preventDefault();
        if (loadedFiles.length > 0) {
            showSaveModal();
        }
    }
    // Ctrl+N: Add new product
    if (e.ctrlKey && e.key === 'n') {
        e.preventDefault();
        if (loadedFiles.length > 0) {
            showAddProductModal();
        }
    }
    // Ctrl+H: Show help
    if (e.ctrlKey && e.key === 'h') {
        e.preventDefault();
        showHelpModal();
    }
});
initDatabase().then(function () { renderSavedList(); }).catch(function (err) { console.error('DB初期化エラー:', err); });
// Export functions to global scope for HTML onclick handlers
window.toggleFilesBar = toggleFilesBar;
window.toggleSavedList = toggleSavedList;
window.showSaveModal = showSaveModal;
window.closeSaveModal = closeSaveModal;
window.saveToDatabase = saveToDatabase;
window.loadFromDB = loadFromDB;
window.deleteFromDB = deleteFromDB;
window.showAddProductModal = showAddProductModal;
window.closeAddProductModal = closeAddProductModal;
window.showHelpModal = showHelpModal;
window.closeHelpModal = closeHelpModal;
window.addProduct = addProduct;
window.addProductWithCalendar = addProductWithCalendar;
window.prevMonth = prevMonth;
window.nextMonth = nextMonth;
window.deleteProduct = deleteProduct;
window.editCell = editCell;
window.toggleFullscreen = toggleFullscreen;
window.updateTable = updateTable;
window.toggleDropdown = toggleDropdown;
window.toggleStore = toggleStore;
window.toggleSupplier = toggleSupplier;
window.selectAllStores = selectAllStores;
window.clearAllStores = clearAllStores;
window.selectAllSuppliers = selectAllSuppliers;
window.clearAllSuppliers = clearAllSuppliers;
window.removeFile = removeFile;
window.toggleFileFilter = toggleFileFilter;
window.selectAllFiles = selectAllFiles;
window.clearAllFileFilters = clearAllFileFilters;
window.setTag = setTag;
window.importTags = importTags;
window.printTable = printTable;
window.exportToExcel = exportToExcel;
window.exportToCSV = exportToCSV;
window.exportTagStats = exportTagStats;
window.exportTagTemplate = exportTagTemplate;
window.clearSelection = clearSelection;
window.toggleTagStats = toggleTagStats;
// Firebase cloud sync functions
window.showCloudSyncModal = FirebaseSync.showCloudSyncModal;
window.closeCloudSyncModal = FirebaseSync.closeCloudSyncModal;
window.initFirebase = FirebaseSync.initFirebase;
window.autoInitFirebase = FirebaseSync.autoInitFirebase;
window.createRoom = FirebaseSync.createRoom;
window.joinRoom = FirebaseSync.joinRoom;
window.uploadToCloud = FirebaseSync.uploadToCloud;
window.downloadFromCloud = FirebaseSync.downloadFromCloud;
window.enableAutoSync = FirebaseSync.enableAutoSync;
window.leaveRoom = FirebaseSync.leaveRoom;
// Export data for Firebase sync
window.loadedFiles = loadedFiles;
window.rawData = rawData;
window.productInfo = productInfo;
window.productTags = productTags;
window.cellEdits = cellEdits;
window.mergeAllData = mergeAllData;
window.updateFileChips = updateFileChips;
window.initUI = initUI;
window.showToast = showToast;
//# sourceMappingURL=app.js.map