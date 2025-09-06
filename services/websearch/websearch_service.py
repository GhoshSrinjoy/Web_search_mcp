import httpx
import os
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class WebSearchService:
    def __init__(self):
        self.base_url = os.getenv("WEBSEARCH_URL", "http://localhost:8055")
    
    async def web_search(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        """Search the web using SearXNG"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/search",
                    json={"query": query, "max_results": max_results},
                    timeout=30
                )
                return response.json()
        except Exception as e:
            logger.error(f"Web search failed: {e}")
            return {"error": str(e), "results": []}
    
    async def extract_content(self, url: str) -> Dict[str, Any]:
        """Extract content from URL"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/extract",
                    json={"url": url},
                    timeout=30
                )
                return response.json()
        except Exception as e:
            logger.error(f"Content extraction failed: {e}")
            return {"error": str(e), "text": "", "title": ""}
    
    async def fetch_content(self, url: str) -> Dict[str, Any]:
        """Alias for extract_content for backward compatibility"""
        return await self.extract_content(url)