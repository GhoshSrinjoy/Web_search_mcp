#!/usr/bin/env python3
"""
MCP Client that connects Ollama to MCP servers for autonomous tool usage
Supports: gpt-oss:20b, qwen3:0.6b, qwen3:8b
"""

import asyncio
import json
import sys
import subprocess
import httpx
from typing import Dict, List, Any, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp-client")

class MCPClient:
    def __init__(self, config_file: str = "mcp_client_config.json"):
        with open(config_file, 'r') as f:
            self.config = json.load(f)
        
        self.available_models = self.config.get("availableModels", ["gpt-oss:20b"])
        self.current_model = self.config.get("defaultModel", "gpt-oss:20b")
        self.ollama_url = self.config["llm"]["baseUrl"]
        self.tools = []
        self.mcp_process = None
    
    async def start_mcp_server(self):
        """Start the MCP server subprocess"""
        server_config = self.config["mcpServers"]["websearch"]
        cmd = [server_config["command"]] + server_config["args"]
        env = server_config.get("env", {})
        
        logger.info(f"Starting MCP server: {' '.join(cmd)}")
        self.mcp_process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={**env}
        )
        
        # Initialize MCP connection and get tools
        await self.initialize_tools()
    
    async def initialize_tools(self):
        """Get available tools from MCP server"""
        # Send initialize request
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "clientInfo": {
                    "name": "websearch-mcp-client",
                    "version": "1.0.0"
                }
            }
        }
        
        # For now, hardcode the tools since we know what the server provides
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "web_search",
                    "description": "Search the internet for current information about any topic",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query to find information on the web"
                            },
                            "max_results": {
                                "type": "integer",
                                "description": "Maximum number of search results to return (default: 5)"
                            }
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "extract_content",
                    "description": "Extract full text content from a webpage URL",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "url": {
                                "type": "string",
                                "description": "URL to extract content from"
                            }
                        },
                        "required": ["url"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "rag_search",
                    "description": "Search through previously stored knowledge base for relevant information",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query to find information in the knowledge base"
                            },
                            "max_results": {
                                "type": "integer",
                                "description": "Maximum number of results to return (default: 10)"
                            }
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "store_content",
                    "description": "Store extracted content in the knowledge base for future retrieval",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "url": {"type": "string", "description": "Source URL of the content"},
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
                    "name": "knowledge_stats",
                    "description": "Get statistics about the current knowledge base",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            }
        ]
        
        logger.info(f"Initialized {len(self.tools)} tools")
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Call MCP tool via subprocess communication"""
        # This is simplified - in a real implementation you'd use proper MCP protocol
        # For now, we'll simulate tool calls by importing and calling our functions
        try:
            if tool_name == "web_search":
                # Import and use websearch service
                import sys
                import os
                sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))
                from services.websearch import WebSearchService
                websearch = WebSearchService()
                query = arguments.get("query", "")
                max_results = arguments.get("max_results", 5)
                results = await websearch.web_search(query, max_results)
                
                formatted_results = []
                for i, result in enumerate(results.get("results", []), 1):
                    formatted_results.append(
                        f"{i}. **{result.get('title', 'No Title')}**\n"
                        f"   URL: {result.get('url', '')}\n"
                        f"   Description: {result.get('content', 'No description')[:200]}...\n"
                    )
                
                return f"Found {results.get('number_of_results', 0)} search results:\n\n" + "\n".join(formatted_results)
            
            elif tool_name == "extract_content":
                from services.websearch import WebSearchService
                websearch = WebSearchService()
                url = arguments.get("url", "")
                content = await websearch.fetch_content(url)
                
                response = f"**Title:** {content.get('title', 'No Title')}\n"
                response += f"**URL:** {url}\n"
                response += f"**Content Length:** {len(content.get('text', ''))} characters\n\n"
                response += f"**Content:**\n{content.get('text', 'No content extracted')}"
                
                return response
            
            elif tool_name == "rag_search":
                from services.vectorstore import ContentVectorizer
                vectorizer = ContentVectorizer(chroma_path="./data/chroma_db")
                query = arguments.get("query", "")
                max_results = arguments.get("max_results", 10)
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
                        f"{i}. **{source.get('title', 'No Title')}** (Similarity: {score:.3f})\n"
                        f"   URL: {source.get('url', '')}\n"
                        f"   Content: {chunk[:300]}...\n"
                    )
                
                return f"Found {len(rag_result.retrieved_chunks)} relevant chunks:\n\n" + "\n".join(formatted_results)
            
            else:
                return f"Tool '{tool_name}' not implemented yet"
                
        except Exception as e:
            logger.error(f"Tool call failed: {e}")
            return f"Tool execution failed: {str(e)}"
    
    async def chat_with_tools(self, user_input: str) -> str:
        """Send message to Ollama with tool calling capability"""
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                # First, ask the model what tools it wants to use
                system_prompt = f"""You are an AI assistant with access to these tools:

