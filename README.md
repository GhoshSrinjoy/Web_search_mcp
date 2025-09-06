# WebSearch MCP

A Model Context Protocol (MCP) server that provides web search, content extraction, and RAG capabilities for AI assistants.

## What is MCP?

Model Context Protocol (MCP) is an open standard that connects AI assistants to data sources and tools. Think of it as a standardized way for LLMs to access external services like web search, databases, and APIs.

## Quick Start

### Option 1: Interactive Chat with Ollama

1. **Install Ollama** and pull a model:
```bash
ollama pull gpt-oss:20b
```

2. **Run the interactive client**:
```bash
START_MCP_INTERACTIVE.BAT
```

This starts:
- All required services (Redis, SearXNG, Extractor, Vectorstore)  
- An interactive chat where the LLM can autonomously call MCP tools

### Option 2: Use with Claude Desktop

Add to your Claude Desktop config:
```json
{
  "mcpServers": {
    "websearch": {
      "command": "python",
      "args": ["D:/src/websearch_mcp/src/mcp/mcp_server.py"],
      "env": {
        "WEBSEARCH_URL": "http://localhost:8055"
      }
    }
  }
}
```

Then start services: `docker-compose up -d`

## Available MCP Tools

The server exposes these tools that LLMs can call autonomously:

- **web_search** - Search the internet for current information
- **extract_content** - Extract full text from web URLs  
- **rag_search** - Search stored knowledge base
- **store_content** - Store content in knowledge base
- **knowledge_stats** - Get knowledge base statistics
- **research_query** - Comprehensive research with multiple sources
- **smart_answer** - Intelligent answers using stored + web data

## How It Works

1. **MCP Server** (`src/mcp/mcp_server.py`) - Exposes tools via MCP protocol
2. **Services** - Web search (SearXNG), content extraction, vector storage
3. **LLM Integration** - LLM decides when to call tools autonomously
4. **Caching** - Redis caches search results for performance

## Architecture

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│    LLM      │────│ MCP Client  │────│ MCP Server  │
│  (Ollama/   │    │             │    │             │
│   Claude)   │    └─────────────┘    └─────────────┘
└─────────────┘                              │
                                             ├── SearXNG (Search)
                                             ├── Extractor (Content)
                                             ├── ChromaDB (Vectors)  
                                             └── Redis (Cache)
```

## Development

### Local Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Start services
docker-compose up -d redis searxng extractor vectorstore

# Run MCP server directly
python src/mcp/mcp_server.py
```

### Testing MCP Tools
```bash
# Test web search
echo '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"web_search","arguments":{"query":"python MCP tutorial"}}}' | python src/mcp/mcp_server.py
```

## Configuration

Edit `mcp_client_config.json`:
```json
{
  "mcpServers": {
    "websearch": {
      "command": "python", 
      "args": ["/app/src/mcp/mcp_server.py"]
    }
  },
  "defaultModel": "gpt-oss:20b",
  "llm": {
    "baseUrl": "http://host.docker.internal:11434"
  }
}
```

## Files

- `START_MCP_INTERACTIVE.BAT` - Interactive chat with tool calling
- `src/mcp/mcp_server.py` - MCP server implementation
- `src/client/mcp_client.py` - Client that connects Ollama to MCP server
- `docker-compose.yml` - All service definitions

## Troubleshooting

**Empty LLM responses**: Ensure Ollama is running and accessible at `http://host.docker.internal:11434`

**Tool calls not working**: Check that MCP server starts without errors and tools are properly registered

**Network issues**: Verify all containers can communicate - check `docker-compose logs`