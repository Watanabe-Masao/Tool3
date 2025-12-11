/**
 * Firebase Cloud Sync Module
 * PC とスマートフォン間でデータを同期
 */
import { DEFAULT_FIREBASE_CONFIG } from './env-config.js';
// Firebase インスタンス
let firebaseApp = null;
let firestore = null;
let auth = null;
let currentRoomCode = null;
let autoSyncEnabled = false;
let unsubscribe = null;
/**
 * Firebase を初期化
 */
export function initFirebase() {
    const apiKey = document.getElementById('firebase-api-key').value.trim();
    const projectId = document.getElementById('firebase-project-id').value.trim();
    const appId = document.getElementById('firebase-app-id').value.trim();
    if (!apiKey || !projectId || !appId) {
        alert('❌ 全ての項目を入力してください');
        return;
    }
    try {
        const firebaseConfig = {
            apiKey: apiKey,
            authDomain: `${projectId}.firebaseapp.com`,
            projectId: projectId,
            storageBucket: `${projectId}.firebasestorage.app`,
            messagingSenderId: appId.split(':')[1],
            appId: appId
        };
        initializeFirebaseWithConfig(firebaseConfig);
    }
    catch (error) {
        console.error('Firebase init error:', error);
        alert('❌ Firebase初期化エラー: ' + error.message);
    }
}
/**
 * デフォルト設定でFirebaseを自動初期化
 */
export function autoInitFirebase() {
    // 既に初期化済みの場合はスキップ
    if (firebaseApp) {
        return;
    }
    // localStorageに保存された設定を優先
    const savedConfig = localStorage.getItem('firebaseConfig');
    const config = savedConfig ? JSON.parse(savedConfig) : DEFAULT_FIREBASE_CONFIG;
    initializeFirebaseWithConfig(config);
}
/**
 * Firebase設定で初期化（共通処理）
 */
function initializeFirebaseWithConfig(firebaseConfig) {
    try {
        // Firebase初期化
        if (!firebaseApp) {
            firebaseApp = firebase.initializeApp(firebaseConfig);
        }
        firestore = firebase.firestore();
        auth = firebase.auth();
        // オフライン永続化を有効化（ネットワーク接続が不安定な環境でもデータを保持）
        firestore.enablePersistence({ synchronizeTabs: true })
            .catch((err) => {
            if (err.code === 'failed-precondition') {
                console.warn('⚠️ 複数タブで開いているためオフライン機能が制限されています');
            }
            else if (err.code === 'unimplemented') {
                console.warn('⚠️ ブラウザがオフライン機能に対応していません');
            }
            else {
                console.error('Persistence error:', err);
            }
        });
        // 匿名認証
        auth.signInAnonymously()
            .then(() => {
            showToast('✅ Firebase接続成功');
            // 設定をlocalStorageに保存
            localStorage.setItem('firebaseConfig', JSON.stringify(firebaseConfig));
            // UI切替
            document.getElementById('firebase-setup-section').style.display = 'none';
            document.getElementById('firebase-sync-section').style.display = 'block';
            updateSyncStatus('接続済み', true);
            // 保存されたルームコードがあれば自動参加
            const savedRoomCode = localStorage.getItem('currentRoomCode');
            if (savedRoomCode) {
                currentRoomCode = savedRoomCode;
                document.getElementById('room-code-input').value = savedRoomCode;
                document.getElementById('sync-actions').style.display = 'block';
                updateSyncStatus(`ルーム: ${savedRoomCode}`, true);
            }
        })
            .catch((error) => {
            console.error('Firebase auth error:', error);
            alert('❌ Firebase認証エラー: ' + error.message);
        });
    }
    catch (error) {
        console.error('Firebase init error:', error);
        alert('❌ Firebase初期化エラー: ' + error.message);
    }
}
/**
 * ルームコードを生成（6桁英数字）
 */
