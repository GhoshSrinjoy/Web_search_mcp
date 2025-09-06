"""
Individual MCP Server for Content Extraction Component
"""
from fastmcp import FastMCP
import asyncio
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))
from services.websearch import WebSearchService

mcp = FastMCP("extractor")
websearch_service = WebSearchService()

@mcp.tool()
async def extract_content(url: str) -> str:
    """Extract full text content from a webpage URL"""
    try:
        content = await websearch_service.extract_content(url)
        
        if "error" in content:
            return f"Content extraction failed: {content['error']}"
        
        response = f"**Title:** {content.get('title', 'No Title')}\n"
        response += f"**URL:** {url}\n"
        response += f"**Content Length:** {len(content.get('text', ''))} characters\n\n"
        response += f"**Content:**\n{content.get('text', 'No content extracted')[:1500]}..."
        
        return response
        
    except Exception as e:
        return f"Extraction error: {str(e)}"

if __name__ == "__main__":
    mcp.run()