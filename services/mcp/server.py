import os
import asyncio
import hashlib
import json
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from urllib.parse import urlparse

import httpx
import redis.asyncio as redis
from pydantic import BaseModel, Field
from fastmcp import FastMCP
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
SEARXNG_URL = os.environ.get("SEARXNG_URL", "http://searxng:8080").rstrip("/")
EXTRACTOR_URL = os.environ.get("EXTRACTOR_URL", "http://extractor:8055").rstrip("/")
REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379")
MAX_CONCURRENT = int(os.environ.get("MAX_CONCURRENT_REQUESTS", "5"))
RATE_LIMIT_PER_DOMAIN = float(os.environ.get("RATE_LIMIT_PER_DOMAIN", "2"))
CACHE_TTL = int(os.environ.get("CACHE_TTL", "3600"))

# Models
class SearchResult(BaseModel):
    title: str
    url: str
    snippet: Optional[str] = None
    engine: Optional[str] = None
    score: Optional[float] = None
    cached: bool = False

class SearchResponse(BaseModel):
    query: str
    timestamp: str
    count: int
    results: List[SearchResult] = Field(default_factory=list)
    search_id: str

class PageContent(BaseModel):
    url: str
    title: Optional[str] = None
    text: str
    extracted_at: str
    word_count: int
    cached: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)

class SessionInfo(BaseModel):
    session_id: str
    created_at: str
    searches_performed: int
    pages_extracted: int

# Rate limiter
class RateLimiter:
    def __init__(self, rate: float):
        self.rate = rate
        self.domains = {}
        
    async def acquire(self, url: str):
        domain = urlparse(url).netloc
        now = asyncio.get_event_loop().time()
        
        if domain in self.domains:
            elapsed = now - self.domains[domain]
            if elapsed < 1.0 / self.rate:
                await asyncio.sleep(1.0 / self.rate - elapsed)
        
        self.domains[domain] = asyncio.get_event_loop().time()

# Initialize components
rate_limiter = RateLimiter(RATE_LIMIT_PER_DOMAIN)
redis_client = None

async def get_redis():
    global redis_client
    if not redis_client:
        redis_client = await redis.from_url(REDIS_URL, decode_responses=True)
    return redis_client

def get_cache_key(prefix: str, identifier: str) -> str:
    """Generate cache key with prefix and hashed identifier"""
    hash_id = hashlib.md5(identifier.encode()).hexdigest()[:12]
    return f"mcp:{prefix}:{hash_id}"

# MCP Server
mcp = FastMCP("WebSearchMCP")

@mcp.tool()
async def web_search(
    query: str,
    max_results: int = 10,
    categories: str = "general",
    time_range: Optional[str] = None,  # 'day'|'week'|'month'|'year'
    language: str = "en",
    safe_search: int = 1,  # 0=off, 1=moderate, 2=strict
) -> SearchResponse:
    """
    Search the web using SearXNG metasearch engine.
    
    Args:
        query: Search query string
        max_results: Maximum number of results (1-50)
        categories: Search categories (general, images, news, etc.)
        time_range: Filter by time (day, week, month, year)
        language: Language code (en, de, fr, etc.)
        safe_search: Safe search level (0=off, 1=moderate, 2=strict)
    """
    # Check cache first
    cache = await get_redis()
    cache_key = get_cache_key("search", f"{query}:{categories}:{time_range}:{language}")
    
    cached_result = await cache.get(cache_key)
    if cached_result:
        data = json.loads(cached_result)
        for result in data["results"]:
            result["cached"] = True
        return SearchResponse(**data)
    
    # Perform search
    params = {
        "q": query,
        "format": "json",
        "categories": categories,
        "pageno": 1,
        "language": language,
        "safesearch": safe_search,
    }
    if time_range:
        params["time_range"] = time_range
    
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(f"{SEARXNG_URL}/search", params=params)
            response.raise_for_status()
            data = response.json()
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise
    
    # Process results
    results = []
    for hit in (data.get("results") or [])[: min(max_results, 50)]:
        results.append(
            SearchResult(
                title=hit.get("title", ""),
                url=hit.get("url", ""),
                snippet=hit.get("content"),
                engine=hit.get("engine"),
                score=hit.get("score"),
                cached=False,
            )
        )
    
    search_response = SearchResponse(
        query=query,
        timestamp=datetime.utcnow().isoformat(),
        count=len(results),
        results=results,
        search_id=hashlib.md5(f"{query}{datetime.utcnow()}".encode()).hexdigest()[:12],
    )
    
    # Cache the results
    await cache.setex(
        cache_key,
        CACHE_TTL,
        json.dumps(search_response.model_dump()),
    )
    
    # Track in session
    await cache.hincrby(f"mcp:session:stats", "searches_performed", 1)
    
    return search_response

