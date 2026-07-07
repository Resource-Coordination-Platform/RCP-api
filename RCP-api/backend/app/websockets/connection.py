"""WebSocket connection manager for the Real-Time Notification service.

Connections are grouped per tenant so broadcasts never leak across
community hubs (multi-tenant isolation applies to live updates too).
"""

import uuid
from collections import defaultdict

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        # tenant_id -> {user_id -> [sockets]} (a user may have several tabs/devices)
        self._connections: dict[uuid.UUID, dict[uuid.UUID, list[WebSocket]]] = (
            defaultdict(lambda: defaultdict(list))
        )

    async def connect(
        self, websocket: WebSocket, tenant_id: uuid.UUID, user_id: uuid.UUID
    ) -> None:
        await websocket.accept()
        self._connections[tenant_id][user_id].append(websocket)

    def disconnect(
        self, websocket: WebSocket, tenant_id: uuid.UUID, user_id: uuid.UUID
    ) -> None:
        sockets = self._connections[tenant_id][user_id]
        if websocket in sockets:
            sockets.remove(websocket)

    async def send_to_user(
        self, tenant_id: uuid.UUID, user_id: uuid.UUID, message: dict
    ) -> None:
        for socket in self._connections[tenant_id][user_id]:
            await socket.send_json(message)

    async def broadcast_to_tenant(self, tenant_id: uuid.UUID, message: dict) -> None:
        for sockets in self._connections[tenant_id].values():
            for socket in sockets:
                await socket.send_json(message)


manager = ConnectionManager()
