# WebSearch MCP

Docker-only MCP implementation with web search, content extraction, and RAG capabilities.

## Quick Start

### Interactive Chat
```bash
START_MCP_INTERACTIVE.BAT
```
Choose Docker Mode. Done.

### Claude Desktop Integration

1. **Start Docker services**:
```bash
docker-compose up -d
```

2. **Copy the config**:
```bash
copy claude_desktop_config.json %APPDATA%\Claude\claude_desktop_config.json
```

3. **Restart Claude Desktop**

The model now has direct access to all web search, extraction, storage, RAG, and research tools.

## Available Tools

- **web_search** - Internet search
- **extract_content** - Extract content from URLs  
- **rag_search** - Search knowledge base
- **store_content** - Store content
- **knowledge_stats** - KB stats
- **research_query** - Multi-source research with auto-storage
- **smart_answer** - Enhanced answers using stored + web data

## Architecture

```
Claude/LLM ──► Docker Container ──► MCP Servers ──► Services
                                      │
                                      ├── SearXNG (Search)
                                      ├── Extractor (Content)
                                      ├── ChromaDB (Vectors)
                                      └── Redis (Cache)
```

## Scripts

- **`START_MCP_INTERACTIVE.BAT`** - Complete Docker pipeline
- **`docker-compose up -d`** - Start all services
- **`docker-compose down`** - Stop everything
- **`docker-compose logs -f`** - View logs

## Configuration

`mcp_servers_config.json`:
```json
{
  "llm": {
    "model": "qwen3:8b",
    "baseUrl": "http://localhost:11434"
  },
  "availableModels": ["qwen3:0.6b", "qwen3:8b"]
}
```

## Requirements

- Docker + Docker Compose
- Ollama with qwen3 models

## Troubleshooting

**No response**: Check `ollama serve` is running
**Tool errors**: `docker-compose logs` 
**Claude integration**: Restart Claude Desktop after config changes