function generateRoomCode() {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
    let code = '';
    for (let i = 0; i < 6; i++) {
        code += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return code;
}
/**
 * 新しいルームを作成
 */
export function createRoom() {
    if (!firestore) {
        alert('❌ 先にFirebaseに接続してください');
        return;
    }
    const roomCode = generateRoomCode();
    currentRoomCode = roomCode;
    // ルームコード表示
    document.getElementById('room-code-value').textContent = roomCode;
    document.getElementById('created-room-code').style.display = 'block';
    document.getElementById('sync-actions').style.display = 'block';
    // ルームコードをlocalStorageに保存
    localStorage.setItem('currentRoomCode', roomCode);
    showToast(`✅ ルーム作成: ${roomCode}`);
    updateSyncStatus(`ルーム: ${roomCode}`, true);
}
/**
 * 既存のルームに参加
 */
export function joinRoom() {
    if (!firestore) {
        alert('❌ 先にFirebaseに接続してください');
        return;
    }
    const input = document.getElementById('room-code-input');
    const roomCode = input.value.trim().toUpperCase();
    if (roomCode.length !== 6) {
        alert('❌ 6桁のルームコードを入力してください');
        return;
    }
    currentRoomCode = roomCode;
    // ルームコードをlocalStorageに保存
    localStorage.setItem('currentRoomCode', roomCode);
    document.getElementById('sync-actions').style.display = 'block';
    showToast(`✅ ルーム参加: ${roomCode}`);
    updateSyncStatus(`ルーム: ${roomCode}`, true);
    // 自動的にデータを取得
    downloadFromCloud();
}
// チャンクサイズ（500KB - Firestoreのフィールド値制限に余裕を持たせる）
const CHUNK_SIZE = 500 * 1024;
/**
 * クラウドにデータをアップロード（チャンク分割対応）
 */
export async function uploadToCloud() {
    if (!firestore || !currentRoomCode) {
        alert('❌ 先にルームに参加してください');
        return;
    }
    try {
        showToast('⏳ アップロード中...');
        // グローバル変数からデータを取得
        const dataToUpload = {
            loadedFiles: window.loadedFiles || [],
            rawData: window.rawData || {},
            productInfo: window.productInfo || {},
            productTags: window.productTags || {},
            cellEdits: window.cellEdits || {}
        };
        // JSONに変換
        const jsonString = JSON.stringify(dataToUpload);
        const totalSize = jsonString.length;
        // チャンクに分割
        const chunks = [];
        for (let i = 0; i < jsonString.length; i += CHUNK_SIZE) {
            chunks.push(jsonString.slice(i, i + CHUNK_SIZE));
        }
        // 既存のチャンクを削除
        const existingChunks = await firestore.collection('rooms').doc(currentRoomCode).collection('chunks').get();
        const deletePromises = existingChunks.docs.map(doc => doc.ref.delete());
        await Promise.all(deletePromises);
        // 新しいチャンクをアップロード
        const uploadPromises = chunks.map((chunk, index) => {
            return firestore.collection('rooms').doc(currentRoomCode).collection('chunks').doc(String(index)).set({
                data: chunk,
                index: index
            });
        });
        await Promise.all(uploadPromises);
        // メインドキュメントにメタデータを保存
        await firestore.collection('rooms').doc(currentRoomCode).set({
            chunkCount: chunks.length,
            totalSize: totalSize,
            timestamp: new Date().toISOString(),
            deviceId: getDeviceId()
        });
        showToast(`✅ アップロード完了 (${(totalSize / 1024 / 1024).toFixed(2)}MB)`);
    }
    catch (error) {
        console.error('Upload error:', error);
        alert('❌ アップロードエラー: ' + error.message);
    }
}
/**
 * クラウドからデータをダウンロード（チャンク分割対応）
 */
export async function downloadFromCloud() {
    if (!firestore || !currentRoomCode) {
        alert('❌ 先にルームに参加してください');
        return;
    }
    try {
        showToast('⏳ ダウンロード中...');
        // メインドキュメントを取得
        const mainDoc = await firestore.collection('rooms').doc(currentRoomCode).get();
        if (!mainDoc.exists) {
            showToast('ℹ️ ルームにデータがありません');
            return;
        }
        const metadata = mainDoc.data();
        // チャンク分割されたデータかどうかを確認
        if (metadata.chunkCount) {
            // チャンクを取得して結合
            const chunksSnapshot = await firestore.collection('rooms').doc(currentRoomCode).collection('chunks').orderBy('index').get();
            if (chunksSnapshot.empty) {
                showToast('ℹ️ ルームにデータがありません');
                return;
            }
            // チャンクを結合
            let jsonString = '';
            chunksSnapshot.docs.forEach(doc => {
                jsonString += doc.data().data;
            });
            // JSONをパース
            const data = JSON.parse(jsonString);
            // データを復元
            if (data.loadedFiles) window.loadedFiles = data.loadedFiles;
            if (data.rawData) window.rawData = data.rawData;
            if (data.productInfo) window.productInfo = data.productInfo;
            if (data.productTags) window.productTags = data.productTags;
            if (data.cellEdits) window.cellEdits = data.cellEdits;
        } else {
            // 旧形式（チャンク分割なし）のデータ
            if (metadata.loadedFiles) window.loadedFiles = metadata.loadedFiles;
            if (metadata.rawData) window.rawData = metadata.rawData;
            if (metadata.productInfo) window.productInfo = metadata.productInfo;
            if (metadata.productTags) window.productTags = metadata.productTags;
            if (metadata.cellEdits) window.cellEdits = metadata.cellEdits;
        }
        // UIを更新
        window.mergeAllData();
        window.updateFileChips();
        window.initUI();
        // ドロップゾーンを非表示、メインコンテンツを表示
        const dropZone = document.getElementById('drop-zone');
        const filesBar = document.getElementById('files-bar');
        const mainContent = document.getElementById('main-content');
        if (dropZone) dropZone.style.display = 'none';
        if (filesBar) filesBar.classList.add('show');
        if (mainContent) mainContent.classList.add('show');
        showToast('✅ クラウドからデータ取得完了');
    }
    catch (error) {
        console.error('Download error:', error);
        alert('❌ ダウンロードエラー: ' + error.message);
    }
}
/**
 * 自動同期を有効化
 */
export function enableAutoSync() {
    if (!firestore || !currentRoomCode) {
        alert('❌ 先にルームに参加してください');
        return;
    }
    if (autoSyncEnabled) {
        // 自動同期を無効化
        if (unsubscribe) {
            unsubscribe();
            unsubscribe = null;
        }
        autoSyncEnabled = false;
        document.getElementById('auto-sync-btn').textContent = '🔄 自動同期を有効化';
        showToast('自動同期を無効化しました');
    }
    else {
        // 自動同期を有効化
        unsubscribe = firestore.collection('rooms').doc(currentRoomCode)
            .onSnapshot((doc) => {
            if (!doc.exists)
                return;
            const data = doc.data();
            // 自分のデバイスからのアップロードは無視
            if (data.deviceId === getDeviceId())
                return;
            // データを復元
            if (data.loadedFiles)
                window.loadedFiles = data.loadedFiles;
            if (data.rawData)
                window.rawData = data.rawData;
            if (data.productInfo)
                window.productInfo = data.productInfo;
            if (data.productTags)
                window.productTags = data.productTags;
            if (data.cellEdits)
                window.cellEdits = data.cellEdits;
            // UIを更新
            window.mergeAllData();
            window.updateFileChips();
            window.initUI();
            showToast('🔄 他デバイスからデータ同期');
        });
        autoSyncEnabled = true;
        document.getElementById('auto-sync-btn').textContent = '⏸️ 自動同期を無効化';
        showToast('✅ 自動同期を有効化しました');
    }
}
/**
 * ルームから退出
 */
export function leaveRoom() {
    if (unsubscribe) {
        unsubscribe();
        unsubscribe = null;
    }
    autoSyncEnabled = false;
    currentRoomCode = null;
    localStorage.removeItem('currentRoomCode');
    document.getElementById('sync-actions').style.display = 'none';
    document.getElementById('created-room-code').style.display = 'none';
    document.getElementById('room-code-input').value = '';
    updateSyncStatus('接続済み', true);
    showToast('ルームから退出しました');
}
/**
 * 同期ステータスを更新
 */
function updateSyncStatus(text, connected) {
    const statusEl = document.getElementById('sync-status');
    const textEl = document.getElementById('sync-status-text');
    textEl.textContent = text;
    if (connected) {
        statusEl.classList.add('connected');
    }
    else {
        statusEl.classList.remove('connected');
    }
}
/**
 * デバイスIDを取得または生成
 */
function getDeviceId() {
    let deviceId = localStorage.getItem('deviceId');
    if (!deviceId) {
        deviceId = 'device_' + Math.random().toString(36).substr(2, 9);
        localStorage.setItem('deviceId', deviceId);
    }
    return deviceId;
}
/**
 * クラウド同期モーダルを表示
 */
export function showCloudSyncModal() {
    // デフォルト設定を入力欄に表示
    const savedConfig = localStorage.getItem('firebaseConfig');
    const config = savedConfig ? JSON.parse(savedConfig) : DEFAULT_FIREBASE_CONFIG;
    document.getElementById('firebase-api-key').value = config.apiKey || '';
    document.getElementById('firebase-project-id').value = config.projectId || '';
    document.getElementById('firebase-app-id').value = config.appId || '';
    // Firebase未初期化の場合は自動接続
    if (!firebaseApp) {
        autoInitFirebase();
    }
    // 保存されたルームコードを復元
    const savedRoomCode = localStorage.getItem('currentRoomCode');
    if (savedRoomCode && firestore) {
        currentRoomCode = savedRoomCode;
        document.getElementById('room-code-input').value = savedRoomCode;
    }
    // ファイル選択リストを更新
    updateUploadFileList();
    document.getElementById('cloud-sync-modal').classList.add('show');
}
/**
 * アップロードファイル選択リストを更新
 */
export function updateUploadFileList() {
    const listEl = document.getElementById('upload-file-list');
    if (!listEl) return;
    const loadedFiles = window.loadedFiles || [];
    const rawData = window.rawData || {};
    if (loadedFiles.length === 0) {
        listEl.innerHTML = '<div class="no-files-msg">読み込まれたファイルがありません</div>';
        return;
    }
    listEl.innerHTML = loadedFiles.map(fileName => {
        const fileData = rawData[fileName] || [];
        const dataSize = JSON.stringify(fileData).length;
        const sizeStr = dataSize > 1024 * 1024
            ? (dataSize / 1024 / 1024).toFixed(2) + ' MB'
            : (dataSize / 1024).toFixed(1) + ' KB';
        return `
            <label class="file-checkbox-item">
                <input type="checkbox" value="${fileName}" checked>
                <span class="file-name">${fileName}</span>
                <span class="file-size">${sizeStr}</span>
            </label>
        `;
    }).join('');
}
/**
 * 全ファイルを選択
 */
export function selectAllUploadFiles() {
    const checkboxes = document.querySelectorAll('#upload-file-list input[type="checkbox"]');
    checkboxes.forEach(cb => cb.checked = true);
}
/**
 * 全ファイルの選択を解除
 */
export function clearAllUploadFiles() {
    const checkboxes = document.querySelectorAll('#upload-file-list input[type="checkbox"]');
    checkboxes.forEach(cb => cb.checked = false);
}
/**
 * 選択されたファイルのみをアップロード
 */
export async function uploadSelectedFiles() {
    if (!firestore || !currentRoomCode) {
        alert('❌ 先にルームに参加してください');
        return;
    }
    // 選択されたファイルを取得
    const checkboxes = document.querySelectorAll('#upload-file-list input[type="checkbox"]:checked');
    const selectedFiles = Array.from(checkboxes).map(cb => cb.value);
    if (selectedFiles.length === 0) {
        alert('❌ アップロードするファイルを選択してください');
        return;
    }
    try {
        showToast(`⏳ ${selectedFiles.length}ファイルをアップロード中...`);
        // 選択されたファイルのデータのみを抽出
        const rawData = window.rawData || {};
        const productInfo = window.productInfo || {};
        const productTags = window.productTags || {};
        const cellEdits = window.cellEdits || {};
        const dataToUpload = {
            loadedFiles: selectedFiles,
            rawData: {},
            productInfo: {},
            productTags: productTags,  // タグは全体で共有
            cellEdits: {}
        };
        // 選択されたファイルのデータのみをコピー
        selectedFiles.forEach(fileName => {
            if (rawData[fileName]) {
                dataToUpload.rawData[fileName] = rawData[fileName];
            }
        });
        // 選択されたファイルに含まれる商品の情報をコピー
        const selectedProducts = new Set();
        selectedFiles.forEach(fileName => {
            const fileData = rawData[fileName] || [];
            fileData.forEach(row => {
                if (row['商品名']) {
                    selectedProducts.add(row['商品名']);
                }
            });
        });
        // 手動追加された商品（どのファイルにも含まれない商品）も含める
        const allFileProducts = new Set();
        Object.values(rawData).forEach(fileData => {
            (fileData || []).forEach(row => {
                if (row['商品名']) {
                    allFileProducts.add(row['商品名']);
                }
            });
        });
        // productInfoにあるがどのファイルにも含まれない商品 = 手動追加商品
        Object.keys(productInfo).forEach(productName => {
            if (!allFileProducts.has(productName)) {
                selectedProducts.add(productName);  // 手動追加商品を含める
            }
        });
        selectedProducts.forEach(productName => {
            if (productInfo[productName]) {
                dataToUpload.productInfo[productName] = productInfo[productName];
            }
        });
        // セル編集も選択されたファイルに関連するものと、手動追加分を含める
        Object.keys(cellEdits).forEach(key => {
            const parts = key.split('_');
            const fileName = parts.slice(0, -2).join('_');
            // 選択ファイルに関連 OR どのファイルにも関連しない（手動編集）
            const isRelatedToSelectedFile = selectedFiles.includes(fileName) || selectedFiles.some(f => key.includes(f));
            const isManualEdit = !Object.keys(rawData).some(f => key.includes(f));
            if (isRelatedToSelectedFile || isManualEdit) {
                dataToUpload.cellEdits[key] = cellEdits[key];
            }
        });
        // JSONに変換
        const jsonString = JSON.stringify(dataToUpload);
        const totalSize = jsonString.length;
        // チャンクに分割
        const chunks = [];
        for (let i = 0; i < jsonString.length; i += CHUNK_SIZE) {
            chunks.push(jsonString.slice(i, i + CHUNK_SIZE));
        }
        // 既存のチャンクを削除
        const existingChunks = await firestore.collection('rooms').doc(currentRoomCode).collection('chunks').get();
        const deletePromises = existingChunks.docs.map(doc => doc.ref.delete());
        await Promise.all(deletePromises);
        // 新しいチャンクをアップロード
        const uploadPromises = chunks.map((chunk, index) => {
            return firestore.collection('rooms').doc(currentRoomCode).collection('chunks').doc(String(index)).set({
                data: chunk,
                index: index
            });
        });
        await Promise.all(uploadPromises);
        // メインドキュメントにメタデータを保存
        await firestore.collection('rooms').doc(currentRoomCode).set({
            chunkCount: chunks.length,
            totalSize: totalSize,
            fileCount: selectedFiles.length,
            files: selectedFiles,
            timestamp: new Date().toISOString(),
            deviceId: getDeviceId()
        });
        showToast(`✅ ${selectedFiles.length}ファイルをアップロード完了 (${(totalSize / 1024 / 1024).toFixed(2)}MB)`);
    }
    catch (error) {
        console.error('Upload error:', error);
        alert('❌ アップロードエラー: ' + error.message);
    }
}
/**
 * クラウド同期モーダルを閉じる
 */
export function closeCloudSyncModal() {
    document.getElementById('cloud-sync-modal').classList.remove('show');
}
/**
 * トースト通知を表示（app.tsの関数を使用）
 */
function showToast(message) {
    window.showToast(message);
}
//# sourceMappingURL=firebase.js.map