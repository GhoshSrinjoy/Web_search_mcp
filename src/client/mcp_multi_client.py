"""
MCP Multi-Client that connects to multiple individual MCP servers
Each component runs as its own MCP server
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
logger = logging.getLogger("mcp-multi-client")

class MCPMultiClient:
    def __init__(self, config_file: str = "mcp_servers_config.json"):
        with open(config_file, 'r') as f:
            self.config = json.load(f)
        
        # Auto-detect environment and adjust Ollama URL
        self.ollama_url = self._get_ollama_url()
        self.current_model = self.config["llm"]["model"]
        self.available_models = self.config.get("availableModels", [])
        
        # MCP servers and their processes
        self.mcp_servers = {}
        self.available_tools = []
    
    def _get_ollama_url(self) -> str:
        """Auto-detect environment and return appropriate Ollama URL"""
        base_url = self.config["llm"]["baseUrl"]
        
        # Check if running in Docker container
        if self._is_running_in_docker():
            # Use Docker internal URL
            if "localhost" in base_url:
                return base_url.replace("localhost", "host.docker.internal")
            return base_url
        else:
            # Use localhost for local development
            if "host.docker.internal" in base_url:
                return base_url.replace("host.docker.internal", "localhost")
            return base_url
    
    def _is_running_in_docker(self) -> bool:
        """Detect if running inside a Docker container"""
        try:
            # Check for Docker-specific files/environment
            if os.path.exists('/.dockerenv'):
                return True
            
            # Check for Docker in cgroup info
            if os.path.exists('/proc/self/cgroup'):
                with open('/proc/self/cgroup', 'r') as f:
                    return 'docker' in f.read().lower()
            
            # Check environment variables that Docker sets
            if os.environ.get('DOCKER_CONTAINER'):
                return True
                
            return False
        except:
            return False
        
    async def start_all_mcp_servers(self):
        """Start all configured MCP servers"""
        print("Starting individual MCP servers...")
        print(f"[ENV] Docker mode: {self._is_running_in_docker()}")
        print(f"[ENV] Using Ollama URL: {self.ollama_url}")
        
        for server_name, server_config in self.config["mcpServers"].items():
            print(f"  Starting {server_name}...")
            
            cmd = [server_config["command"]] + server_config["args"]
            env = {**os.environ, **server_config.get("env", {})}
            
            try:
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
                
                # Initialize this MCP server
                await self.initialize_mcp_server(server_name, process)
                print(f"  [OK] {server_name} started")
                
            except Exception as e:
                print(f"  [FAIL] {server_name} failed: {e}")
    
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
                        "name": "mcp-multi-client",
                        "version": "1.0.0"
                    }
                }
            }
            
            process.stdin.write(json.dumps(init_request) + "\n")
            process.stdin.flush()
            
            # Read response
            response_line = process.stdout.readline()
            if not response_line:
                return
                
            init_response = json.loads(response_line)
            if "error" in init_response:
                return
            
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
            if not tools_response_line:
                return
                
            tools_response = json.loads(tools_response_line)
            
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
            
        except Exception as e:
            logger.warning(f"Failed to initialize MCP server {server_name}: {e}")
    
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
            if not response_line:
                return "No response from MCP server"
                
            tool_response = json.loads(response_line)
            print(f"[DEBUG] Tool response: {tool_response}")
            
            if "result" in tool_response:
                content = tool_response["result"]["content"]
                print(f"[DEBUG] Content: {content}")
                if isinstance(content, list) and len(content) > 0:
                    return content[0].get("text", "No content returned")
                return str(content)
            elif "error" in tool_response:
                return f"Tool error: {tool_response['error']['message']}"
            else:
                return "Unknown tool response format"
                
        except Exception as e:
            return f"Tool execution failed: {str(e)}"
    
    async def chat_with_ollama(self, user_input: str) -> str:
        """Chat with Ollama using all available MCP tools"""
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                messages = [{"role": "user", "content": user_input}]
                
                # First call to Ollama with all tools
                response = await client.post(
                    f"{self.ollama_url}/api/chat",
                    json={
                        "model": self.current_model,
                        "messages": messages,
                        "tools": [tool for tool in self.available_tools],
                        "stream": False,
                        "options": {
                            "temperature": self.config["llm"].get("temperature", 0.1)
                        }
                    }
                )
                
                if response.status_code != 200:
                    return f"Ollama error: {response.status_code} - {response.text}"
                
                result = response.json()
                assistant_message = result.get("message", {})
                tool_calls = assistant_message.get("tool_calls", [])
                
                if not tool_calls:
                    return assistant_message.get("content", "No response from model")
                
                # Process tool calls via individual MCP servers
                messages.append(assistant_message)
                
                for tool_call in tool_calls:
                    function = tool_call.get("function", {})
                    tool_name = function.get("name", "")
                    arguments = function.get("arguments", {})
                    
                    print(f"\n[TOOL] Calling MCP tool: {tool_name}")
                    print(f"[ARGS] Arguments: {arguments}")
                    print(f"[SERVER] Via server: {self.get_server_for_tool(tool_name)}")
                    
                    # Call MCP tool
                    tool_result = await self.call_mcp_tool(tool_name, arguments)
                    
                    print(f"[DONE] Tool completed")
                    
                    # Add tool result to messages
                    messages.append({
                        "role": "tool",
                        "content": tool_result,
                        "tool_call_id": tool_call.get("id", "")
                    })
                
                # Second call for final response (with tools for chaining)
                print(f"[DEBUG] Sending {len(messages)} messages to Ollama")
                print(f"[DEBUG] Last message: {messages[-1]['content'][:200]}...")
                
                final_response = await client.post(
                    f"{self.ollama_url}/api/chat",
                    json={
                        "model": self.current_model,
                        "messages": messages,
                        "tools": [tool for tool in self.available_tools],
                        "stream": False,
                        "options": {
                            "temperature": self.config["llm"].get("temperature", 0.3)
                        }
                    }
                )
                
                print(f"[DEBUG] Final response status: {final_response.status_code}")
                
                if final_response.status_code != 200:
                    return f"Final response error: {final_response.status_code}"
                
                final_result = final_response.json()
                final_message = final_result.get("message", {})
                final_tool_calls = final_message.get("tool_calls", [])
                
                # Handle chained tool calls recursively
                if final_tool_calls:
                    messages.append(final_message)
                    
                    for tool_call in final_tool_calls:
                        function = tool_call.get("function", {})
                        tool_name = function.get("name", "")
                        arguments = function.get("arguments", {})
                        
                        print(f"\n[CHAIN] Calling follow-up tool: {tool_name}")
                        print(f"[ARGS] Arguments: {arguments}")
                        
                        tool_result = await self.call_mcp_tool(tool_name, arguments)
                        
                        messages.append({
                            "role": "tool",
                            "content": tool_result,
                            "tool_call_id": tool_call.get("id", "")
                        })
                    
                    # Add explicit instruction for final synthesis
                    messages.append({
                        "role": "user",
                        "content": "Now provide a comprehensive answer based on the information you've gathered."
                    })
                    
                    # Final generation call without tools
                    gen_response = await client.post(
                        f"{self.ollama_url}/api/chat",
                        json={
                            "model": self.current_model,
                            "messages": messages,
                            "stream": False,
                            "options": {
                                "temperature": self.config["llm"].get("temperature", 0.3)
                            }
                        }
                    )
                    
                    if gen_response.status_code == 200:
                        gen_result = gen_response.json()
                        return gen_result.get("message", {}).get("content", "No final response")
                
                return final_message.get("content", "No final response")
                
        except Exception as e:
            return f"Chat error: {str(e)}"
    
    def get_server_for_tool(self, tool_name: str) -> str:
        """Get server name that provides a tool"""
        for tool in self.available_tools:
            if tool["function"]["name"] == tool_name:
                return tool.get("_mcp_server", "unknown")
        return "unknown"
    
    def switch_model(self, model_name: str):
        """Switch Ollama model"""
        if model_name in self.available_models:
            self.current_model = model_name
            print(f"[OK] Switched to model: {model_name}")
        else:
            print(f"[ERROR] Model {model_name} not available. Available: {', '.join(self.available_models)}")
    
    async def chat_loop(self):
        """Interactive chat loop"""
        print(f"\n[MCP] Multi-Client Chat Interface")
        print("=" * 45)
        print(f"Current model: {self.current_model}")
        print(f"Available models: {', '.join(self.available_models)}")
        print(f"Active MCP servers: {', '.join(self.mcp_servers.keys())}")
        print(f"Available tools: {', '.join([tool['function']['name'] for tool in self.available_tools])}")
        print("\nCommands:")
        print("  /model <name> - Switch model")
        print("  /servers - Show server status")
        print("  /exit - Exit chat")
        print("\nEach tool runs on its own MCP server!\n")
        
        while True:
            try:
                user_input = input("You: ").strip()
                
                if user_input.lower() in ['/exit', '/quit']:
                    break
                elif user_input.startswith('/model '):
                    model_name = user_input[7:].strip()
                    self.switch_model(model_name)
                    continue
                elif user_input == '/servers':
                    self.show_server_status()
                    continue
                elif not user_input:
                    continue
                
                print(f"\n[PROCESS] Processing with {self.current_model} and {len(self.mcp_servers)} MCP servers...")
                response = await self.chat_with_ollama(user_input)
                print(f"\n[AI] {self.current_model}:")
                print(response)
                print("\n" + "="*60 + "\n")
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"\n[ERROR] Error: {e}\n")
    
    def show_server_status(self):
        """Show status of all MCP servers"""
        print("\n[STATUS] MCP Server Status:")
        for server_name, server_info in self.mcp_servers.items():
            process = server_info["process"]
            status = "Running" if process.poll() is None else "Stopped"
            print(f"  {server_name}: {status}")
        print()
    
    def cleanup(self):
        """Cleanup all MCP server processes"""
        print("\nShutting down MCP servers...")
        for server_name, server_info in self.mcp_servers.items():
            process = server_info["process"]
            if process and process.poll() is None:
                print(f"  Stopping {server_name}...")
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()

async def main():
    """Main function"""
    client = MCPMultiClient()
    
    try:
        await client.start_all_mcp_servers()
        print(f"\n[START] Started {len(client.mcp_servers)} MCP servers")
        print(f"[TOOLS] Available tools: {len(client.available_tools)}")
        
        if len(client.available_tools) == 0:
            print("[ERROR] No tools available. Check MCP server configurations.")
            return
        
        await asyncio.sleep(2)  # Wait for servers to fully initialize
        await client.chat_loop()
    finally:
        client.cleanup()

if __name__ == "__main__":
    asyncio.run(main())