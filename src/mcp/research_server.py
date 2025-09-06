"""
Individual MCP Server for Research Component (combines multiple operations)
"""
from fastmcp import FastMCP
import asyncio
import sys
import os
import time
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))
from services.websearch import WebSearchService
from services.vectorstore import ContentVectorizer, ContentResult

mcp = FastMCP("research")
websearch_service = WebSearchService()
vectorizer = ContentVectorizer(chroma_path="./data/chroma_db")

@mcp.tool()
async def research_query(query: str, max_sources: int = 3, store_results: bool = True) -> str:
    """RECOMMENDED: Complete research workflow - searches web, extracts full content, stores in vector DB, and provides comprehensive analysis. Use this for detailed research questions."""
    try:
        # Step 1: Web search
        search_results = await websearch_service.web_search(query, max_sources)
        
        if "error" in search_results:
            return f"Research failed - search error: {search_results['error']}"
        
        urls = [result.get('url') for result in search_results.get("results", [])[:max_sources]]
        if not urls:
            return f"No search results found for: {query}"
        
        # Step 2: Parallel content extraction
        async def extract_and_process(url):
            try:
                content = await websearch_service.extract_content(url)
                if "error" not in content and len(content.get('text', '')) > 500:
                    if store_results:
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
            except Exception:
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
        
        # Format comprehensive response
        response = f"**Research Results for: '{query}'**\n\n"
        response += f"**Summary:**\n"
        response += f"• Found {len(urls)} sources\n"
        response += f"• Extracted {len(extracted_contents)} articles\n"
        response += f"• Stored {stored_count} in knowledge base\n"
        response += f"• Total content: {total_chars:,} characters\n\n"
        
        response += f"**Extracted Content:**\n"
        for content in extracted_contents[:2]:  # Show first 2
            stored_indicator = "[STORED]" if content['stored'] else "[DIRECT]"
            response += f"{stored_indicator} **{content['title']}**\n"
            response += f"URL: {content['url']}\n"
            response += f"Content: {content['text'][:400]}...\n\n"
        
        return response
        
    except Exception as e:
        return f"Research failed: {str(e)}"

@mcp.tool()
async def smart_answer(question: str, prefer_stored: bool = True) -> str:
    """Get intelligent answers by first checking knowledge base, then supplementing with web search if needed"""
    try:
        response_parts = []
        
        # Step 1: Check knowledge base first
        if prefer_stored:
            rag_result = await vectorizer.rag_search(question, max_results=3)
            
            if rag_result.retrieved_chunks:
                response_parts.append("**From Knowledge Base:**")
                for i, (chunk, source, score) in enumerate(zip(
                    rag_result.retrieved_chunks[:2],
                    rag_result.sources[:2], 
                    rag_result.similarity_scores[:2]
                ), 1):
                    response_parts.append(f"\n{i}. **{source.get('title', 'Unknown')}** (Relevance: {score:.3f})")
                    response_parts.append(f"   {chunk[:300]}...")
                    response_parts.append(f"   Source: {source.get('url', 'Unknown')}")
                
                # If high relevance, return knowledge base results
                if len(rag_result.similarity_scores) > 0 and rag_result.similarity_scores[0] > 0.75:
                    response_parts.append(f"\n\n*High relevance match found in knowledge base.*")
                    return "\n".join(response_parts)
            else:
                response_parts.append("No relevant information found in knowledge base.")
        
        # Step 2: Supplement with web search
        response_parts.append(f"\n\n**Current Web Information:**")
        
        search_results = await websearch_service.web_search(question, 2)
        if "error" not in search_results and search_results.get("results"):
            
            # Extract content from top result
            top_url = search_results["results"][0].get("url")
            if top_url:
                content = await websearch_service.extract_content(top_url)
                if "error" not in content:
                    text = content.get('text', '')
                    
                    if len(text) < 2000:
                        response_parts.append(f"\n**{content.get('title', 'Current Information')}:**")
                        response_parts.append(f"{text[:800]}...")
                        response_parts.append(f"\nSource: {top_url}")
                    else:
                        # Store large content
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
        
        return "\n".join(response_parts)
        
    except Exception as e:
        return f"Smart answer failed: {str(e)}"

if __name__ == "__main__":
    mcp.run()