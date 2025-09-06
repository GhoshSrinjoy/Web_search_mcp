#!/usr/bin/env python3
"""
Simple working Ollama client with direct function calls
No MCP complexity - just working tools that show progress
"""

import asyncio
import json
import httpx
from typing import Dict, List, Any
import logging
import sys
import os

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

from services.websearch import WebSearchService
from services.vectorstore import ContentVectorizer, ContentResult
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("simple-client")

class SimpleOllamaClient:
    def __init__(self):
        # Ollama configuration
        self.ollama_url = "http://host.docker.internal:11434"
        self.current_model = "gpt-oss:20b"
        self.available_models = ["gpt-oss:20b", "qwen3:0.6b", "qwen3:8b"]
        
        # Initialize services
        self.websearch = WebSearchService()
        self.vectorizer = ContentVectorizer(chroma_path="./data/chroma_db")
        
        # Define tools in Ollama format
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "research_company",
                    "description": "Research a company comprehensively - searches web, extracts content, stores data, and provides detailed results. Use this for company questions.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "company_name": {"type": "string", "description": "Company name to research"},
                            "query_details": {"type": "string", "description": "Specific details to find (e.g., 'contact person and office location')"}
                        },
                        "required": ["company_name", "query_details"]
                    }
                }
            },
            {
                "type": "function", 
                "function": {
                    "name": "quick_web_search",
                    "description": "Quick web search for current information. Shows progress and results.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query"},
                            "max_results": {"type": "integer", "description": "Max results (default: 5)"}
                        },
                        "required": ["query"]
                    }
                }
            }
        ]
        
        logger.info(f"Initialized Simple Ollama Client with {len(self.tools)} tools")

    async def research_company(self, company_name: str, query_details: str) -> str:
        """Comprehensive company research with progress indicators"""
        print(f"\n🏢 RESEARCHING: {company_name}")
        print(f"📋 Looking for: {query_details}")
        print("=" * 50)
        
        try:
            # Step 1: Web Search
            print("🔍 STEP 1/4: Web Search...")
            search_query = f"{company_name} {query_details}"
            search_results = await self.websearch.web_search(search_query, 3)
            
            if "error" in search_results:
                return f"❌ Search failed: {search_results['error']}"
            
            urls = [result.get('url') for result in search_results.get("results", [])[:3]]
            print(f"   ✅ Found {len(urls)} sources")
            for i, result in enumerate(search_results.get("results", [])[:3], 1):
                print(f"   {i}. {result.get('title', 'No Title')}")
            
            if not urls:
                return f"❌ No search results found for {company_name}"
            
            # Step 2: Content Extraction
            print(f"\n📄 STEP 2/4: Extracting content from {len(urls)} sources...")
            extracted_data = []
            
            for i, url in enumerate(urls, 1):
                print(f"   📄 Extracting {i}/{len(urls)}: {url}")
                try:
                    content = await self.websearch.extract_content(url)
                    if "error" not in content and len(content.get('text', '')) > 200:
                        extracted_data.append({
                            'url': url,
                            'title': content.get('title', 'Untitled'),
                            'text': content.get('text', ''),
                            'chars': len(content.get('text', ''))
                        })
                        print(f"   ✅ Extracted {len(content.get('text', '')):,} characters")
                    else:
                        print(f"   ⚠️ Failed or too small")
                except Exception as e:
                    print(f"   ❌ Error: {e}")
            
            if not extracted_data:
                return f"❌ No content could be extracted for {company_name}"
            
            print(f"   ✅ Successfully extracted {len(extracted_data)} articles")
            
            # Step 3: Store in Knowledge Base
            print(f"\n💾 STEP 3/4: Storing {len(extracted_data)} articles in knowledge base...")
            stored_count = 0
            
            for i, data in enumerate(extracted_data, 1):
                print(f"   💾 Storing {i}/{len(extracted_data)}: {data['title']}")
                try:
                    content_result = ContentResult(
                        url=data['url'],
                        title=data['title'],
                        text=data['text'],
                        timestamp=time.time()
                    )
                    result = await self.vectorizer.process_content(content_result)
                    if result.get('status') == 'success':
                        stored_count += 1
                        chunks = result.get('chunks', 0)
                        print(f"   ✅ Stored as {chunks} chunks")
                    else:
                        print(f"   ⚠️ Storage failed")
                except Exception as e:
                    print(f"   ❌ Storage error: {e}")
            
            print(f"   ✅ Stored {stored_count}/{len(extracted_data)} articles")
            
            # Step 4: Analyze and Extract Key Info
            print(f"\n🧠 STEP 4/4: Analyzing content for {query_details}...")
            
            # Search knowledge base for specific info
            rag_result = await self.vectorizer.rag_search(f"{company_name} {query_details}", max_results=5)
            
            # Build comprehensive response
            total_chars = sum(data['chars'] for data in extracted_data)
            
            response = f"🏢 **{company_name.upper()} RESEARCH COMPLETE**\n"
            response += "=" * 50 + "\n\n"
            
            response += f"📊 **SUMMARY:**\n"
            response += f"• Searched web: 3 queries\n" 
            response += f"• Found sources: {len(urls)}\n"
            response += f"• Extracted articles: {len(extracted_data)}\n"
            response += f"• Stored in KB: {stored_count}\n"
            response += f"• Total content: {total_chars:,} characters\n\n"
            
            response += f"🔍 **KEY INFORMATION ABOUT {query_details.upper()}:**\n"
            if rag_result.retrieved_chunks:
                for i, (chunk, source, score) in enumerate(zip(
                    rag_result.retrieved_chunks[:3],
                    rag_result.sources[:3],
                    rag_result.similarity_scores[:3]
                ), 1):
                    response += f"{i}. **{source.get('title', 'Unknown')}** (Relevance: {score:.2f})\n"
                    response += f"   {chunk[:400]}...\n\n"
            else:
                response += "❌ No specific matches found in extracted content.\n\n"
            
            response += f"📄 **EXTRACTED SOURCES:**\n"
            for i, data in enumerate(extracted_data, 1):
                response += f"{i}. **{data['title']}**\n"
                response += f"   URL: {data['url']}\n"
                response += f"   Content: {data['text'][:300]}...\n"
                response += f"   Length: {data['chars']:,} characters\n\n"
            
            print("✅ RESEARCH COMPLETE!")
            print("=" * 50)
            
            return response
            
        except Exception as e:
            error_msg = f"❌ Research failed: {str(e)}"
            print(error_msg)
            return error_msg

    async def quick_web_search(self, query: str, max_results: int = 5) -> str:
        """Quick web search with progress"""
        print(f"\n🔍 QUICK SEARCH: {query}")
        print("-" * 30)
        
        try:
            print("🔍 Searching web...")
            results = await self.websearch.web_search(query, max_results)
            
            if "error" in results:
                return f"❌ Search failed: {results['error']}"
            
            count = results.get('number_of_results', 0)
            print(f"✅ Found {count} results")
            
            response = f"🔍 **SEARCH RESULTS FOR: '{query}'**\n\n"
            
            for i, result in enumerate(results.get("results", []), 1):
                response += f"{i}. **{result.get('title', 'No Title')}**\n"
                response += f"   URL: {result.get('url', '')}\n"
                response += f"   {result.get('content', 'No description')[:200]}...\n\n"
            
            return response
            
        except Exception as e:
            error_msg = f"❌ Search error: {str(e)}"
            print(error_msg)
            return error_msg

    async def call_tool(self, tool_name: str, arguments: Dict) -> str:
        """Execute tool calls"""
        if tool_name == "research_company":
            return await self.research_company(
                arguments.get("company_name", ""),
                arguments.get("query_details", "")
            )
        elif tool_name == "quick_web_search":
            return await self.quick_web_search(
                arguments.get("query", ""),
                arguments.get("max_results", 5)
            )
        else:
            return f"❌ Unknown tool: {tool_name}"

    async def chat_with_ollama(self, user_input: str) -> str:
        """Chat with Ollama using tools"""
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                messages = [{"role": "user", "content": user_input}]
                
                # First call with tools
                response = await client.post(
                    f"{self.ollama_url}/api/chat",
                    json={
                        "model": self.current_model,
                        "messages": messages,
                        "tools": self.tools,
                        "stream": False,
                        "options": {"temperature": 0.1}
                    }
                )
                
                if response.status_code != 200:
                    return f"❌ Ollama error: {response.status_code} - {response.text}"
                
                result = response.json()
                assistant_message = result.get("message", {})
                tool_calls = assistant_message.get("tool_calls", [])
                
                if not tool_calls:
                    return assistant_message.get("content", "No response from model")
                
                # Execute tools
                messages.append(assistant_message)
                
                for tool_call in tool_calls:
                    function = tool_call.get("function", {})
                    tool_name = function.get("name", "")
                    arguments = function.get("arguments", {})
                    
                    print(f"\n🔧 CALLING TOOL: {tool_name}")
                    print(f"📋 Arguments: {arguments}")
                    
                    tool_result = await self.call_tool(tool_name, arguments)
                    
                    messages.append({
                        "role": "tool",
                        "content": tool_result,
                        "tool_call_id": tool_call.get("id", "")
                    })
                
                # Final response
                final_response = await client.post(
                    f"{self.ollama_url}/api/chat",
                    json={
                        "model": self.current_model,
                        "messages": messages,
                        "stream": False,
                        "options": {"temperature": 0.3}
                    }
                )
                
                if final_response.status_code != 200:
                    return f"❌ Final response error: {final_response.status_code}"
                
                final_result = final_response.json()
                return final_result.get("message", {}).get("content", "No final response")
                
        except Exception as e:
            return f"❌ Chat error: {str(e)}"

    def switch_model(self, model_name: str):
        """Switch model"""
        if model_name in self.available_models:
            self.current_model = model_name
            print(f"✅ Switched to: {model_name}")
        else:
            print(f"❌ Model not available. Available: {', '.join(self.available_models)}")

    async def chat_loop(self):
        """Interactive chat"""
        print(f"\n🚀 SIMPLE OLLAMA CLIENT")
        print("=" * 40)
        print(f"Current model: {self.current_model}")
        print(f"Available tools: {', '.join([t['function']['name'] for t in self.tools])}")
        print("\nCommands:")
        print("  /model <name> - Switch model")
        print("  /exit - Exit")
        print("\nThe AI will automatically use tools and show progress!\n")
        
        while True:
            try:
                user_input = input("You: ").strip()
                
                if user_input.lower() in ['/exit', '/quit']:
                    break
                elif user_input.startswith('/model '):
                    model_name = user_input[7:].strip()
                    self.switch_model(model_name)
                    continue
                elif not user_input:
                    continue
                
                print(f"\n🤔 Processing with {self.current_model}...")
                response = await self.chat_with_ollama(user_input)
                print(f"\n🤖 {self.current_model}:")
                print(response)
                print("\n" + "="*60 + "\n")
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"\n❌ Error: {e}\n")

async def main():
    client = SimpleOllamaClient()
    await client.chat_loop()

if __name__ == "__main__":
    asyncio.run(main())