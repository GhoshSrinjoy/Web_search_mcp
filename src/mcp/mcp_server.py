"""
MCP Server for WebSearch, Content Extraction, and RAG Tools
This server exposes tools that LLMs can call autonomously via MCP
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional
import httpx
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))
from services.vectorstore import ContentVectorizer, ContentResult, RAGResult
import time
import hashlib
import redis.asyncio as redis

# MCP imports
from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("websearch-mcp-server")

# Initialize the MCP server
server = Server("websearch-mcp-server")

# Initialize services  
from services.websearch import WebSearchService

# Initialize services
websearch_service = WebSearchService()
vectorizer = ContentVectorizer(chroma_path="./data/chroma_db")

# Redis cache for search coordination
redis_client = None

async def get_redis():
    global redis_client
    if not redis_client:
        redis_url = os.getenv("REDIS_URL", "redis://redis:6379")
        redis_client = await redis.from_url(redis_url, decode_responses=True)
    return redis_client

async def cache_search_result(query: str, result: Dict, ttl: int = 3600):
    """Cache search results with TTL"""
    try:
        cache = await get_redis()
        cache_key = f"search:{hashlib.md5(query.encode()).hexdigest()}"
        await cache.setex(cache_key, ttl, json.dumps(result))
        logger.debug(f"Cached search result for: {query}")
    except Exception as e:
        logger.warning(f"Failed to cache search result: {e}")

async def get_cached_search(query: str) -> Dict:
    """Get cached search results"""
    try:
        cache = await get_redis()
        cache_key = f"search:{hashlib.md5(query.encode()).hexdigest()}"
        cached = await cache.get(cache_key)
        if cached:
            logger.debug(f"Found cached search result for: {query}")
            return json.loads(cached)
        return None
    except Exception as e:
        logger.warning(f"Failed to get cached search: {e}")
        return None

@server.list_tools()
async def list_tools() -> List[types.Tool]:
    """List available tools"""
    return [
        types.Tool(
            name="web_search",
            description="Search the internet for current information about any topic",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query to find information on the web"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of search results to return (default: 5)",
                        "default": 5
                    }
                },
                "required": ["query"]
            }
        ),
        types.Tool(
            name="extract_content",
            description="Extract full text content from a webpage URL",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL to extract content from"
                    }
                },
                "required": ["url"]
            }
        ),
        types.Tool(
            name="rag_search",
            description="Search through previously stored knowledge base for relevant information",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query to find information in the knowledge base"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default: 10)",
                        "default": 10
                    }
                },
                "required": ["query"]
            }
        ),
        types.Tool(
            name="store_content",
            description="Store extracted content in the knowledge base for future retrieval",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "Source URL of the content"
                    },
                    "title": {
                        "type": "string",
                        "description": "Title of the content"
                    },
                    "text": {
                        "type": "string",
                        "description": "Full text content to store"
                    }
                },
                "required": ["url", "title", "text"]
            }
        ),
        types.Tool(
            name="knowledge_stats",
            description="Get statistics about the current knowledge base",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        types.Tool(
            name="research_query",
            description="Perform comprehensive research with parallel searches, intelligent content processing, and RAG integration. Use this for complex queries requiring multiple sources.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Research query or topic to investigate comprehensively"
                    },
                    "max_sources": {
                        "type": "integer",
                        "description": "Maximum number of sources to search and extract (default: 3)",
                        "default": 3
                    },
                    "store_results": {
                        "type": "boolean",
                        "description": "Whether to store extracted content in knowledge base (default: true)",
                        "default": True
                    }
                },
                "required": ["query"]
            }
        ),
        types.Tool(
            name="smart_answer",
            description="Get an intelligent answer by first checking knowledge base, then supplementing with web search if needed. Optimized for direct responses.",
            inputSchema={
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "Question to answer using stored knowledge and/or web search"
                    },
                    "prefer_stored": {
                        "type": "boolean",
                        "description": "Prefer using stored knowledge over web search (default: true)",
                        "default": True
                    }
                },
                "required": ["question"]
            }
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[types.TextContent]:
    """Handle tool calls"""
    try:
        if name == "web_search":
            query = arguments.get("query")
            max_results = arguments.get("max_results", 5)
            
            if not query:
                return [types.TextContent(
                    type="text",
                    text="Error: Query parameter is required for web search"
                )]
            
            logger.info(f"Performing web search: {query}")
            
            # Check cache first
            cached_results = await get_cached_search(f"{query}:{max_results}")
            if cached_results:
                logger.info(f"Using cached search results for: {query}")
                results = cached_results
            else:
                results = await websearch_service.web_search(query, max_results)
                if "error" not in results:
                    # Cache successful results
                    await cache_search_result(f"{query}:{max_results}", results, 1800)  # 30 min TTL
            
            if "error" in results:
                return [types.TextContent(
                    type="text",
                    text=f"Web search failed: {results['error']}"
                )]
            
            # Format results for LLM
            formatted_results = []
            for i, result in enumerate(results.get("results", []), 1):
                formatted_results.append(
                    f"{i}. **{result.get('title', 'No Title')}**\n"
                    f"   URL: {result.get('url', '')}\n"
                    f"   Description: {result.get('content', 'No description')[:200]}...\n"
                )
            
            response = f"Found {results.get('number_of_results', 0)} search results:\n\n" + "\n".join(formatted_results)
            return [types.TextContent(type="text", text=response)]
            
        elif name == "extract_content":
            url = arguments.get("url")
            
            if not url:
                return [types.TextContent(
                    type="text",
                    text="Error: URL parameter is required for content extraction"
                )]
            
            logger.info(f"Extracting content from: {url}")
            content = await websearch_service.extract_content(url)
            
            if "error" in content:
                return [types.TextContent(
                    type="text",
                    text=f"Content extraction failed: {content['error']}"
                )]
            
            response = f"**Title:** {content.get('title', 'No Title')}\n"
            response += f"**URL:** {url}\n"
            response += f"**Content Length:** {len(content.get('text', ''))} characters\n\n"
            response += f"**Content:**\n{content.get('text', 'No content extracted')}"
            
            return [types.TextContent(type="text", text=response)]
            
        elif name == "rag_search":
            query = arguments.get("query")
            max_results = arguments.get("max_results", 10)
            
            if not query:
                return [types.TextContent(
                    type="text",
                    text="Error: Query parameter is required for RAG search"
                )]
            
            logger.info(f"Performing RAG search: {query}")
            rag_result = await vectorizer.rag_search(query, max_results)
            
            if not rag_result.retrieved_chunks:
                return [types.TextContent(
                    type="text",
                    text=f"No relevant information found in knowledge base for query: '{query}'"
                )]
            
            # Format RAG results
            formatted_results = []
            for i, (chunk, source, score) in enumerate(zip(
                rag_result.retrieved_chunks,
                rag_result.sources,
                rag_result.similarity_scores
            ), 1):
                formatted_results.append(
                    f"{i}. **{source.get('title', 'No Title')}** (Similarity: {score:.3f})\n"
                    f"   URL: {source.get('url', '')}\n"
                    f"   Content: {chunk[:300]}...\n"
                )
            
            response = f"Found {len(rag_result.retrieved_chunks)} relevant chunks:\n\n" + "\n".join(formatted_results)
            return [types.TextContent(type="text", text=response)]
            
        elif name == "store_content":
            url = arguments.get("url")
            title = arguments.get("title")
            text = arguments.get("text")
            
            if not all([url, title, text]):
                return [types.TextContent(
                    type="text",
                    text="Error: URL, title, and text parameters are required for storing content"
                )]
            
            logger.info(f"Storing content: {title}")
            
            # Create content result and store
            content_result = ContentResult(
                url=url,
                title=title,
                text=text,
                timestamp=time.time()
            )
            
            result = await vectorizer.process_content(content_result)
            
            if result.get('status') == 'success':
                chunks_count = result.get('chunks', 0)
                response = f"Successfully stored content '{title}' in knowledge base.\n"
                response += f"Generated {chunks_count} chunks from {len(text)} characters."
            else:
                response = f"Failed to store content: {result.get('error', 'Unknown error')}"
            
            return [types.TextContent(type="text", text=response)]
            
        elif name == "knowledge_stats":
            logger.info("Getting knowledge base statistics")
            stats = vectorizer.get_knowledge_stats()
            
            response = "**Knowledge Base Statistics:**\n"
            response += f"- Total chunks: {stats.get('total_chunks', 0)}\n"
            response += f"- Unique sources: {stats.get('unique_sources', 0)}\n"
            response += f"- Unique documents: {stats.get('unique_titles', 0)}\n"
            response += f"- Embedding model: {stats.get('embedding_model', 'N/A')}\n"
            response += f"- Collection: {stats.get('collection_name', 'N/A')}\n"
            
            if stats.get('error'):
                response += f"- Error: {stats['error']}\n"
            
            return [types.TextContent(type="text", text=response)]
            
        elif name == "research_query":
            query = arguments.get("query")
            max_sources = arguments.get("max_sources", 3)
            store_results = arguments.get("store_results", True)
            
            if not query:
                return [types.TextContent(
                    type="text",
                    text="Error: Query parameter is required for research"
                )]
            
            logger.info(f"Performing comprehensive research: {query}")
            
            try:
                # Step 1: Parallel web search
                search_results = await websearch_service.web_search(query, max_sources)
                
                if "error" in search_results:
                    return [types.TextContent(
                        type="text",
                        text=f"Research failed - search error: {search_results['error']}"
                    )]
                
                urls = []
                search_summaries = []
                for result in search_results.get("results", [])[:max_sources]:
                    urls.append(result.get('url'))
                    search_summaries.append(f"• {result.get('title', 'No Title')}: {result.get('content', '')[:150]}...")
                
                if not urls:
                    return [types.TextContent(
                        type="text",
                        text=f"No search results found for: {query}"
                    )]
                
                # Step 2: Parallel content extraction
                content_tasks = []
                import asyncio
                
                async def extract_and_process(url):
                    try:
                        content = await websearch_service.extract_content(url)
                        if "error" not in content:
                            content_length = len(content.get('text', ''))
                            
                            # Smart decision: store if substantial content
                            if store_results and content_length > 500:
                                content_result = ContentResult(
                                    url=url,
                                    title=content.get('title', 'Untitled'),
                                    text=content.get('text', ''),
                                    timestamp=time.time()
                                )
                                await vectorizer.process_content(content_result)
                                return content, True  # Stored
                            else:
                                return content, False  # Not stored (too small)
                        return None, False
                    except Exception as e:
                        logger.error(f"Failed to process {url}: {e}")
                        return None, False
                
                # Execute extractions in parallel
                extraction_results = await asyncio.gather(*[extract_and_process(url) for url in urls])
                
                # Step 3: Compile results
                extracted_contents = []
                stored_count = 0
                total_chars = 0
                
                for i, (content, was_stored) in enumerate(extraction_results):
                    if content:
                        extracted_contents.append({
                            'url': urls[i],
                            'title': content.get('title', 'Untitled'),
                            'text': content.get('text', ''),
                            'stored': was_stored
                        })
                        if was_stored:
                            stored_count += 1
                        total_chars += len(content.get('text', ''))
                
                # Step 4: RAG search for synthesis if we have stored content  
                synthesis_text = ""
                if stored_count > 0:
                    rag_result = await vectorizer.rag_search(query, max_results=5)
                    if rag_result.retrieved_chunks:
                        synthesis_text = f"\n\n**📚 Knowledge Base Synthesis:**\n"
                        for chunk, source in zip(rag_result.retrieved_chunks[:3], rag_result.sources[:3]):
                            synthesis_text += f"• {source.get('title', 'Unknown')}: {chunk[:200]}...\n"
                
                # Format comprehensive response
                response = f"**🔍 Research Results for: '{query}'**\n\n"
                response += f"**📊 Summary:**\n"
                response += f"• Found {len(urls)} sources\n"
                response += f"• Extracted {len(extracted_contents)} articles\n"
                response += f"• Stored {stored_count} in knowledge base\n"
                response += f"• Total content: {total_chars:,} characters\n\n"
                
                response += f"**🔗 Sources Found:**\n"
                for summary in search_summaries:
                    response += f"{summary}\n"
                
                response += f"\n**📄 Extracted Content:**\n"
                for content in extracted_contents[:2]:  # Show first 2
                    stored_indicator = "💾 [STORED]" if content['stored'] else "📄 [DIRECT]"
                    response += f"{stored_indicator} **{content['title']}**\n"
                    response += f"URL: {content['url']}\n"
                    response += f"Content: {content['text'][:400]}...\n\n"
                
                if len(extracted_contents) > 2:
                    response += f"... and {len(extracted_contents) - 2} more sources\n\n"
                
                response += synthesis_text
                
                return [types.TextContent(type="text", text=response)]
                
            except Exception as e:
                logger.error(f"Research query failed: {e}")
                return [types.TextContent(
                    type="text", 
                    text=f"Research failed due to error: {str(e)}"
                )]
                
        elif name == "smart_answer":
            question = arguments.get("question")
            prefer_stored = arguments.get("prefer_stored", True)
            
            if not question:
                return [types.TextContent(
                    type="text",
                    text="Error: Question parameter is required"
                )]
            
            logger.info(f"Smart answer for: {question}")
            
            try:
                response_parts = []
                
                # Step 1: Check knowledge base first if preferred
                if prefer_stored:
                    rag_result = await vectorizer.rag_search(question, max_results=3)
                    
                    if rag_result.retrieved_chunks:
                        response_parts.append(f"**📚 From Knowledge Base:**")
                        for i, (chunk, source, score) in enumerate(zip(
                            rag_result.retrieved_chunks[:2],
                            rag_result.sources[:2], 
                            rag_result.similarity_scores[:2]
                        )):
                            response_parts.append(f"\n{i+1}. **{source.get('title', 'Unknown')}** (Relevance: {score:.3f})")
                            response_parts.append(f"   {chunk[:300]}...")
                            response_parts.append(f"   Source: {source.get('url', 'Unknown')}")
                        
                        # If high relevance, return just knowledge base results
                        if len(rag_result.similarity_scores) > 0 and rag_result.similarity_scores[0] > 0.75:
                            response_parts.append(f"\n\n*High relevance match found in knowledge base.*")
                            return [types.TextContent(type="text", text="\n".join(response_parts))]
                    else:
                        response_parts.append("📚 No relevant information found in knowledge base.")
                
                # Step 2: Supplement with web search
                response_parts.append(f"\n\n**🔍 Current Web Information:**")
                
                search_results = await websearch_service.web_search(question, 2)
                if "error" not in search_results and search_results.get("results"):
                    
                    # Extract content from top result for direct answer
                    top_url = search_results["results"][0].get("url")
                    if top_url:
                        content = await websearch_service.extract_content(top_url)
                        if "error" not in content:
                            text = content.get('text', '')
                            
                            # Direct answer if content is small enough
                            if len(text) < 2000:
                                response_parts.append(f"\n**{content.get('title', 'Current Information')}:**")
                                response_parts.append(f"{text[:800]}...")
                                response_parts.append(f"\nSource: {top_url}")
                            else:
                                # Store large content and provide summary
                                content_result = ContentResult(
                                    url=top_url,
                                    title=content.get('title', 'Web Search Result'),
                                    text=text,
                                    timestamp=time.time()
                                )
                                await vectorizer.process_content(content_result)
                                
                                response_parts.append(f"\n**{content.get('title', 'Current Information')}** [STORED IN KB]:")
                                response_parts.append(f"{text[:500]}...")
                                response_parts.append(f"Full content stored in knowledge base for future queries.")
                                response_parts.append(f"Source: {top_url}")
                
                return [types.TextContent(type="text", text="\n".join(response_parts))]
                
            except Exception as e:
                logger.error(f"Smart answer failed: {e}")
                return [types.TextContent(
                    type="text",
                    text=f"Smart answer failed: {str(e)}"
                )]
        
        else:
            return [types.TextContent(
                type="text",
                text=f"Unknown tool: {name}"
            )]
            
    except Exception as e:
        logger.error(f"Tool call failed: {e}")
        return [types.TextContent(
            type="text",
            text=f"Tool execution failed: {str(e)}"
        )]

async def main():
    """Main server function"""
    logger.info("Starting WebSearch MCP Server")
    
    # Use stdio transport for MCP
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )

if __name__ == "__main__":
    asyncio.run(main())