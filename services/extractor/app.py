import os
import asyncio
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
import trafilatura
from trafilatura.settings import use_config
import httpx
import logging
from bs4 import BeautifulSoup
import redis.asyncio as redis
import json
import hashlib
from urllib.parse import urljoin, urlparse

# Configuration
PORT = int(os.environ.get("PORT", "8055"))
REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379")
MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH", "10485760"))
REQUEST_TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT", "30"))

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Enhanced Trafilatura config
config = use_config()
config.set("DEFAULT", "EXTRACTION_TIMEOUT", str(REQUEST_TIMEOUT))
config.set("DEFAULT", "MIN_EXTRACTED_SIZE", "200")
config.set("DEFAULT", "MIN_OUTPUT_SIZE", "100")
config.set("DEFAULT", "MIN_OUTPUT_COMM_SIZE", "10")
config.set("DEFAULT", "EXTENSIVE_DATE_SEARCH", "on")

# Precision-focused config for first pass
precision_config = use_config()
precision_config.set("DEFAULT", "EXTRACTION_TIMEOUT", str(REQUEST_TIMEOUT))
precision_config.set("DEFAULT", "MIN_EXTRACTED_SIZE", "300")
precision_config.set("DEFAULT", "MIN_OUTPUT_SIZE", "200")
precision_config.set("DEFAULT", "EXTENSIVE_DATE_SEARCH", "off")

app = FastAPI(title="Content Extractor Service", version="1.0.0")

# Models
class ExtractRequest(BaseModel):
    url: str
    extract_images: bool = False
    timeout: int = 30
    include_links: bool = False
    include_formatting: bool = False

class ExtractResponse(BaseModel):
    url: str
    title: Optional[str] = None
    text: str
    images: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

# Cache client
redis_client = None

def extract_with_fallback(html: str, url: str, request_params: ExtractRequest) -> tuple[str, dict]:
    """Enhanced extraction with precision-first approach and fallback."""
    
    # Try precision-focused extraction first
    try:
        logger.debug("Attempting precision-focused extraction")
        result = trafilatura.extract(
            html,
            config=precision_config,
            favor_precision=True,
            include_tables=True,
            include_comments=False,
            include_links=request_params.include_links,
            include_formatting=request_params.include_formatting,
            output_format='json',
            target_language='en',
            with_metadata=False,
        )
        
        if result:
            import json
            try:
                parsed = json.loads(result)
                text = parsed.get('text', '')
                metadata = {
                    'title': parsed.get('title'),
                    'date': parsed.get('date'),
                    'author': parsed.get('author'),
                    'sitename': parsed.get('sitename'),
                    'extraction_method': 'precision'
                }
                if text and len(text.strip()) >= 200:
                    logger.info(f"Precision extraction successful: {len(text)} chars")
                    return text, {k: v for k, v in metadata.items() if v}
            except json.JSONDecodeError:
                logger.warning("Failed to parse JSON from precision extraction")
    
    except Exception as e:
        logger.warning(f"Precision extraction failed: {e}")
    
    # Fallback to recall-focused extraction
    try:
        logger.debug("Attempting recall-focused extraction")
        result = trafilatura.extract(
            html,
            config=config,
            favor_recall=True,
            include_tables=True,
            include_comments=True,
            include_links=request_params.include_links,
            include_formatting=request_params.include_formatting,
            target_language='en',
            with_metadata=False,
        )
        
        if result and len(result.strip()) >= 100:
            logger.info(f"Recall extraction successful: {len(result)} chars")
            return result, {'extraction_method': 'recall'}
            
    except Exception as e:
        logger.warning(f"Recall extraction failed: {e}")
    
    # Final fallback to basic extraction
    try:
        logger.debug("Using basic extraction fallback")
        result = trafilatura.extract(
            html,
            include_links=request_params.include_links,
            include_formatting=request_params.include_formatting,
        )
        
        if result:
            logger.info(f"Basic extraction successful: {len(result)} chars")
            return result, {'extraction_method': 'basic'}
            
    except Exception as e:
        logger.warning(f"Basic extraction failed: {e}")
    
    return None, {}

async def get_redis():
    global redis_client
    if not redis_client:
        redis_client = await redis.from_url(REDIS_URL, decode_responses=True)
    return redis_client

