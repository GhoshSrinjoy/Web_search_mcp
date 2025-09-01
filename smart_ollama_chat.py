"""
Smart WebSearch MCP + Ollama Chat Interface
Automatically chains search and extract operations like Claude/GPT
"""

import asyncio
import httpx
import json
import re
from typing import Dict, Any, Optional, List
import sys

class SmartWebSearchMCP:
    """Smart WebSearch MCP client with automatic tool chaining"""
    
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

class SmartOllamaChat:
    """Smart Ollama chat interface with automatic tool usage"""
    
    def __init__(self, model_name: str):
        self.model_name = model_name
        self.websearch = SmartWebSearchMCP()
        
    def detect_intent(self, user_input: str) -> Dict[str, Any]:
        """Detect what the user wants to do - search, extract, or both"""
        user_lower = user_input.lower()
        
        # Check for explicit commands first
        if user_input.startswith('/'):
            if user_input.startswith('/search '):
                return {"action": "search", "query": user_input[8:]}
            elif user_input.startswith('/extract '):
                return {"action": "extract", "url": user_input[9:]}
            elif user_input.startswith('/health'):
                return {"action": "health"}
            elif user_input.startswith('/help'):
                return {"action": "help"}
            elif user_input.lower() in ['/exit', '/quit']:
                return {"action": "exit"}
        
        # Smart intent detection for natural language
        search_keywords = ['search', 'find', 'look for', 'what is', 'tell me about', 'recent', 'latest', 'current', 'projects', 'research', 'information about']
        extract_keywords = ['full content', 'extract', 'get content', 'read article', 'full article', 'complete text']
        
        # Check if URL is mentioned
        url_pattern = r'https?://[^\s]+'
        urls = re.findall(url_pattern, user_input)
        
        has_search_intent = any(keyword in user_lower for keyword in search_keywords)
        has_extract_intent = any(keyword in user_lower for keyword in extract_keywords)
        has_urls = len(urls) > 0
        
        # Determine action based on intent
        if has_urls and (has_extract_intent or 'extract' in user_lower):
            return {"action": "extract", "url": urls[0]}
        elif has_search_intent or any(keyword in user_lower for keyword in ['faps', 'research', 'projects', 'recent', 'latest']):
            # Remove any URLs from search query
            query = re.sub(r'https?://[^\s]+', '', user_input).strip()
            return {"action": "search", "query": query}
        elif has_urls:
            return {"action": "extract", "url": urls[0]}
        
        # Default to search for questions or requests for information
        if '?' in user_input or any(word in user_lower for word in ['what', 'how', 'when', 'where', 'why', 'tell me']):
            return {"action": "search", "query": user_input}
        
        return {"action": "chat", "message": user_input}
    
    async def auto_extract_top_results(self, search_results: Dict[str, Any], max_extracts: int = 2) -> List[Dict[str, Any]]:
        """Automatically extract content from top search results"""
        results = search_results.get('results', [])
        extracted_content = []
        
        print(f"\n🤖 Auto-extracting content from top {min(max_extracts, len(results))} results...")
        
        for i, result in enumerate(results[:max_extracts]):
            url = result.get('url', '')
            title = result.get('title', 'No title')
            
            try:
                print(f"   📄 Extracting from: {title}")
                content = await self.websearch.fetch_content(url)
                content['source_title'] = title
                content['source_url'] = url
                extracted_content.append(content)
            except Exception as e:
                print(f"   ❌ Failed to extract from {title}: {e}")
        
        return extracted_content
    
    async def chat_loop(self):
        """Main smart chat loop"""
        print(f"\n🤖 Smart WebSearch MCP + {self.model_name}")
        print("=" * 55)
        print("🧠 INTELLIGENT MODE: I can automatically:")
        print("   • Search when you ask questions")
        print("   • Extract content from URLs you mention") 
        print("   • Chain search + extract for comprehensive answers")
        print()
        print("💬 Just talk naturally! Examples:")
        print("   'Tell me about recent FAPS projects'")
        print("   'What are the latest AI developments?'")
        print("   'Extract content from https://example.com'")
        print()
        print("⚡ Manual commands still work:")
        print("   /search <query>  /extract <url>  /health  /help  /exit")
        print()
        
        # Test connection
        try:
            health = await self.websearch.health_check()
            print(f"✅ WebSearch services: {health.get('status', 'unknown')}")
        except Exception as e:
            print(f"⚠️  WebSearch services may not be ready: {e}")
        
        print(f"\nConnected to: {self.model_name}")
        print("Ask me anything or give me a task!\n")
        
        while True:
            try:
                user_input = input("You: ").strip()
                
                if not user_input:
                    continue
                
                # Detect what the user wants to do
                intent = self.detect_intent(user_input)
                action = intent.get('action')
                
                if action == 'exit':
                    break
                elif action == 'help':
                    await self.show_help()
                elif action == 'health':
                    await self.check_health()
                elif action == 'search':
                    query = intent.get('query', '')
                    await self.smart_search(query, auto_extract=True)
                elif action == 'extract':
                    url = intent.get('url', '')
                    await self.handle_extract(url)
                else:
                    await self.handle_smart_chat(user_input)
                    
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"\n❌ Error: {e}\n")
    
    async def smart_search(self, query: str, auto_extract: bool = False):
        """Smart search with optional auto-extraction"""
        if not query:
            print("\n❌ Please provide a search query\n")
            return
            
        try:
            print(f"\n🔍 Searching for: {query}")
            results = await self.websearch.web_search(query, max_results=5)
            
            print(f"\n📊 Found {results.get('number_of_results', 0)} results:")
            print("-" * 50)
            
            for i, result in enumerate(results.get('results', []), 1):
                title = result.get('title', 'No title')
                url = result.get('url', '')
                content = result.get('content', '')[:150] + "..." if result.get('content') else 'No description'
                
                print(f"{i}. {title}")
                print(f"   🔗 {url}")
                print(f"   📝 {content}")
                print()
            
            # Auto-extract if requested
            if auto_extract and results.get('results'):
                extracted = await self.auto_extract_top_results(results, max_extracts=2)
                
                if extracted:
                    print("\n📋 SUMMARY FROM TOP RESULTS:")
                    print("=" * 40)
                    for i, content in enumerate(extracted, 1):
                        title = content.get('source_title', 'Unknown')
                        text = content.get('text', '')
                        
                        print(f"\n{i}. {title}")
                        print("-" * len(title))
                        # Show first 500 characters of each extracted content
                        preview = text[:500] + "..." if len(text) > 500 else text
                        print(preview)
                        print()
                
        except Exception as e:
            print(f"\n❌ Search failed: {e}\n")
    
    async def handle_extract(self, url: str):
        """Handle content extraction"""
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
            print("\n📝 Full content:")
            print("=" * 50)
            print(text)
            print("=" * 50)
            print()
            
        except Exception as e:
            print(f"\n❌ Extraction failed: {e}\n")
    
    async def handle_smart_chat(self, message: str):
        """Handle general chat with smart responses"""
        print(f"\n🤖 {self.model_name}: I understand you want to chat about:")
        print(f"   '{message}'")
        print("\n💡 I can help you by:")
        print("   • Searching for current information")
        print("   • Extracting content from specific sources")
        print("   • Providing comprehensive research")
        print("\nTry rephrasing as a question or search request!")
        print("Example: 'Tell me about [your topic]' or 'Find recent [your topic]'")
        print()
    
    async def show_help(self):
        """Show help information"""
        print("\n🧠 Smart WebSearch MCP - Natural Language Interface")
        print("=" * 55)
        print("\n💬 NATURAL LANGUAGE (Recommended):")
        print("   'Tell me about FAPS recent projects'")
        print("   'What are the latest AI developments?'")
        print("   'Find information about quantum computing'")
        print("   'Search for Python 3.13 features and extract details'")
        print("\n⚡ MANUAL COMMANDS:")
        print("   /search <query>     - Search web for information")
        print("   /extract <url>      - Extract content from URL")
        print("   /health             - Check services")
        print("   /help               - Show this help")
        print("   /exit or /quit      - Exit chat")
        print("\n✨ SMART FEATURES:")
        print("   • Automatic tool selection based on your request")
        print("   • Auto-extraction from top search results")
        print("   • Natural language understanding")
        print("   • Context-aware responses")
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

async def main():
    """Main function"""
    if len(sys.argv) > 1:
        model_name = sys.argv[1]
    else:
        model_name = "gpt-oss:20b"
    
    chat = SmartOllamaChat(model_name)
    await chat.chat_loop()
    
    print("\nThanks for using Smart WebSearch MCP! 🤖👋")

if __name__ == "__main__":
    asyncio.run(main())