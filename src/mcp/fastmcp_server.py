"""
Working MCP Server using FastMCP for WebSearch, Content Extraction, and RAG
Based on official FastMCP examples and documentation
"""

import asyncio
import httpx
import time
import hashlib
import json
from typing import Dict, List, Any
from fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("websearch-server")

# Initialize services
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

from services.websearch import WebSearchService
from services.vectorstore import ContentVectorizer, ContentResult

# Global service instances
websearch_service = WebSearchService()
vectorizer = ContentVectorizer(chroma_path="./data/chroma_db")

@mcp.tool()
async def web_search(query: str, max_results: int = 5) -> str:
    """Search the internet for current information about any topic"""
    print(f"🔍 Searching web for: {query}")
    
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
        
        response = f"Found {results.get('number_of_results', 0)} search results:\n\n" + "\n".join(formatted_results)
        print(f"✅ Found {len(formatted_results)} results")
        return response
        
    except Exception as e:
        error_msg = f"Search error: {str(e)}"
        print(f"❌ {error_msg}")
        return error_msg

@mcp.tool()
async def extract_content(url: str) -> str:
    """Extract full text content from a webpage URL"""
    print(f"📄 Extracting content from: {url}")
    
    try:
        content = await websearch_service.extract_content(url)
        
        if "error" in content:
            return f"Content extraction failed: {content['error']}"
        
        response = f"**Title:** {content.get('title', 'No Title')}\n"
        response += f"**URL:** {url}\n"
        response += f"**Content Length:** {len(content.get('text', ''))} characters\n\n"
        response += f"**Content:**\n{content.get('text', 'No content extracted')[:1500]}..."
        
        print(f"✅ Extracted {len(content.get('text', ''))} characters")
        return response
        
    except Exception as e:
        error_msg = f"Extraction error: {str(e)}"
        print(f"❌ {error_msg}")
        return error_msg

@mcp.tool()
async def rag_search(query: str, max_results: int = 10) -> str:
    """Search through previously stored knowledge base for relevant information"""
    print(f"🧠 Searching knowledge base for: {query}")
    
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
        
        response = f"Found {len(rag_result.retrieved_chunks)} relevant chunks:\n\n" + "\n".join(formatted_results)
        print(f"✅ Found {len(rag_result.retrieved_chunks)} relevant chunks")
        return response
        
    except Exception as e:
        error_msg = f"RAG search error: {str(e)}"
        print(f"❌ {error_msg}")
        return error_msg

@mcp.tool()
async def store_content(url: str, title: str, text: str) -> str:
    """Store extracted content in knowledge base for future searches"""
    print(f"💾 Storing content: {title}")
    
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
            response = f"✅ Successfully stored '{title}' in knowledge base\n"
            response += f"Generated {chunks_count} chunks from {len(text)} characters"
            print(f"✅ Stored {chunks_count} chunks")
        else:
            response = f"❌ Failed to store content: {result.get('error', 'Unknown error')}"
            print(f"❌ Storage failed")
        
        return response
        
    except Exception as e:
        error_msg = f"Storage error: {str(e)}"
        print(f"❌ {error_msg}")
        return error_msg