@mcp.tool()
async def fetch_content(
    url: str,
    use_javascript: bool = False,
    extract_images: bool = False,
    timeout: int = 30,
) -> PageContent:
    """
    Extract readable content from a URL.
    
    Args:
        url: URL to extract content from
        use_javascript: Use Playwright for JS rendering (slower)
        extract_images: Extract image URLs from the page
        timeout: Request timeout in seconds
    """
    # Rate limit
    await rate_limiter.acquire(url)
    
    # Check cache
    cache = await get_redis()
    cache_key = get_cache_key("content", url)
    
    cached_content = await cache.get(cache_key)
    if cached_content:
        data = json.loads(cached_content)
        data["cached"] = True
        return PageContent(**data)
    
    # Extract content
    endpoint = "/extract/js" if use_javascript else "/extract"
    payload = {
        "url": url,
        "extract_images": extract_images,
        "timeout": timeout,
    }
    
    try:
        async with httpx.AsyncClient(timeout=timeout + 5) as client:
            response = await client.post(
                f"{EXTRACTOR_URL}{endpoint}",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
    except Exception as e:
        logger.error(f"Content extraction failed for {url}: {e}")
        raise
    
    # Process response
    text = data.get("text", "")
    page_content = PageContent(
        url=url,
        title=data.get("title"),
        text=text,
        extracted_at=datetime.utcnow().isoformat(),
        word_count=len(text.split()),
        cached=False,
        metadata=data.get("metadata", {}),
    )
    
    # Cache the content
    await cache.setex(
        cache_key,
        CACHE_TTL,
        json.dumps(page_content.model_dump()),
    )
    
    # Track in session
    await cache.hincrby(f"mcp:session:stats", "pages_extracted", 1)
    
    return page_content

@mcp.tool()
async def batch_fetch(
    urls: List[str],
    max_concurrent: Optional[int] = None,
    use_javascript: bool = False,
) -> List[PageContent]:
    """
    Fetch content from multiple URLs concurrently.
    
    Args:
        urls: List of URLs to fetch
        max_concurrent: Maximum concurrent requests (default: 5)
        use_javascript: Use JS rendering for all URLs
    """
    if max_concurrent is None:
        max_concurrent = MAX_CONCURRENT
    
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def fetch_with_semaphore(url: str) -> Optional[PageContent]:
        async with semaphore:
            try:
                return await fetch_content(url, use_javascript=use_javascript)
            except Exception as e:
                logger.error(f"Failed to fetch {url}: {e}")
                return None
    
    tasks = [fetch_with_semaphore(url) for url in urls]
    results = await asyncio.gather(*tasks)
    
    return [r for r in results if r is not None]

@mcp.tool()
async def get_session_info() -> SessionInfo:
    """Get current session statistics."""
    cache = await get_redis()
    stats = await cache.hgetall(f"mcp:session:stats")
    
    return SessionInfo(
        session_id=hashlib.md5(REDIS_URL.encode()).hexdigest()[:12],
        created_at=datetime.utcnow().isoformat(),
        searches_performed=int(stats.get("searches_performed", 0)),
        pages_extracted=int(stats.get("pages_extracted", 0)),
    )

@mcp.tool()
async def clear_cache(pattern: Optional[str] = None) -> Dict[str, Any]:
    """
    Clear cached data.
    
    Args:
        pattern: Optional pattern to match keys (e.g., "search:*" or "content:*")
    """
    cache = await get_redis()
    
    if pattern:
        keys = await cache.keys(f"mcp:{pattern}")
    else:
        keys = await cache.keys("mcp:*")
    
    if keys:
        deleted = await cache.delete(*keys)
        return {"status": "success", "deleted_keys": deleted}
    
    return {"status": "success", "deleted_keys": 0}

# Health check endpoint - added as a simple tool for now
@mcp.tool()
async def health_check() -> dict:
    """Check the health status of all services"""
    try:
        # Check Redis
        cache = await get_redis()
        await cache.ping()
        
        # Check SearXNG
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{SEARXNG_URL}/healthz")
            response.raise_for_status()
        
        return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

if __name__ == "__main__":
    mcp.run()