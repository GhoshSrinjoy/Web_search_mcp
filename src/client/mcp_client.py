"""
MCP Client that bridges Ollama with MCP server
Acts as a bridge between Ollama's function calling and MCP protocol
"""

import asyncio
import json
import httpx
import subprocess
from typing import Dict, List, Any, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp-client")

class MCPClient:
    def __init__(self, config_file: str = "mcp_client_config.json"):
        with open(config_file, 'r') as f:
            self.config = json.load(f)
        
        self.ollama_url = self.config["llm"]["baseUrl"]
        self.current_model = self.config.get("defaultModel", "gpt-oss:20b")
        self.available_models = self.config.get("availableModels", [])
        
        self.tools = []
        
        # Initialize tools immediately 
        self.initialize_tools()
    
    def initialize_tools(self):
        """Define tools for Ollama function calling"""
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "web_search",
                    "description": "Basic web search - use only for simple searches when you need URLs. For company info, use smart_answer or research_query instead.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query"},
                            "max_results": {"type": "integer", "description": "Max results (default: 5)"}
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "extract_content",
                    "description": "Extract content from a webpage",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "url": {"type": "string", "description": "URL to extract content from"}
                        },
                        "required": ["url"]
                    }
                }
            },
            {
                "type": "function", 
                "function": {
                    "name": "rag_search",
                    "description": "Search stored knowledge base for relevant information",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query"},
                            "max_results": {"type": "integer", "description": "Max results (default: 10)"}
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "store_content",
                    "description": "Store extracted content in knowledge base for future searches",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "url": {"type": "string", "description": "Source URL"},
                            "title": {"type": "string", "description": "Title of the content"},
                            "text": {"type": "string", "description": "Full text content to store"}
                        },
                        "required": ["url", "title", "text"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "research_query",
                    "description": "Use for deep research on companies/topics - does parallel searches, extracts content, and stores everything automatically. Perfect for building knowledge about new companies.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Research query (e.g., 'RX-Systems GMBH company information')"},
                            "max_sources": {"type": "integer", "description": "Max sources to research (default: 3)"},
                            "store_results": {"type": "boolean", "description": "Whether to store results in knowledge base (default: true)"}
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "smart_answer", 
                    "description": "BEST CHOICE for questions like 'Who is the contact person for X company?' - Automatically searches knowledge base first, then web if needed",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "question": {"type": "string", "description": "Question to answer"},
                            "prefer_stored": {"type": "boolean", "description": "Prefer stored knowledge over web search (default: true)"}
                        },
                        "required": ["question"]
                    }
                }
            }
        ]
        
        logger.info(f"Initialized {len(self.tools)} tools for Ollama")
    
    async def call_tool(self, tool_name: str, arguments: Dict) -> str:
        """Call tools by executing service functions directly"""
        try:
            # Direct service calls for tool execution
            
            if tool_name == "web_search":
                from services.websearch import WebSearchService
                websearch = WebSearchService()
                query = arguments.get("query", "")
                max_results = arguments.get("max_results", 5)
                results = await websearch.web_search(query, max_results)
                
                if "error" in results:
                    return f"Search failed: {results['error']}"
                
                formatted_results = []
                for i, result in enumerate(results.get("results", []), 1):
                    formatted_results.append(
                        f"{i}. **{result.get('title', 'No Title')}**\n"
                        f"   URL: {result.get('url', '')}\n" 
                        f"   {result.get('content', 'No description')[:150]}...\n"
                    )
                
                return f"Found {results.get('number_of_results', 0)} search results:\n\n" + "\n".join(formatted_results)
            
            elif tool_name == "extract_content":
                from services.websearch import WebSearchService
                websearch = WebSearchService()
                url = arguments.get("url", "")
                content = await websearch.extract_content(url)
                
                if "error" in content:
                    return f"Content extraction failed: {content['error']}"
                
                response = f"**Title:** {content.get('title', 'No Title')}\n"
                response += f"**URL:** {url}\n\n"
                response += f"**Content:**\n{content.get('text', 'No content')[:1000]}..."
                
                return response
            
            elif tool_name == "rag_search":
                from services.vectorstore import ContentVectorizer
                vectorizer = ContentVectorizer(chroma_path="./data/chroma_db")
                query = arguments.get("query", "")
                max_results = arguments.get("max_results", 10)
                rag_result = await vectorizer.rag_search(query, max_results)
                
                if not rag_result.retrieved_chunks:
                    return f"No relevant information found for: '{query}'"
                
                formatted_results = []
                for i, (chunk, source, score) in enumerate(zip(
                    rag_result.retrieved_chunks[:3],
                    rag_result.sources[:3],
                    rag_result.similarity_scores[:3]
                ), 1):
                    formatted_results.append(
                        f"{i}. **{source.get('title', 'Unknown')}** (Score: {score:.3f})\n"
                        f"   {chunk[:200]}...\n"
                    )
                
                return f"Found {len(rag_result.retrieved_chunks)} relevant results:\n\n" + "\n".join(formatted_results)
            
            elif tool_name == "store_content":
                from services.vectorstore import ContentVectorizer, ContentResult
                import time
                
                vectorizer = ContentVectorizer(chroma_path="./data/chroma_db")
                url = arguments.get("url", "")
                title = arguments.get("title", "")
                text = arguments.get("text", "")
                
                if not all([url, title, text]):
                    return "Error: URL, title, and text are required for storing content"
                
                content_result = ContentResult(
                    url=url,
                    title=title,
                    text=text,
                    timestamp=time.time()
                )
                
                result = await vectorizer.process_content(content_result)
                
                if result.get('status') == 'success':
                    chunks_count = result.get('chunks', 0)
                    return f"✅ Stored '{title}' in knowledge base\nGenerated {chunks_count} chunks from {len(text)} characters"
                else:
                    return f"❌ Failed to store content: {result.get('error', 'Unknown error')}"
            
            elif tool_name == "research_query":
                from services.websearch import WebSearchService
                from services.vectorstore import ContentVectorizer, ContentResult
                import asyncio
                import time
                
                websearch = WebSearchService()
                vectorizer = ContentVectorizer(chroma_path="./data/chroma_db")
                
                query = arguments.get("query", "")
                max_sources = arguments.get("max_sources", 3)
                store_results = arguments.get("store_results", True)
                
                # Step 1: Web search
                search_results = await websearch.web_search(query, max_sources)
                
                if "error" in search_results:
                    return f"Research failed - search error: {search_results['error']}"
                
                urls = [result.get('url') for result in search_results.get("results", [])[:max_sources]]
                if not urls:
                    return f"No search results found for: {query}"
                
                # Step 2: Parallel content extraction and storage
                async def extract_and_store(url):
                    try:
                        content = await websearch.extract_content(url)
                        if "error" not in content and len(content.get('text', '')) > 500:
                            if store_results:
                                content_result = ContentResult(
                                    url=url,
                                    title=content.get('title', 'Untitled'),
                                    text=content.get('text', ''),
                                    timestamp=time.time()
                                )
                                await vectorizer.process_content(content_result)
                                return content, True
                            else:
                                return content, False
                        return None, False
                    except Exception as e:
                        return None, False
                
                # Execute in parallel
                extraction_results = await asyncio.gather(*[extract_and_store(url) for url in urls])
                
                # Compile results
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
                
                # Format response
                response = f"🔍 **Research Results for: '{query}'**\n\n"
                response += f"📊 **Summary:**\n"
                response += f"• Found {len(urls)} sources\n"
                response += f"• Extracted {len(extracted_contents)} articles\n"
                response += f"• Stored {stored_count} in knowledge base\n"
                response += f"• Total content: {total_chars:,} characters\n\n"
                
                response += f"📄 **Key Content:**\n"
                for i, content in enumerate(extracted_contents[:2], 1):
                    stored_indicator = "💾 [STORED]" if content['stored'] else "📄 [DIRECT]"
                    response += f"{i}. {stored_indicator} **{content['title']}**\n"
                    response += f"   {content['text'][:300]}...\n\n"
                
                return response
            
            elif tool_name == "smart_answer":
                from services.websearch import WebSearchService
                from services.vectorstore import ContentVectorizer, ContentResult
                import time
                
                websearch = WebSearchService()
                vectorizer = ContentVectorizer(chroma_path="./data/chroma_db")
                
                question = arguments.get("question", "")
                prefer_stored = arguments.get("prefer_stored", True)
                
                response_parts = []
                
                # Step 1: Check knowledge base first
                if prefer_stored:
                    rag_result = await vectorizer.rag_search(question, max_results=3)
                    
                    if rag_result.retrieved_chunks:
                        response_parts.append("📚 **From Knowledge Base:**")
                        for i, (chunk, source, score) in enumerate(zip(
                            rag_result.retrieved_chunks[:2],
                            rag_result.sources[:2],
                            rag_result.similarity_scores[:2]
                        ), 1):
                            response_parts.append(f"\n{i}. **{source.get('title', 'Unknown')}** (Score: {score:.3f})")
                            response_parts.append(f"   {chunk[:250]}...")
                        
                        # If high relevance, return knowledge base results
                        if len(rag_result.similarity_scores) > 0 and rag_result.similarity_scores[0] > 0.75:
                            response_parts.append(f"\n\n*High relevance match found in knowledge base.*")
                            return "\n".join(response_parts)
                    else:
                        response_parts.append("📚 No relevant info found in knowledge base.")
                
                # Step 2: Supplement with web search
                response_parts.append(f"\n\n🔍 **Current Web Information:**")
                
                search_results = await websearch.web_search(question, 2)
                if "error" not in search_results and search_results.get("results"):
                    # Extract content from top result
                    top_url = search_results["results"][0].get("url")
                    if top_url:
                        content = await websearch.extract_content(top_url)
                        if "error" not in content:
                            text = content.get('text', '')
                            
                            if len(text) < 1500:
                                response_parts.append(f"\n**{content.get('title', 'Current Info')}:**")
                                response_parts.append(f"{text[:600]}...")
                            else:
                                # Store large content
                                content_result = ContentResult(
                                    url=top_url,
                                    title=content.get('title', 'Web Search Result'),
                                    text=text,
                                    timestamp=time.time()
                                )
                                await vectorizer.process_content(content_result)
                                
                                response_parts.append(f"\n**{content.get('title', 'Current Info')}** [STORED]:")
                                response_parts.append(f"{text[:400]}...")
                                response_parts.append("Full content stored in knowledge base.")
                
                return "\n".join(response_parts)
            
            else:
                return f"Unknown tool: {tool_name}"
                
        except Exception as e:
            logger.error(f"Tool call failed: {e}")
            return f"Tool execution error: {str(e)}"
    
    async def chat_with_ollama(self, user_input: str) -> str:
        """Chat with Ollama using function calling"""
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                # Create messages with tools
                messages = [
                    {"role": "user", "content": user_input}
                ]
                
                # First call to Ollama with tools
                response = await client.post(
                    f"{self.ollama_url}/api/chat",
                    json={
                        "model": self.current_model,
                        "messages": messages,
                        "tools": self.tools,
                        "stream": False,
                        "options": {
                            "temperature": 0.1
                        }
                    }
                )
                
                if response.status_code != 200:
                    return f"Ollama error: {response.status_code} - {response.text}"
                
                result = response.json()
                assistant_message = result.get("message", {})
                
                # Check if assistant wants to call tools
                tool_calls = assistant_message.get("tool_calls", [])
                
                if not tool_calls:
                    # No tool calls, return direct response
                    return assistant_message.get("content", "No response from model")
                
                # Process tool calls
                messages.append(assistant_message)  # Add assistant message with tool calls
                
                for tool_call in tool_calls:
                    function = tool_call.get("function", {})
                    tool_name = function.get("name", "")
                    arguments = function.get("arguments", {})
                    
                    print(f"🔧 Calling tool: {tool_name}")
                    
                    # Call the tool
                    tool_result = await self.call_tool(tool_name, arguments)
                    
                    # Add tool result to messages
                    messages.append({
                        "role": "tool",
                        "content": tool_result,
                        "tool_call_id": tool_call.get("id", "")
                    })
                
                # Second call to get final response
                final_response = await client.post(
                    f"{self.ollama_url}/api/chat",
                    json={
                        "model": self.current_model,
                        "messages": messages,
                        "stream": False,
                        "options": {
                            "temperature": 0.3
                        }
                    }
                )
                
                if final_response.status_code != 200:
                    return f"Final response error: {final_response.status_code}"
                
                final_result = final_response.json()
                final_content = final_result.get("message", {}).get("content", "")
                
                if not final_content.strip():
                    # If final response is empty, return the tool results directly
                    tool_summaries = []
                    for msg in messages:
                        if msg.get("role") == "tool":
                            content = msg.get("content", "")[:200]
                            tool_summaries.append(f"Tool result: {content}...")
                    return "Tool executed but no final response. Results:\n" + "\n".join(tool_summaries)
                
                return final_content
                
        except Exception as e:
            logger.error(f"Chat failed: {e}")
            return f"Chat error: {str(e)}"
    
    def switch_model(self, model_name: str):
        """Switch Ollama model"""
        if model_name in self.available_models:
            self.current_model = model_name
            print(f"✅ Switched to model: {model_name}")
        else:
            print(f"❌ Model {model_name} not available. Available: {', '.join(self.available_models)}")
    
    async def chat_loop(self):
        """Interactive chat loop"""
        print(f"\n🔄 MCP-Enabled Chat")
        print("=" * 25)
        print(f"Current model: {self.current_model}")
        print(f"Available models: {', '.join(self.available_models)}")
        print(f"Available tools: {', '.join([tool['function']['name'] for tool in self.tools])}")
        print("\nCommands:")
        print("  /model <name> - Switch model") 
        print("  /exit - Exit chat")
        print("\nThe LLM can call tools when needed!\n")
        
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
                
                print("\n🤔 Processing...")
                response = await self.chat_with_ollama(user_input)
                print(f"\n🤖 {self.current_model}:")
                print(response)
                print()
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"\n❌ Error: {e}\n")
    
    def cleanup(self):
        """Cleanup resources"""
        pass  # No cleanup needed for direct service calls

async def main():
    """Main function"""
    client = MCPClient()
    
    try:
        await client.chat_loop()
    finally:
        client.cleanup()

if __name__ == "__main__":
    asyncio.run(main())