@mcp.tool()
async def research_query(query: str, max_sources: int = 3, store_results: bool = True) -> str:
    """Comprehensive research with parallel searches, automatic content extraction, and storage. 
    Perfect for complex queries requiring multiple sources like company information."""
    print(f"🔍 Starting comprehensive research for: {query}")
    
    try:
        # Step 1: Web search
        print("   📊 Step 1/4: Web search...")
        search_results = await websearch_service.web_search(query, max_sources)
        
        if "error" in search_results:
            return f"Research failed - search error: {search_results['error']}"
        
        urls = []
        search_summaries = []
        for result in search_results.get("results", [])[:max_sources]:
            urls.append(result.get('url'))
            search_summaries.append(f"• {result.get('title', 'No Title')}: {result.get('content', '')[:150]}...")
        
        if not urls:
            return f"No search results found for: {query}"
        
        print(f"   ✅ Found {len(urls)} sources")
        
        # Step 2: Parallel content extraction
        print("   📄 Step 2/4: Extracting content in parallel...")
        
        async def extract_and_process(url):
            try:
                content = await websearch_service.extract_content(url)
                if "error" not in content:
                    content_length = len(content.get('text', ''))
                    
                    # Store if substantial content
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
                print(f"   ⚠️ Failed to process {url}: {e}")
                return None, False
        
        # Execute extractions in parallel
        extraction_results = await asyncio.gather(*[extract_and_process(url) for url in urls])
        
        # Step 3: Compile results
        print("   📋 Step 3/4: Compiling results...")
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
        
        print(f"   ✅ Extracted {len(extracted_contents)} articles, stored {stored_count}")
        
        # Step 4: RAG search for synthesis if we have stored content  
        print("   🧠 Step 4/4: Knowledge synthesis...")
        synthesis_text = ""
        if stored_count > 0:
            rag_result = await vectorizer.rag_search(query, max_results=5)
            if rag_result.retrieved_chunks:
                synthesis_text = f"\n\n**📚 Knowledge Base Synthesis:**\n"
                for chunk, source in zip(rag_result.retrieved_chunks[:3], rag_result.sources[:3]):
                    synthesis_text += f"• {source.get('title', 'Unknown')}: {chunk[:200]}...\n"
        
        # Format comprehensive response
        response = f"🔍 **Research Results for: '{query}'**\n\n"
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
        
        print(f"✅ Research complete! {len(urls)} sources → {len(extracted_contents)} extracted → {stored_count} stored")
        return response
        
    except Exception as e:
        error_msg = f"Research failed: {str(e)}"
        print(f"❌ {error_msg}")
        return error_msg

@mcp.tool()
async def smart_answer(question: str, prefer_stored: bool = True) -> str:
    """Get intelligent answers by first checking knowledge base, then supplementing with web search if needed. 
    Optimized for direct responses to questions like 'Who is the contact person for X company?'"""
    print(f"💡 Smart answer for: {question}")
    
    try:
        response_parts = []
        
        # Step 1: Check knowledge base first if preferred
        print("   🧠 Step 1/3: Checking knowledge base...")
        if prefer_stored:
            rag_result = await vectorizer.rag_search(question, max_results=3)
            
            if rag_result.retrieved_chunks:
                response_parts.append("**📚 From Knowledge Base:**")
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
                    print("   ✅ High relevance found in knowledge base")
                    return "\n".join(response_parts)
                
                print(f"   ℹ️ Found {len(rag_result.retrieved_chunks)} results, but low relevance")
            else:
                response_parts.append("📚 No relevant information found in knowledge base.")
                print("   ℹ️ No relevant info in knowledge base")
        
        # Step 2: Supplement with web search
        print("   🔍 Step 2/3: Web search...")
        response_parts.append(f"\n\n**🔍 Current Web Information:**")
        
        search_results = await websearch_service.web_search(question, 2)
        if "error" not in search_results and search_results.get("results"):
            
            # Extract content from top result for direct answer
            top_url = search_results["results"][0].get("url")
            if top_url:
                print(f"   📄 Step 3/3: Extracting from top result...")
                content = await websearch_service.extract_content(top_url)
                if "error" not in content:
                    text = content.get('text', '')
                    
                    # Direct answer if content is small enough
                    if len(text) < 2000:
                        response_parts.append(f"\n**{content.get('title', 'Current Information')}:**")
                        response_parts.append(f"{text[:800]}...")
                        response_parts.append(f"\nSource: {top_url}")
                        print(f"   ✅ Direct answer from {len(text)} chars")
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
                        print(f"   💾 Stored large content ({len(text)} chars) and provided summary")
        
        print("   ✅ Smart answer complete")
        return "\n".join(response_parts)
        
    except Exception as e:
        error_msg = f"Smart answer failed: {str(e)}"
        print(f"❌ {error_msg}")
        return error_msg

if __name__ == "__main__":
    # Run the server using FastMCP's built-in runner
    mcp.run()