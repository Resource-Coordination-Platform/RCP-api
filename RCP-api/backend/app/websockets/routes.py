"""Real-Time Notification & WebSocket service endpoint.

Clients connect with their JWT (?token=...) and receive live task
assignments and resource-availability updates for their tenant.
"""

import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from jose import JWTError

from app.core.security import decode_access_token
from app.websockets.connection import manager

router = APIRouter()


@router.websocket("/ws/notifications")
async def notifications_ws(websocket: WebSocket, token: str):
    try:
        payload = decode_access_token(token)
        user_id = uuid.UUID(payload["sub"])
        tenant_id = uuid.UUID(payload["tenant_id"])
    except (JWTError, KeyError, ValueError):
        await websocket.close(code=4401)
        return

    await manager.connect(websocket, tenant_id, user_id)
    try:
        while True:
            # keep the connection alive; client messages are ignored for now
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, tenant_id, user_id)
