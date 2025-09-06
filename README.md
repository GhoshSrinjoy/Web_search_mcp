# WebSearch MCP

A Model Context Protocol (MCP) server that provides web search, content extraction, and RAG capabilities for AI assistants. **Docker-only** implementation with full containerized services.

## What is MCP?

Model Context Protocol (MCP) is an open standard that connects AI assistants to data sources and tools. Think of it as a standardized way for LLMs to access external services like web search, databases, and APIs.

## Quick Start

### Interactive Chat with Ollama (Docker)

1. **Install Ollama** and pull Qwen models:
```bash
ollama pull qwen3:8b
ollama pull qwen3:0.6b
```

2. **Start the Docker pipeline**:
```bash
START_MCP_INTERACTIVE.BAT
```

This automatically:
- Builds and starts all Docker containers
- Launches Redis, SearXNG, content extractor, and vector database
- Starts interactive chat where LLM can autonomously call MCP tools

### Use with Claude Desktop

1. **Start the Docker services first**:
```bash
docker-compose up -d redis searxng extractor vectorstore
```

2. **Add to your Claude Desktop config** (`%APPDATA%\Claude\claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "websearch": {
      "command": "python",
      "args": ["D:/src/websearch_mcp/src/mcp/websearch_server.py"],
      "env": {
        "WEBSEARCH_URL": "http://localhost:8055"
      }
    },
    "extractor": {
      "command": "python",
      "args": ["D:/src/websearch_mcp/src/mcp/extractor_server.py"],
      "env": {
        "WEBSEARCH_URL": "http://localhost:8055"
      }
    },
    "storage": {
      "command": "python",
      "args": ["D:/src/websearch_mcp/src/mcp/storage_server.py"],
      "env": {
        "CHROMA_PATH": "D:/src/websearch_mcp/data/chroma_db"
      }
    },
    "rag": {
      "command": "python",
      "args": ["D:/src/websearch_mcp/src/mcp/rag_server.py"],
      "env": {
        "CHROMA_PATH": "D:/src/websearch_mcp/data/chroma_db"
      }
    },
    "research": {
      "command": "python",
      "args": ["D:/src/websearch_mcp/src/mcp/research_server.py"],
      "env": {
        "WEBSEARCH_URL": "http://localhost:8055",
        "CHROMA_PATH": "D:/src/websearch_mcp/data/chroma_db"
      }
    }
  }
}
```

3. **Restart Claude Desktop** - You'll see the MCP tools available in the interface

## Available MCP Tools

The system exposes these tools that LLMs can call autonomously:

- **web_search** - Search the internet for current information
- **extract_content** - Extract full text from web URLs  
- **rag_search** - Search stored knowledge base
- **store_content** - Store content in knowledge base
- **knowledge_stats** - Get knowledge base statistics
- **research_query** - Comprehensive research with auto storage and multi-source analysis
- **smart_answer** - Intelligent answers using stored + web data

## Scripts to Run

### Main Script
- **`START_MCP_INTERACTIVE.BAT`** - Complete Docker pipeline with interactive chat

### Individual Docker Services
```bash
# Start all services
docker-compose up -d

# Start specific services
docker-compose up -d redis searxng extractor
docker-compose up -d vectorstore

# View logs
docker-compose logs -f

# Stop everything  
docker-compose down
```

## How It Works

1. **MCP Servers** - Multiple specialized MCP servers for different functions
2. **Docker Services** - Web search (SearXNG), content extraction, vector storage (ChromaDB)
3. **LLM Integration** - LLM decides when to call tools autonomously via tool calling
4. **Caching** - Redis caches search results and extractions for performance
5. **RAG Pipeline** - Automatic content storage and retrieval for enhanced answers

## Architecture

```
┌─────────────┐    ┌─────────────────┐    ┌─────────────────┐
│    LLM      │────│ MCP Multi-Client │────│ Multiple MCP    │
│ (Ollama/    │    │                 │    │ Servers         │
│  Claude)    │    └─────────────────┘    └─────────────────┘
└─────────────┘                                    │
                                                   ├── websearch_server
                                                   ├── extractor_server  
                                                   ├── storage_server
                                                   ├── rag_server
                                                   └── research_server
                                                           │
                           ┌────────────────────────────────┼────────────────────┐
                           │                                │                    │
                    ┌──────▼──────┐              ┌─────────▼────────┐    ┌──────▼──────┐
                    │   SearXNG   │              │   ChromaDB       │    │    Redis    │
                    │  (Search)   │              │  (Vectors)       │    │   (Cache)   │
                    └─────────────┘              └──────────────────┘    └─────────────┘
                           │
                    ┌──────▼──────┐
                    │  Extractor  │
                    │  (Content)  │
                    └─────────────┘
```

## Configuration

Main config file: `mcp_servers_config.json`
```json
{
  "llm": {
    "provider": "ollama",
    "model": "qwen3:8b",
    "baseUrl": "http://localhost:11434",
    "temperature": 0.1
  },
  "availableModels": [
    "qwen3:0.6b", 
    "qwen3:8b"
  ]
}
```

## Key Files

- **`START_MCP_INTERACTIVE.BAT`** - Main launcher script
- **`src/client/mcp_multi_client.py`** - Multi-MCP client with tool chaining
- **`src/mcp/`** - All MCP server implementations
- **`docker-compose.yml`** - Container orchestration
- **`mcp_servers_config.json`** - LLM and server configuration

## Troubleshooting

**Empty LLM responses**: 
- Ensure Ollama is running: `ollama serve`
- Verify model is pulled: `ollama list`

**Tool calls not working**: 
- Check container logs: `docker-compose logs`
- Ensure services are healthy: `docker-compose ps`

**Claude integration not working**:
- Restart Claude Desktop after config changes
- Check file paths are absolute in config
- Ensure Docker services are running first

**Network issues**: 
- Verify containers can communicate: `docker network ls`
- Check Ollama is accessible at `http://host.docker.internal:11434`