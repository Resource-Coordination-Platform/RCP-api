from rcp_clients.base import ServiceClient


class IAMClient(ServiceClient):
    async def jwks(self) -> dict:
        response = await self.get("/.well-known/jwks.json")
        response.raise_for_status()
        return response.json()
