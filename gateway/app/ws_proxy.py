"""WebSocket gateway that forwards bearer-authenticated traffic to RTO."""

from __future__ import annotations

import asyncio
import contextlib
import urllib.parse

from fastapi import WebSocket, WebSocketDisconnect

from app.core.config import settings


def _upstream_ws_url() -> str:
    parsed = urllib.parse.urlsplit(settings.RTO_URL)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    # netloc keeps the port (hostname alone would silently drop :8080)
    return urllib.parse.urlunsplit((scheme, parsed.netloc or "localhost", "/ws", "", ""))


async def proxy_ws(websocket: WebSocket) -> None:
    try:
        import websockets
    except Exception:
        await websocket.close(code=1011)
        return

    subprotocols = [value.strip() for value in websocket.headers.get("sec-websocket-protocol", "").split(",") if value.strip()]
    await websocket.accept(subprotocol=subprotocols[0] if subprotocols else None)

    async with websockets.connect(_upstream_ws_url(), subprotocols=subprotocols) as upstream:
        async def client_to_upstream() -> None:
            while True:
                message = await websocket.receive()
                if message["type"] == "websocket.disconnect":
                    break
                if message.get("text") is not None:
                    await upstream.send(message["text"])
                elif message.get("bytes") is not None:
                    await upstream.send(message["bytes"])

        async def upstream_to_client() -> None:
            while True:
                message = await upstream.recv()
                if isinstance(message, bytes):
                    await websocket.send_bytes(message)
                else:
                    await websocket.send_text(message)

        with contextlib.suppress(WebSocketDisconnect):
            await asyncio.gather(client_to_upstream(), upstream_to_client())