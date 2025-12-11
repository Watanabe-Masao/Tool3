/**
 * Firebase Cloud Sync Module
 * PC とスマートフォン間でデータを同期
 */

import { DEFAULT_FIREBASE_CONFIG } from './env-config';

declare const firebase: any;

// Firebase インスタンス
let firebaseApp: any = null;
let firestore: any = null;
let auth: any = null;
let currentRoomCode: string | null = null;
let autoSyncEnabled: boolean = false;
let unsubscribe: (() => void) | null = null;

/**
 * Firebase を初期化
 */
export function initFirebase(): void {
  const apiKey = (document.getElementById('firebase-api-key') as HTMLInputElement).value.trim();
  const projectId = (document.getElementById('firebase-project-id') as HTMLInputElement).value.trim();
  const appId = (document.getElementById('firebase-app-id') as HTMLInputElement).value.trim();

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

  } catch (error: any) {
    console.error('Firebase init error:', error);
    alert('❌ Firebase初期化エラー: ' + error.message);
  }
}

/**
 * デフォルト設定でFirebaseを自動初期化
 */
export function autoInitFirebase(): void {
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
function initializeFirebaseWithConfig(firebaseConfig: any): void {
  try {
    // Firebase初期化
    if (!firebaseApp) {
      firebaseApp = firebase.initializeApp(firebaseConfig);
    }

    firestore = firebase.firestore();
    auth = firebase.auth();

    // 匿名認証
    auth.signInAnonymously()
      .then(() => {
        showToast('✅ Firebase接続成功');

        // 設定をlocalStorageに保存
        localStorage.setItem('firebaseConfig', JSON.stringify(firebaseConfig));

        // UI切替
        document.getElementById('firebase-setup-section')!.style.display = 'none';
        document.getElementById('firebase-sync-section')!.style.display = 'block';
        updateSyncStatus('接続済み', true);

        // 保存されたルームコードがあれば自動参加
        const savedRoomCode = localStorage.getItem('currentRoomCode');
        if (savedRoomCode) {
          currentRoomCode = savedRoomCode;
          (document.getElementById('room-code-input') as HTMLInputElement).value = savedRoomCode;
          document.getElementById('sync-actions')!.style.display = 'block';
          updateSyncStatus(`ルーム: ${savedRoomCode}`, true);
        }
      })
      .catch((error: any) => {
        console.error('Firebase auth error:', error);
        alert('❌ Firebase認証エラー: ' + error.message);
      });

  } catch (error: any) {
    console.error('Firebase init error:', error);
    alert('❌ Firebase初期化エラー: ' + error.message);
  }
}

/**
 * ルームコードを生成（6桁英数字）
 */
function generateRoomCode(): string {
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
export function createRoom(): void {
  if (!firestore) {
    alert('❌ 先にFirebaseに接続してください');
    return;
  }

  const roomCode = generateRoomCode();
  currentRoomCode = roomCode;

  // ルームコード表示
  document.getElementById('room-code-value')!.textContent = roomCode;
  document.getElementById('created-room-code')!.style.display = 'block';
  document.getElementById('sync-actions')!.style.display = 'block';

  // ルームコードをlocalStorageに保存
  localStorage.setItem('currentRoomCode', roomCode);

  showToast(`✅ ルーム作成: ${roomCode}`);
  updateSyncStatus(`ルーム: ${roomCode}`, true);
}

/**
 * 既存のルームに参加
 */
export function joinRoom(): void {
  if (!firestore) {
    alert('❌ 先にFirebaseに接続してください');
    return;
  }

  const input = document.getElementById('room-code-input') as HTMLInputElement;
  const roomCode = input.value.trim().toUpperCase();

  if (roomCode.length !== 6) {
    alert('❌ 6桁のルームコードを入力してください');
    return;
  }

  currentRoomCode = roomCode;

  // ルームコードをlocalStorageに保存
  localStorage.setItem('currentRoomCode', roomCode);

  document.getElementById('sync-actions')!.style.display = 'block';
  showToast(`✅ ルーム参加: ${roomCode}`);
  updateSyncStatus(`ルーム: ${roomCode}`, true);

  // 自動的にデータを取得
  downloadFromCloud();
}

/**
 * クラウドにデータをアップロード
 */
export function uploadToCloud(): void {
  if (!firestore || !currentRoomCode) {
    alert('❌ 先にルームに参加してください');
    return;
  }

  // グローバル変数からデータを取得（app.tsで定義されている）
  const dataToUpload = {
    loadedFiles: (window as any).loadedFiles || [],
    rawData: (window as any).rawData || {},
    productInfo: (window as any).productInfo || {},
    productTags: (window as any).productTags || {},
    cellEdits: (window as any).cellEdits || {},
    timestamp: new Date().toISOString(),
    deviceId: getDeviceId()
  };

  firestore.collection('rooms').doc(currentRoomCode).set(dataToUpload)
    .then(() => {
      showToast('✅ クラウドにアップロード完了');
    })
    .catch((error: any) => {
      console.error('Upload error:', error);
      alert('❌ アップロードエラー: ' + error.message);
    });
}

/**
 * クラウドからデータをダウンロード
 */
export function downloadFromCloud(): void {
  if (!firestore || !currentRoomCode) {
    alert('❌ 先にルームに参加してください');
    return;
  }

  firestore.collection('rooms').doc(currentRoomCode).get()
    .then((doc: any) => {
      if (!doc.exists) {
        showToast('ℹ️ ルームにデータがありません');
        return;
      }

      const data = doc.data();

      // データを復元
      if (data.loadedFiles) (window as any).loadedFiles = data.loadedFiles;
      if (data.rawData) (window as any).rawData = data.rawData;
      if (data.productInfo) (window as any).productInfo = data.productInfo;
      if (data.productTags) (window as any).productTags = data.productTags;
      if (data.cellEdits) (window as any).cellEdits = data.cellEdits;

      // UIを更新
      (window as any).mergeAllData();
      (window as any).updateFileChips();
      (window as any).initUI();

      showToast('✅ クラウドからデータ取得完了');
    })
    .catch((error: any) => {
      console.error('Download error:', error);
      alert('❌ ダウンロードエラー: ' + error.message);
    });
}

/**
 * 自動同期を有効化
 */
export function enableAutoSync(): void {
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
    document.getElementById('auto-sync-btn')!.textContent = '🔄 自動同期を有効化';
    showToast('自動同期を無効化しました');
  } else {
    // 自動同期を有効化
    unsubscribe = firestore.collection('rooms').doc(currentRoomCode)
      .onSnapshot((doc: any) => {
        if (!doc.exists) return;

        const data = doc.data();

        // 自分のデバイスからのアップロードは無視
        if (data.deviceId === getDeviceId()) return;

        // データを復元
        if (data.loadedFiles) (window as any).loadedFiles = data.loadedFiles;
        if (data.rawData) (window as any).rawData = data.rawData;
        if (data.productInfo) (window as any).productInfo = data.productInfo;
        if (data.productTags) (window as any).productTags = data.productTags;
        if (data.cellEdits) (window as any).cellEdits = data.cellEdits;

        // UIを更新
        (window as any).mergeAllData();
        (window as any).updateFileChips();
        (window as any).initUI();

        showToast('🔄 他デバイスからデータ同期');
      });

    autoSyncEnabled = true;
    document.getElementById('auto-sync-btn')!.textContent = '⏸️ 自動同期を無効化';
    showToast('✅ 自動同期を有効化しました');
  }
}

/**
 * ルームから退出
 */
export function leaveRoom(): void {
  if (unsubscribe) {
    unsubscribe();
    unsubscribe = null;
  }

  autoSyncEnabled = false;
  currentRoomCode = null;
  localStorage.removeItem('currentRoomCode');

  document.getElementById('sync-actions')!.style.display = 'none';
  document.getElementById('created-room-code')!.style.display = 'none';
  (document.getElementById('room-code-input') as HTMLInputElement).value = '';

  updateSyncStatus('接続済み', true);
  showToast('ルームから退出しました');
}

/**
 * 同期ステータスを更新
 */
function updateSyncStatus(text: string, connected: boolean): void {
  const statusEl = document.getElementById('sync-status')!;
  const textEl = document.getElementById('sync-status-text')!;

  textEl.textContent = text;

  if (connected) {
    statusEl.classList.add('connected');
  } else {
    statusEl.classList.remove('connected');
  }
}

/**
 * デバイスIDを取得または生成
 */
function getDeviceId(): string {
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
export function showCloudSyncModal(): void {
  // デフォルト設定を入力欄に表示
  const savedConfig = localStorage.getItem('firebaseConfig');
  const config = savedConfig ? JSON.parse(savedConfig) : DEFAULT_FIREBASE_CONFIG;

  (document.getElementById('firebase-api-key') as HTMLInputElement).value = config.apiKey || '';
  (document.getElementById('firebase-project-id') as HTMLInputElement).value = config.projectId || '';
  (document.getElementById('firebase-app-id') as HTMLInputElement).value = config.appId || '';

  // Firebase未初期化の場合は自動接続
  if (!firebaseApp) {
    autoInitFirebase();
  }

  // 保存されたルームコードを復元
  const savedRoomCode = localStorage.getItem('currentRoomCode');
  if (savedRoomCode && firestore) {
    currentRoomCode = savedRoomCode;
    (document.getElementById('room-code-input') as HTMLInputElement).value = savedRoomCode;
  }

  document.getElementById('cloud-sync-modal')!.classList.add('show');
}

/**
 * クラウド同期モーダルを閉じる
 */
export function closeCloudSyncModal(): void {
  document.getElementById('cloud-sync-modal')!.classList.remove('show');
}

/**
 * トースト通知を表示（app.tsの関数を使用）
 */
function showToast(message: string): void {
  (window as any).showToast(message);
}
