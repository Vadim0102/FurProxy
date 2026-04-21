import httpx
from loguru import logger

class ProxyFetcher:
    async def fetch_one(self, url: str) -> str:
        """Загружает одну подписку."""
        async with httpx.AsyncClient(http2=True, verify=False) as client:
            try:
                resp = await client.get(url, timeout=15, follow_redirects=True)
                if resp.status_code == 200:
                    return resp.text
            except Exception as e:
                logger.warning(f"Error fetching {url}: {e}")
        return ""
