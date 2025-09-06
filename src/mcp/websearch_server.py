#!/usr/bin/env python3
"""
Individual MCP Server for Web Search Component
"""
from fastmcp import FastMCP
import asyncio
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))
from services.websearch import WebSearchService

mcp = FastMCP("websearch")
websearch_service = WebSearchService()

@mcp.tool()
async def web_search(query: str, max_results: int = 5) -> str:
    """Simple web search that returns basic search results. Use 'research_query' for comprehensive research with content extraction and storage."""
    try:
        results = await websearch_service.web_search(query, max_results)
        
        if "error" in results:
            return f"Search failed: {results['error']}"
        
        formatted_results = []
        for i, result in enumerate(results.get("results", []), 1):
            formatted_results.append(
                f"{i}. **{result.get('title', 'No Title')}**\n"
                f"   URL: {result.get('url', '')}\n"
                f"   {result.get('content', 'No description')[:200]}...\n"
            )
        
        return f"Found {results.get('number_of_results', 0)} search results:\n\n" + "\n".join(formatted_results)
        
    except Exception as e:
        return f"Search error: {str(e)}"

if __name__ == "__main__":
    mcp.run()