def clean_text(text: str) -> str:
    """Clean and normalize extracted text."""
    if not text:
        return ""
    
    # Basic text cleaning
    lines = (line.strip() for line in text.splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    cleaned = ' '.join(chunk for chunk in chunks if chunk)
    
    return cleaned

def extract_images_from_html(html: str, base_url: str) -> List[str]:
    """Extract and resolve image URLs from HTML."""
    images = []
    
    try:
        soup = BeautifulSoup(html, 'html.parser')
        
        # Find all img tags
        for img in soup.find_all('img'):
            src = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
            if src:
                # Resolve relative URLs
                if not src.startswith(('http://', 'https://', 'data:')):
                    src = urljoin(base_url, src)
                
                # Skip data URLs and very small images
                if not src.startswith('data:') and 'spacer' not in src.lower():
                    images.append(src)
        
        # Also check for CSS background images
        for element in soup.find_all(style=True):
            style = element.get('style', '')
            if 'background-image:' in style:
                # Simple regex to extract URL from background-image
                import re
                matches = re.findall(r'background-image:\s*url\(["\']?([^"\']+)["\']?\)', style)
                for match in matches:
                    if not match.startswith(('http://', 'https://', 'data:')):
                        match = urljoin(base_url, match)
                    if not match.startswith('data:'):
                        images.append(match)
    
    except Exception as e:
        logger.warning(f"Failed to extract images: {e}")
    
    # Remove duplicates while preserving order
    seen = set()
    unique_images = []
    for img in images:
        if img not in seen:
            seen.add(img)
            unique_images.append(img)
    
    return unique_images[:50]  # Limit to 50 images

@app.post("/extract", response_model=ExtractResponse)
async def extract_content(request: ExtractRequest):
    """Extract readable content using Trafilatura."""
    try:
        logger.info(f"Extracting content from: {request.url}")
        
        # Validate URL
        parsed_url = urlparse(request.url)
        if not parsed_url.scheme or not parsed_url.netloc:
            raise HTTPException(status_code=400, detail="Invalid URL format")
        
        # Download content with custom headers
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        try:
            # Trafilatura fetch_url doesn't accept timeout parameter
            downloaded = trafilatura.fetch_url(
                request.url,
                config=config
            )
        except Exception as fetch_error:
            logger.warning(f"Trafilatura fetch failed, trying httpx: {fetch_error}")
            # Fallback to httpx if trafilatura fails
            try:
                async with httpx.AsyncClient(timeout=request.timeout, headers=headers) as client:
                    response = await client.get(request.url)
                    response.raise_for_status()
                    downloaded = response.text
            except Exception as httpx_error:
                error_msg = str(httpx_error) if httpx_error else "Unknown network error"
                logger.error(f"Both fetch methods failed: {error_msg}")
                raise HTTPException(status_code=400, detail=f"Failed to fetch URL: {error_msg}")
        
        if not downloaded:
            raise HTTPException(status_code=400, detail="No content retrieved from URL")
        
        # Check content length
        if len(downloaded) > MAX_CONTENT_LENGTH:
            logger.warning(f"Content too large ({len(downloaded)} bytes), truncating")
            downloaded = downloaded[:MAX_CONTENT_LENGTH]
        
        # Extract metadata first
        metadata_dict = {}
        title = None
        
        try:
            metadata = trafilatura.extract_metadata(downloaded)
            if metadata:
                title = metadata.title
                metadata_dict = {
                    "author": metadata.author,
                    "date": metadata.date,
                    "description": metadata.description,
                    "sitename": metadata.sitename,
                    "tags": metadata.tags,
                    "language": metadata.language,
                }
                # Remove None values
                metadata_dict = {k: v for k, v in metadata_dict.items() if v is not None}
        except Exception as meta_error:
            logger.warning(f"Metadata extraction failed: {meta_error}")
        
        # Extract main text content using enhanced method
        result_text, enhanced_metadata = extract_with_fallback(downloaded, request.url, request)
        
        # Merge enhanced metadata with existing metadata
        if enhanced_metadata:
            metadata_dict.update(enhanced_metadata)
        
        # Fallback to BeautifulSoup if enhanced extraction fails
        if not result_text or len(result_text.strip()) < 50:
            logger.info("Using BeautifulSoup fallback extraction")
            try:
                soup = BeautifulSoup(downloaded, 'html.parser')
                
                # Remove script and style elements
                for script in soup(["script", "style", "nav", "footer", "header", "aside"]):
                    script.decompose()
                
                # Try to find main content areas
                main_content = None
                for selector in ['main', 'article', '.content', '.post', '.entry']:
                    main_content = soup.select_one(selector)
                    if main_content:
                        break
                
                if main_content:
                    text = main_content.get_text()
                else:
                    text = soup.get_text()
                
                result_text = clean_text(text)
                
            except Exception as soup_error:
                logger.error(f"BeautifulSoup fallback failed: {soup_error}")
                raise HTTPException(status_code=422, detail="Failed to extract readable content")
        
        # Final check
        if not result_text or len(result_text.strip()) < 10:
            raise HTTPException(status_code=422, detail="No meaningful content extracted")
        
        # Clean the extracted text
        result_text = clean_text(result_text)
        
        # Extract title if not found in metadata
        if not title:
            try:
                soup = BeautifulSoup(downloaded, 'html.parser')
                title_tag = soup.find('title')
                if title_tag:
                    title = title_tag.get_text().strip()
                
                # Try og:title as fallback
                if not title:
                    og_title = soup.find('meta', property='og:title')
                    if og_title:
                        title = og_title.get('content', '').strip()
                
            except Exception:
                pass
        
        # Extract images if requested
        images = []
        if request.extract_images:
            try:
                images = extract_images_from_html(downloaded, request.url)
                logger.info(f"Extracted {len(images)} images")
            except Exception as img_error:
                logger.warning(f"Image extraction failed: {img_error}")
        
        response = ExtractResponse(
            url=request.url,
            title=title,
            text=result_text,
            images=images,
            metadata=metadata_dict,
        )
        
        logger.info(f"Successfully extracted {len(result_text)} characters from {request.url}")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Extraction failed for {request.url}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal extraction error: {str(e)}")

@app.post("/extract/js", response_model=ExtractResponse)
async def extract_with_javascript(request: ExtractRequest):
    """Extract content from JavaScript-rendered pages using Playwright."""
    # This would connect to the Playwright service if Phase 2 is implemented
    raise HTTPException(
        status_code=501,
        detail="JavaScript rendering not implemented yet. Use /extract endpoint for static content."
    )

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        # Test Redis connection
        cache = await get_redis()
        await cache.ping()
        
        # Test basic extraction capability
        test_html = "<html><body><h1>Test</h1><p>This is a test.</p></body></html>"
        test_result = trafilatura.extract(test_html)
        
        if not test_result:
            return {"status": "unhealthy", "error": "Trafilatura not working"}, 503
        
        return {
            "status": "healthy",
            "timestamp": "2024-01-01T00:00:00Z",
            "trafilatura_version": trafilatura.__version__
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}, 503

class SearchRequest(BaseModel):
    query: str = Field(..., description="Search query")
    max_results: Optional[int] = Field(10, description="Maximum number of results")
    language: Optional[str] = Field("en", description="Search language")
    categories: Optional[str] = Field("general", description="Search categories")

@app.post("/search")
async def search_web(request: SearchRequest):
    """Search the web via SearXNG and return results with corrected count."""
    try:
        searxng_url = "http://searxng:8080"
        params = {
            "q": request.query,
            "format": "json",
            "language": request.language,
            "categories": request.categories
        }
        
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(f"{searxng_url}/search", params=params)
            response.raise_for_status()
            data = response.json()
            
            # Fix the number_of_results to show actual count
            if "results" in data:
                data["number_of_results"] = len(data["results"])
                
                # Limit results if requested
                if request.max_results and len(data["results"]) > request.max_results:
                    data["results"] = data["results"][:request.max_results]
                    data["number_of_results"] = len(data["results"])
            
            return data
            
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@app.get("/")
async def root():
    """Root endpoint with service info."""
    return {
        "service": "Content Extractor",
        "version": "1.0.0",
        "endpoints": {
            "/search": "POST - Search the web via SearXNG",
            "/extract": "POST - Extract content from static pages",
            "/extract/js": "POST - Extract content with JavaScript rendering",
            "/health": "GET - Health check"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)