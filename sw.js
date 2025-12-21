// Service Worker for 発注台帳ビューアー PWA
const CACHE_NAME = 'order-viewer-v1';
const ASSETS_TO_CACHE = [
  './',
  './index.html',
  './css/style.css',
  './js/app.js',
  './manifest.json',
  './icons/icon-192.png',
  './icons/icon-512.png'
];

// 外部CDNリソース
const CDN_ASSETS = [
  'https://cdn.sheetjs.com/xlsx-0.20.1/package/dist/xlsx.full.min.js'
];

// インストール時にキャッシュ
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      // ローカルアセットをキャッシュ
      return cache.addAll(ASSETS_TO_CACHE).then(() => {
        // CDNリソースを個別にキャッシュ（失敗しても続行）
        return Promise.allSettled(
          CDN_ASSETS.map(url =>
            fetch(url).then(response => {
              if (response.ok) {
                return cache.put(url, response);
              }
            }).catch(() => console.log('CDN cache skipped:', url))
          )
        );
      });
    }).then(() => {
      // 即座にアクティブ化
      return self.skipWaiting();
    })
  );
});

// アクティベート時に古いキャッシュを削除
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== CACHE_NAME) {
            return caches.delete(cacheName);
          }
        })
      );
    }).then(() => {
      // 全クライアントを即座に制御
      return self.clients.claim();
    })
  );
});

// フェッチ時のキャッシュ戦略: Network First, Cache Fallback
self.addEventListener('fetch', (event) => {
  // POSTリクエストはスキップ
  if (event.request.method !== 'GET') {
    return;
  }

  event.respondWith(
    fetch(event.request)
      .then((response) => {
        // 成功したらキャッシュを更新
        if (response.ok) {
          const responseClone = response.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, responseClone);
          });
        }
        return response;
      })
      .catch(() => {
        // オフライン時はキャッシュから返す
        return caches.match(event.request).then((cachedResponse) => {
          if (cachedResponse) {
            return cachedResponse;
          }
          // HTMLリクエストの場合はindex.htmlを返す
          if (event.request.headers.get('accept').includes('text/html')) {
            return caches.match('./index.html');
          }
        });
      })
  );
});
