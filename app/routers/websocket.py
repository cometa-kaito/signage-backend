from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.websocket import manager

router = APIRouter()

@router.websocket("/ws/{school_id}")
async def websocket_endpoint(websocket: WebSocket, school_id: str):
    await manager.connect(websocket)
    try:
        while True:
            # メッセージ受信待機（接続維持）
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)