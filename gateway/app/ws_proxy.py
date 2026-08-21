"""WebSocket gateway that forwards bearer-authenticated traffic to RTO."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import urllib.parse

from fastapi import WebSocket, WebSocketDisconnect

from app.core.config import settings

logger = logging.getLogger(__name__)


def _upstream_ws_url() -> str:
    parsed = urllib.parse.urlsplit(settings.RTO_URL)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    # netloc keeps the port (hostname alone would silently drop :8080)
    return urllib.parse.urlunsplit((scheme, parsed.netloc or "localhost", "/ws", "", ""))


async def proxy_ws(websocket: WebSocket) -> None:
    try:
        import websockets
        import websockets.exceptions
    except Exception:
        logger.error("websockets library not installed")
        await websocket.close(code=1011)
        return

    subprotocols = [
        value.strip()
        for value in websocket.headers.get("sec-websocket-protocol", "").split(",")
        if value.strip()
    ]
    await websocket.accept(subprotocol=subprotocols[0] if subprotocols else None)

    upstream_url = _upstream_ws_url()
    logger.info("Connecting to upstream RTO at %s", upstream_url)

    try:
        upstream = await websockets.connect(
            upstream_url,
            subprotocols=subprotocols,
            ping_interval=30,
            ping_timeout=20,
            close_timeout=10,
        )
    except Exception as exc:
        logger.error("Failed to connect to upstream RTO at %s: %s", upstream_url, exc)
        await websocket.close(code=1011)
        return

    logger.info("Upstream RTO WebSocket connected successfully")

    async def client_to_upstream() -> None:
        try:
            while True:
                message = await websocket.receive()
                if message["type"] == "websocket.disconnect":
                    break
                if message.get("text") is not None:
                    await upstream.send(message["text"])
                elif message.get("bytes") is not None:
                    await upstream.send(message["bytes"])
        except WebSocketDisconnect:
            pass
        except Exception as exc:
            logger.debug("client_to_upstream ended: %s", exc)

    async def upstream_to_client() -> None:
        try:
            while True:
                message = await upstream.recv()
                if isinstance(message, bytes):
                    await websocket.send_bytes(message)
                else:
                    await websocket.send_text(message)
        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as exc:
            logger.debug("upstream_to_client ended: %s", exc)

    try:
        # Run both directions; when either one finishes (client
        # disconnects or upstream closes), cancel the other.
        tasks = [
            asyncio.create_task(client_to_upstream()),
            asyncio.create_task(upstream_to_client()),
        ]
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
    except Exception as exc:
        logger.error("ws proxy error: %s", exc)
    finally:
        with contextlib.suppress(Exception):
            await upstream.close()
        with contextlib.suppress(Exception):
            await websocket.close()