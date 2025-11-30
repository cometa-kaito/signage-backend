from typing import List
from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        """接続している全ラズパイにメッセージを送る"""
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                # 接続切れなどのエラーは無視して次へ
                pass

# シングルトンインスタンスとして公開
manager = ConnectionManager()