{json.dumps([tool['function'] for tool in self.tools], indent=2)}

When the user asks a question, decide which tools to use and call them. You can chain multiple tools together.

TOOL CALLING FORMAT:
To call a tool, respond with JSON in this exact format:
{{"tool_calls": [{{"tool": "tool_name", "arguments": {{"param": "value"}}}}]}}

After getting tool results, provide a comprehensive answer in the same language as the user's query.

User Query: {user_input}

Decide which tools to call first:"""

                # Get tool calls from LLM
                response = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": self.current_model,
                        "prompt": system_prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.1,
                            "max_tokens": 1000
                        }
                    }
                )
                
                result = response.json()
                llm_response = result.get("response", "")
                
                # Check if LLM wants to call tools
                if "tool_calls" in llm_response:
                    try:
                        # Extract JSON from response
                        import re
                        json_match = re.search(r'\{.*"tool_calls".*\}', llm_response, re.DOTALL)
                        if json_match:
                            tool_request = json.loads(json_match.group())
                            tool_results = []
                            
                            # Execute each tool call
                            for tool_call in tool_request.get("tool_calls", []):
                                tool_name = tool_call.get("tool")
                                arguments = tool_call.get("arguments", {})
                                
                                print(f"🔧 Calling tool: {tool_name}")
                                result = await self.call_tool(tool_name, arguments)
                                tool_results.append(f"Tool: {tool_name}\nResult: {result}")
                            
                            # Send tool results back to LLM for final answer
                            final_prompt = f"""Based on the following tool results, provide a comprehensive answer to the user's query: "{user_input}"

Tool Results:
{chr(10).join(tool_results)}

Provide a well-formatted, comprehensive answer in the same language as the user's query:"""

                            final_response = await client.post(
                                f"{self.ollama_url}/api/generate",
                                json={
                                    "model": self.current_model,
                                    "prompt": final_prompt,
                                    "stream": False,
                                    "options": {
                                        "temperature": 0.3,
                                        "max_tokens": 2000
                                    }
                                }
                            )
                            
                            final_result = final_response.json()
                            return final_result.get("response", "Failed to generate final response")
                    
                    except json.JSONDecodeError:
                        return f"LLM response (no tools called): {llm_response}"
                
                return llm_response
                
        except Exception as e:
            logger.error(f"Chat failed: {e}")
            return f"Chat failed: {str(e)}"
    
    def switch_model(self, model_name: str):
        """Switch to a different model"""
        if model_name in self.available_models:
            self.current_model = model_name
            print(f"✅ Switched to model: {model_name}")
        else:
            print(f"❌ Model {model_name} not available. Available: {', '.join(self.available_models)}")
    
    async def chat_loop(self):
        """Interactive chat loop"""
        print(f"\n🤖 MCP-Enabled Chat with Autonomous Tools")
        print("=" * 50)
        print(f"Current model: {self.current_model}")
        print(f"Available models: {', '.join(self.available_models)}")
        print(f"Available tools: {', '.join([tool['function']['name'] for tool in self.tools])}")
        print("\nCommands:")
        print("  /model <name> - Switch model")
        print("  /exit - Exit chat")
        print("\nThe LLM can autonomously decide when to use tools!\n")
        
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
                
                print("\n🤔 Thinking...")
                response = await self.chat_with_tools(user_input)
                print(f"\n🤖 {self.current_model}:")
                print(response)
                print()
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"\n❌ Error: {e}\n")
    
    def cleanup(self):
        """Clean up MCP process"""
        if self.mcp_process:
            self.mcp_process.terminate()

async def main():
    """Main function"""
    client = MCPClient()
    
    try:
        await client.initialize_tools()
        await client.chat_loop()
    finally:
        client.cleanup()

if __name__ == "__main__":
    asyncio.run(main())