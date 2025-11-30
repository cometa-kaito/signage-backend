const CACHE_NAME = 'signage-cache-v1';

// キャッシュ対象のリスト（アプリの骨格）
// ※画像や動画は動的にキャッシュするのでここには書きません
const STATIC_URLS = [];

// インストール時: 準備
self.addEventListener('install', event => {
    console.log('[SW] Installed');
    self.skipWaiting(); // 直ちに有効化
});

// 有効化時: 古いキャッシュの削除
self.addEventListener('activate', event => {
    console.log('[SW] Activated');
    event.waitUntil(
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames.map(cache => {
                    if (cache !== CACHE_NAME) {
                        return caches.delete(cache);
                    }
                })
            );
        })
    );
    return self.clients.claim();
});

// 通信時: ここで「ネット」か「キャッシュ」かを判断
self.addEventListener('fetch', event => {
    const url = new URL(event.request.url);

    // 1. Config APIへのアクセス (常に最新が欲しいが、オフラインならキャッシュ)
    if (url.pathname.includes('/config')) {
        event.respondWith(
            fetch(event.request)
                .then(response => {
                    // 成功したらキャッシュを更新して返す
                    const resClone = response.clone();
                    caches.open(CACHE_NAME).then(cache => {
                        cache.put(event.request, resClone);
                    });
                    return response;
                })
                .catch(() => {
                    // 失敗（オフライン）ならキャッシュを返す
                    return caches.match(event.request);
                })
        );
        return;
    }

    // 2. WebSocketなどはSWで扱えないのでスルー
    if (url.protocol === 'ws:' || url.protocol === 'wss:') {
        return;
    }

    // 3. 画像・動画・HTMLなどの静的コンテンツ (Stale-While-Revalidate戦略)
    // 「とりあえずキャッシュを表示（速い）」しつつ、「裏で最新を取得して次回更新」する戦略
    event.respondWith(
        caches.match(event.request).then(cachedResponse => {
            const fetchPromise = fetch(event.request).then(networkResponse => {
                // 正常なレスポンスならキャッシュ更新
                if (networkResponse && networkResponse.status === 200) {
                    const resClone = networkResponse.clone();
                    caches.open(CACHE_NAME).then(cache => {
                        cache.put(event.request, resClone);
                    });
                }
                return networkResponse;
            }).catch(err => {
                console.log('[SW] Network fetch failed, staying offline.');
            });

            // キャッシュがあればそれを即返す、なければネットワーク通信の結果を待つ
            return cachedResponse || fetchPromise;
        })
    );
});