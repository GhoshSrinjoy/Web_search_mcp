#!/usr/bin/env python3
"""
Individual MCP Server for RAG Search Component
"""
from fastmcp import FastMCP
import asyncio
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))
from services.vectorstore import ContentVectorizer

mcp = FastMCP("rag")
vectorizer = ContentVectorizer(chroma_path="./data/chroma_db")

@mcp.tool()
async def rag_search(query: str, max_results: int = 10) -> str:
    """Search through previously stored knowledge base for relevant information"""
    try:
        rag_result = await vectorizer.rag_search(query, max_results)
        
        if not rag_result.retrieved_chunks:
            return f"No relevant information found in knowledge base for query: '{query}'"
        
        formatted_results = []
        for i, (chunk, source, score) in enumerate(zip(
            rag_result.retrieved_chunks,
            rag_result.sources,
            rag_result.similarity_scores
        ), 1):
            formatted_results.append(
                f"{i}. **{source.get('title', 'No Title')}** (Score: {score:.3f})\n"
                f"   URL: {source.get('url', '')}\n"
                f"   {chunk[:300]}...\n"
            )
        
        return f"Found {len(rag_result.retrieved_chunks)} relevant chunks:\n\n" + "\n".join(formatted_results)
        
    except Exception as e:
        return f"RAG search error: {str(e)}"

if __name__ == "__main__":
    mcp.run()