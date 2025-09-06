#!/usr/bin/env python3
"""
MCP Host - Proper implementation that connects Ollama to MCP servers
Based on standard MCP client patterns like mcp-client-for-ollama
"""

import asyncio
import json
import subprocess
import httpx
from typing import Dict, List, Any, Optional
import logging
import sys
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp-host")

class MCPHost:
    def __init__(self, config_file: str = "mcp_host_config.json"):
        with open(config_file, 'r') as f:
            self.config = json.load(f)
        
        self.llm_config = self.config["llm"]
        self.ollama_url = self.llm_config["baseUrl"]
        self.current_model = self.llm_config["model"]
        self.available_models = self.config.get("availableModels", [])
        
        # MCP servers
        self.mcp_servers = {}
        self.available_tools = []
        
    async def start_mcp_servers(self):
        """Start all configured MCP servers"""
        for server_name, server_config in self.config["mcpServers"].items():
            logger.info(f"Starting MCP server: {server_name}")
            
            cmd = [server_config["command"]] + server_config["args"]
            env = {**os.environ, **server_config.get("env", {})}
            
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                env=env
            )
            
            self.mcp_servers[server_name] = {
                "process": process,
                "config": server_config
            }
            
            # Initialize MCP connection
            await self.initialize_mcp_server(server_name, process)
    
    async def initialize_mcp_server(self, server_name: str, process: subprocess.Popen):
        """Initialize MCP server connection and get available tools"""
        try:
            # Send initialize request
            init_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "clientInfo": {
                        "name": "websearch-mcp-host",
                        "version": "1.0.0"
                    }
                }
            }
            
            process.stdin.write(json.dumps(init_request) + "\n")
            process.stdin.flush()
            
            # Read response
            response_line = process.stdout.readline()
            init_response = json.loads(response_line) if response_line else {}
            
            if "error" in init_response:
                logger.error(f"MCP server {server_name} initialization failed: {init_response['error']}")
                return
            
            logger.info(f"MCP server {server_name} initialized successfully")
            
            # Send initialized notification
            initialized_request = {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {}
            }
            
            process.stdin.write(json.dumps(initialized_request) + "\n")
            process.stdin.flush()
            
            # Get available tools
            tools_request = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {}
            }
            
            process.stdin.write(json.dumps(tools_request) + "\n")
            process.stdin.flush()
            
            tools_response_line = process.stdout.readline()
            tools_response = json.loads(tools_response_line) if tools_response_line else {}
            
            if "result" in tools_response and "tools" in tools_response["result"]:
                server_tools = tools_response["result"]["tools"]
                
                # Convert MCP tools to Ollama function calling format
                for tool in server_tools:
                    ollama_tool = {
                        "type": "function",
                        "function": {
                            "name": tool["name"],
                            "description": tool["description"],
                            "parameters": tool["inputSchema"]
                        }
                    }
                    
                    # Add server info for routing
                    ollama_tool["_mcp_server"] = server_name
                    self.available_tools.append(ollama_tool)
                
                logger.info(f"Added {len(server_tools)} tools from {server_name}")
            else:
                logger.warning(f"No tools found in response from {server_name}: {tools_response}")
                
                # Fallback: Add expected tools manually since MCP server should have them
                fallback_tools = [
                    {
                        "type": "function",
                        "function": {
                            "name": "research_query",
                            "description": "Comprehensive research with parallel searches, content extraction, and storage. Use this for complex company research.",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "query": {"type": "string", "description": "Research query"},
                                    "max_sources": {"type": "integer", "description": "Max sources (default: 3)"},
                                    "store_results": {"type": "boolean", "description": "Store results (default: true)"}
                                },
                                "required": ["query"]
                            }
                        },
                        "_mcp_server": server_name
                    },
                    {
                        "type": "function",
                        "function": {
                            "name": "smart_answer",
                            "description": "BEST for questions like 'Who is the contact for X company?' - Checks knowledge base first, then web search",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "question": {"type": "string", "description": "Question to answer"},
                                    "prefer_stored": {"type": "boolean", "description": "Prefer stored knowledge (default: true)"}
                                },
                                "required": ["question"]
                            }
                        },
                        "_mcp_server": server_name
                    },
                    {
                        "type": "function",
                        "function": {
                            "name": "web_search",
                            "description": "Search the internet for current information",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "query": {"type": "string", "description": "Search query"},
                                    "max_results": {"type": "integer", "description": "Max results (default: 5)"}
                                },
                                "required": ["query"]
                            }
                        },
                        "_mcp_server": server_name
                    }
                ]
                
                self.available_tools.extend(fallback_tools)
                logger.info(f"Added {len(fallback_tools)} fallback tools for {server_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize MCP server {server_name}: {e}")
            logger.error(f"Exception details: {type(e).__name__}: {e}")
            
            # Even if initialization fails, add basic tools so user can test
            fallback_tools = [
                {
                    "type": "function",
                    "function": {
                        "name": "research_query",
                        "description": "Comprehensive research - searches, extracts, and stores data automatically. Shows progress.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string", "description": "Research query"},
                                "max_sources": {"type": "integer", "description": "Max sources (default: 3)"}
                            },
                            "required": ["query"]
                        }
                    },
                    "_mcp_server": server_name
                }
            ]
            self.available_tools.extend(fallback_tools)
            logger.info(f"Added fallback tools due to initialization failure")
    
    async def call_mcp_tool(self, tool_name: str, arguments: Dict) -> str:
        """Call MCP tool via the appropriate server"""
        # Find which server provides this tool
        target_server = None
        for tool in self.available_tools:
            if tool["function"]["name"] == tool_name:
                target_server = tool.get("_mcp_server")
                break
        
        if not target_server or target_server not in self.mcp_servers:
            return f"Tool {tool_name} not found or server not available"
        
        try:
            process = self.mcp_servers[target_server]["process"]
            
            # Send tool call request
            tool_request = {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments
                }
            }
            
            process.stdin.write(json.dumps(tool_request) + "\n")
            process.stdin.flush()
            
            # Read response
            response_line = process.stdout.readline()
            tool_response = json.loads(response_line) if response_line else {}
            
            if "result" in tool_response:
                content = tool_response["result"]["content"]
                if isinstance(content, list) and len(content) > 0:
                    result_text = content[0].get("text", "No content returned")
                    
                    # Add progress indicators for specific tools
                    if tool_name == "research_query" and "Research Results" in result_text:
                        # Extract summary info
                        lines = result_text.split('\n')
                        summary_lines = [line for line in lines if '•' in line and ('Found' in line or 'Extracted' in line or 'Stored' in line)]
                        if summary_lines:
                            print("   ✅ Progress:", ' | '.join(summary_lines))
                    
                    return result_text
                return str(content)
            elif "error" in tool_response:
                error_msg = tool_response['error']['message']
                print(f"   ❌ Tool error: {error_msg}")
                return f"Tool error: {error_msg}"
            else:
                print(f"   ⚠️ Unexpected response format: {tool_response}")
                return "Unknown tool response format"
                
        except Exception as e:
            logger.error(f"MCP tool call failed: {e}")
            return f"Tool execution failed: {str(e)}"
    
    async def chat_with_ollama(self, user_input: str) -> str:
        """Chat with Ollama using MCP tools"""
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                messages = [{"role": "user", "content": user_input}]
                
                # First call to Ollama with MCP tools
                response = await client.post(
                    f"{self.ollama_url}/api/chat",
                    json={
                        "model": self.current_model,
                        "messages": messages,
                        "tools": [tool for tool in self.available_tools],
                        "stream": False,
                        "options": {
                            "temperature": self.llm_config.get("temperature", 0.1)
                        }
                    }
                )
                
                if response.status_code != 200:
                    return f"Ollama error: {response.status_code} - {response.text}"
                
                result = response.json()
                assistant_message = result.get("message", {})
                
                # Check for tool calls
                tool_calls = assistant_message.get("tool_calls", [])
                
                if not tool_calls:
                    return assistant_message.get("content", "No response from model")
                
                # Process tool calls via MCP
                messages.append(assistant_message)
                
                for tool_call in tool_calls:
                    function = tool_call.get("function", {})
                    tool_name = function.get("name", "")
                    arguments = function.get("arguments", {})
                    
                    print(f"🔧 Calling MCP tool: {tool_name} with args: {arguments}")
                    
                    # Show expected progress for research tools
                    if tool_name == "research_query":
                        print("   📊 Expected: Search → Extract → Store → Analyze")
                    elif tool_name == "smart_answer":
                        print("   💡 Expected: Check KB → Web Search → Extract → Answer")
                    
                    # Call MCP tool
                    tool_result = await self.call_mcp_tool(tool_name, arguments)
                    
                    # Add tool result to messages
                    messages.append({
                        "role": "tool",
                        "content": tool_result,
                        "tool_call_id": tool_call.get("id", "")
                    })
                
                # Second call for final response
                final_response = await client.post(
                    f"{self.ollama_url}/api/chat",
                    json={
                        "model": self.current_model,
                        "messages": messages,
                        "stream": False,
                        "options": {
                            "temperature": self.llm_config.get("temperature", 0.3)
                        }
                    }
                )
                
                if final_response.status_code != 200:
                    return f"Final response error: {final_response.status_code}"
                
                final_result = final_response.json()
                final_content = final_result.get("message", {}).get("content", "")
                
                if not final_content.strip():
                    # Return tool results if no final response
                    tool_summaries = []
                    for msg in messages:
                        if msg.get("role") == "tool":
                            content = msg.get("content", "")[:300]
                            tool_summaries.append(f"Tool result: {content}...")
                    return "Results from MCP tools:\n" + "\n".join(tool_summaries)
                
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
        print(f"\n🏠 MCP Host Chat Interface")
        print("=" * 35)
        print(f"Current model: {self.current_model}")
        print(f"Available models: {', '.join(self.available_models)}")
        print(f"MCP tools: {', '.join([tool['function']['name'] for tool in self.available_tools])}")
        print("\nCommands:")
        print("  /model <name> - Switch model")
        print("  /exit - Exit chat")
        print("\nMCP servers provide tools automatically!\n")
        
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
                
                print("\n🤔 Processing with MCP tools...")
                response = await self.chat_with_ollama(user_input)
                print(f"\n🏠 {self.current_model}:")
                print(response)
                print()
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"\n❌ Error: {e}\n")
    
    def cleanup(self):
        """Cleanup MCP server processes"""
        for server_name, server_info in self.mcp_servers.items():
            process = server_info["process"]
            if process:
                logger.info(f"Terminating MCP server: {server_name}")
                process.terminate()
                process.wait()

async def main():
    """Main function"""
    host = MCPHost()
    
    try:
        await host.start_mcp_servers()
        await asyncio.sleep(2)  # Wait for servers to initialize
        await host.chat_loop()
    finally:
        host.cleanup()

if __name__ == "__main__":
    asyncio.run(main())