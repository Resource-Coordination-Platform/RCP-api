"""Base HTTP client for service-to-service calls.

Callers forward the end user's bearer token (authentication forwarding);
services never mint credentials on each other's behalf.
"""

import httpx


class ServiceClient:
    def __init__(self, base_url: str, timeout: float = 10.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    @property
    def base_url(self) -> str:
        return self._base_url

    def _headers(self, bearer_token: str | None = None) -> dict[str, str]:
        headers: dict[str, str] = {}
        if bearer_token:
            headers["Authorization"] = f"Bearer {bearer_token}"
        return headers

    async def get(self, path: str, bearer_token: str | None = None, **params) -> httpx.Response:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            return await client.get(
                f"{self._base_url}{path}",
                headers=self._headers(bearer_token),
                params=params or None,
            )

    async def health(self) -> dict:
        try:
            response = await self.get("/readiness")
            if response.status_code == 404:
                response = await self.get("/health")
            body = response.json() if response.status_code == 200 else {}
            return {"status": body.get("status", "degraded"), "http_status": response.status_code}
        except httpx.HTTPError as exc:
            return {"status": "unreachable", "error": str(exc)}
