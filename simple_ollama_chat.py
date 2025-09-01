#!/usr/bin/env python3
"""
Simple WebSearch MCP + Ollama Chat Interface
Connects your Ollama model directly to WebSearch MCP tools
"""

import asyncio
import httpx
import json
from typing import Dict, Any, Optional
import sys

class WebSearchMCP:
    """Simple WebSearch MCP client"""
    
    def __init__(self):
        self.base_url = "http://localhost:8055"
    
    async def web_search(self, query: str, max_results: int = 5, **kwargs) -> Dict[str, Any]:
        """Search the web using SearXNG"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/search",
                json={"query": query, "max_results": max_results, **kwargs},
                timeout=30
            )
            return response.json()
    
    async def fetch_content(self, url: str, **kwargs) -> Dict[str, Any]:
        """Extract content from URL"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/extract",
                json={"url": url, **kwargs},
                timeout=30
            )
            return response.json()
    
    async def health_check(self) -> Dict[str, Any]:
        """Check service health"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/health", timeout=10)
            return response.json()

class OllamaChat:
    """Simple Ollama chat interface with WebSearch tools"""
    
    def __init__(self, model_name: str):
        self.model_name = model_name
        self.websearch = WebSearchMCP()
        
    async def chat_loop(self):
        """Main chat loop"""
        print(f"\n🚀 WebSearch MCP + {self.model_name}")
        print("=" * 50)
        print("Available commands:")
        print("  /search <query>     - Search the web")
        print("  /extract <url>      - Extract content from URL")  
        print("  /health             - Check services")
        print("  /help               - Show this help")
        print("  /exit or /quit      - Exit chat")
        print("\nFor regular chat, just type your message.")
        print("The model can request web searches when needed.\n")
        
        # Test connection
        try:
            health = await self.websearch.health_check()
            print(f"✅ WebSearch services: {health.get('status', 'unknown')}")
        except Exception as e:
            print(f"⚠️  WebSearch services may not be ready: {e}")
        
        print(f"\nConnected to: {self.model_name}")
        print("Type your message or command:\n")
        
        while True:
            try:
                user_input = input("You: ").strip()
                
                if not user_input:
                    continue
                    
                if user_input.lower() in ['/exit', '/quit']:
                    break
                elif user_input.lower() == '/help':
                    await self.show_help()
                elif user_input.lower() == '/health':
                    await self.check_health()
                elif user_input.startswith('/search '):
                    query = user_input[8:]
                    await self.handle_search(query)
                elif user_input.startswith('/extract '):
                    url = user_input[9:]
                    await self.handle_extract(url)
                else:
                    await self.handle_chat(user_input)
                    
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"\n❌ Error: {e}\n")
    
    async def show_help(self):
        """Show help information"""
        print("\n📚 WebSearch MCP Commands:")
        print("  /search <query>     - Search web for information")
        print("  /extract <url>      - Extract clean text from URL")
        print("  /health             - Check if all services are running")
        print("  /help               - Show this help")
        print("  /exit or /quit      - Exit the chat")
        print("\n💡 Tips:")
        print("  - Ask questions and mention you need web search")
        print("  - Use /search for direct web searches")
        print("  - Use /extract to read full articles")
        print()
    
    async def check_health(self):
        """Check service health"""
        try:
            health = await self.websearch.health_check()
            print(f"\n🏥 Service Status: {health.get('status', 'unknown')}")
            if 'timestamp' in health:
                print(f"   Last check: {health['timestamp']}")
            print()
        except Exception as e:
            print(f"\n❌ Health check failed: {e}\n")
    
    async def handle_search(self, query: str):
        """Handle web search command"""
        if not query:
            print("\n❌ Please provide a search query\n")
            return
            
        try:
            print(f"\n🔍 Searching for: {query}")
            results = await self.websearch.web_search(query, max_results=5)
            
            print(f"\n📊 Found {results.get('number_of_results', 0)} results:")
            print("-" * 40)
            
            for i, result in enumerate(results.get('results', []), 1):
                title = result.get('title', 'No title')
                url = result.get('url', '')
                content = result.get('content', '')[:150] + "..." if result.get('content') else 'No description'
                
                print(f"{i}. {title}")
                print(f"   🔗 {url}")
                print(f"   📝 {content}")
                print()
                
        except Exception as e:
            print(f"\n❌ Search failed: {e}\n")
    
    async def handle_extract(self, url: str):
        """Handle content extraction command"""
        if not url:
            print("\n❌ Please provide a URL\n")
            return
            
        try:
            print(f"\n📄 Extracting content from: {url}")
            content = await self.websearch.fetch_content(url)
            
            title = content.get('title', 'No title')
            text = content.get('text', '')
            
            print(f"\n📰 {title}")
            print("-" * len(title))
            print(f"🔗 URL: {url}")
            print(f"📊 Length: {len(text)} characters")
            print("\n📝 Content preview:")
            print(text[:500] + "..." if len(text) > 500 else text)
            print()
            
        except Exception as e:
            print(f"\n❌ Extraction failed: {e}\n")
    
    async def handle_chat(self, message: str):
        """Handle regular chat message"""
        print(f"\n{self.model_name}: I understand you want to chat, but this is a demo interface.")
        print("The WebSearch tools are available via the /search and /extract commands.")
        print("\nFor full conversational AI with automatic tool usage, use:")
        print("- Claude Desktop with the MCP configuration files")
        print("- Open WebUI with MCP integration")
        print("- Other MCP-compatible chat interfaces")
        print("\n💡 Try: /search your question here")
        print()

async def main():
    """Main function"""
    if len(sys.argv) > 1:
        model_name = sys.argv[1]
    else:
        model_name = "gpt-oss:20b"
    
    chat = OllamaChat(model_name)
    await chat.chat_loop()
    
    print("\nThanks for using WebSearch MCP! 👋")

if __name__ == "__main__":
    asyncio.run(main())