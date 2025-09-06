#!/usr/bin/env python3
"""
Individual MCP Server for Storage Component
"""
from fastmcp import FastMCP
import asyncio
import sys
import os
import time
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))
from services.vectorstore import ContentVectorizer, ContentResult

mcp = FastMCP("storage")
vectorizer = ContentVectorizer(chroma_path="./data/chroma_db")

@mcp.tool()
async def store_content(url: str, title: str, text: str) -> str:
    """Store extracted content in knowledge base for future searches"""
    try:
        content_result = ContentResult(
            url=url,
            title=title,
            text=text,
            timestamp=time.time()
        )
        
        result = await vectorizer.process_content(content_result)
        
        if result.get('status') == 'success':
            chunks_count = result.get('chunks', 0)
            response = f"Successfully stored '{title}' in knowledge base\n"
            response += f"Generated {chunks_count} chunks from {len(text)} characters"
        else:
            response = f"Failed to store content: {result.get('error', 'Unknown error')}"
        
        return response
        
    except Exception as e:
        return f"Storage error: {str(e)}"

@mcp.tool()
def knowledge_stats() -> str:
    """Get statistics about the current knowledge base"""
    try:
        stats = vectorizer.get_knowledge_stats()
        
        response = "**Knowledge Base Statistics:**\n"
        response += f"- Total chunks: {stats.get('total_chunks', 0)}\n"
        response += f"- Unique sources: {stats.get('unique_sources', 0)}\n"
        response += f"- Unique documents: {stats.get('unique_titles', 0)}\n"
        response += f"- Embedding model: {stats.get('embedding_model', 'N/A')}\n"
        response += f"- Collection: {stats.get('collection_name', 'N/A')}\n"
        
        return response
        
    except Exception as e:
        return f"Stats error: {str(e)}"

if __name__ == "__main__":
    mcp.run()