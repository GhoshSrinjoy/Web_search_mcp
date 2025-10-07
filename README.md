*“I asked my AI to stop doomscrolling. It said it was conducting a ‘multi-source research query.’”*  

# 🌐 Web Search MCP  

A comprehensive MCP (Model Context Protocol) implementation that equips AI models with web search, content extraction, vector storage, and RAG (Retrieval Augmented Generation) capabilities.  
This system allows AI to autonomously search the internet, extract useful content, store it, and perform intelligent retrieval , basically giving your model a memory and a browser that doesn’t get distracted by cat videos. 🧠  

🔗 **Repo:** https://github.com/GhoshSrinjoy/Web_search_mcp  

---

## Executive Summary  

**Web Search MCP** connects AI models to the open web safely and efficiently.  
It uses Dockerized services for searching, scraping, embedding, and semantic retrieval , all orchestrated through the MCP framework.  

**Core idea:** Give your model the ability to *search, think, and remember.*  
No external APIs. No tracking. Just clean, local, privacy-focused research automation.  

---

## Business Problem  

LLMs are powerful, but blind , they can’t browse, fetch fresh data, or verify facts.  
External APIs are expensive, rate-limited, and often privacy-invasive.  

**This project solves that.** It creates a self-contained ecosystem where your model can:  
- 🔍 Search the web via **SearXNG** (privacy-focused search)  
- 🧾 Extract clean text and markdown  
- 📦 Store embeddings in **ChromaDB** for long-term recall  
- 🧠 Perform **Retrieval Augmented Generation (RAG)** seamlessly  
- ⚙️ Use modular MCP servers for any combination of tools  

This makes it perfect for research assistants, autonomous agents, or local AI setups that need internet intelligence without internet dependency.  

---

## Methodology  

**Architecture Overview**  
Each service runs in its own Docker container, connected via Redis for caching and ChromaDB for semantic search:  
- **SearXNG** → web search engine (privacy-first)  
- **Content Extractor** → scrapes and cleans webpage content  
- **ChromaDB** → vector database for embeddings  
- **Redis** → cache layer for speed and session memory  
- **MCP Servers** → interface between LLM and these tools  

**Architecture Benefits**  
- 🧩 **Modular:** Each service can scale independently  
- 🐳 **Containerized:** Consistent, reproducible environment  
- 🔒 **Private:** Anonymous web queries through SearXNG  
- ⚡ **Performant:** Redis + ChromaDB for fast lookup  
- 🧠 **Comprehensive:** Ready for full RAG workflows  

## Setup

### Prerequisites
- Docker & Docker Compose installed
- Ollama running locally with qwen3 models (`ollama serve`)

### 1. Clone Repository
```bash
git clone <repository-url>
cd websearch_mcp
```

### 2. Create Environment File
Create a `.env` file with:
```bash
# Security Configuration  
SEARXNG_SECRET=your_32_char_secret_here

# Redis Configuration
REDIS_URL=redis://redis:6379/0
```

Generate a SearXNG secret:
```bash
openssl rand -hex 32
```

### 3. Usage Options

#### Option A: Interactive Mode (Windows)
```bash
START_MCP_INTERACTIVE.BAT
```

This automatically:
1. Builds all Docker containers
2. Starts all required services
3. Launches interactive chat interface

#### Option B: Manual Docker Setup (Linux/Mac/Windows)
1. **Build containers**:
```bash
docker-compose build
```

2. **Start services**:
```bash
docker-compose up -d redis searxng extractor
sleep 15  # Wait for services to initialize
docker-compose up -d vectorstore
sleep 10  # Wait for vectorstore
```

3. **Run interactive client**:
```bash
docker-compose run --rm mcp-client
```

#### Option C: Claude Desktop Integration
1. **Start services**:
```bash
docker-compose up -d
```

2. **Configure Claude Desktop**:
```bash
copy claude_desktop_config.json %APPDATA%\Claude\claude_desktop_config.json
```

3. **Restart Claude Desktop**

Claude will now have access to all web search and RAG tools.

## Available Tools

- **web_search** - Search the internet using SearXNG
- **extract_content** - Extract clean content from any URL
- **rag_search** - Semantic search through stored knowledge
- **store_content** - Store content in vector database
- **knowledge_stats** - View knowledge base statistics  
- **research_query** - Multi-source research with automatic storage
- **smart_answer** - Enhanced answers using both stored and web data

## Key Files

- **`START_MCP_INTERACTIVE.BAT`** - Main entry point for interactive usage
- **`docker-compose.yml`** - Service orchestration configuration
- **`src/client/mcp_multi_client.py`** - Interactive chat client
- **`src/mcp/*.py`** - MCP server implementations
- **`services/`** - Docker service definitions
- **`mcp_servers_config.json`** - LLM model configuration

## Configuration

### LLM Configuration (mcp_servers_config.json)

The complete `mcp_servers_config.json` structure:
```json
{
  "mcpServers": {
    "websearch": {
      "command": "python",
      "args": ["src/mcp/websearch_server.py"],
      "env": {
        "WEBSEARCH_URL": "http://extractor:8055"
      }
    },
    "extractor": {
      "command": "python", 
      "args": ["src/mcp/extractor_server.py"],
      "env": {
        "WEBSEARCH_URL": "http://extractor:8055"
      }
    },
    "storage": {
      "command": "python",
      "args": ["src/mcp/storage_server.py"],
      "env": {
        "CHROMA_PATH": "./data/chroma_db"
      }
    },
    "rag": {
      "command": "python",
      "args": ["src/mcp/rag_server.py"],
      "env": {
        "CHROMA_PATH": "./data/chroma_db"
      }
    },
    "research": {
      "command": "python",
      "args": ["src/mcp/research_server.py"], 
      "env": {
        "WEBSEARCH_URL": "http://extractor:8055",
        "CHROMA_PATH": "./data/chroma_db"
      }
    }
  },
  "llm": {
    "provider": "ollama",
    "model": "qwen3:8b",
    "baseUrl": "http://localhost:11434",
    "temperature": 0.1,
    "maxTokens": 4000
  },
  "availableModels": [
    "qwen3:0.6b",
    "qwen3:8b"
  ]
}
```

## Troubleshooting

**No LLM response**: Ensure `ollama serve` is running and models are pulled
**Service startup issues**: Check `docker-compose logs -f [service-name]`
**Claude Desktop integration**: Restart Claude Desktop after config changes
**Port conflicts**: Ensure ports 8080, 8055 are available

---
## Skills  

Built with: Python, Docker, Redis, SearXNG, ChromaDB, MCP protocol, and Ollama LLM integration.  
Shows real-world system design , distributed architecture, service orchestration, caching, and retrieval pipelines.  

---

## Results & Business Recommendation  

**What it delivers**  
- 🧠 Self-contained, local AI web search and retrieval engine  
- 🔒 Private by design (no external API calls)  
- ⚡ Fast content extraction and vector storage  
- 🧩 Fully modular , swap, scale, or extend services easily  

**Ideal for:**  
- Researchers building autonomous agents  
- AI developers building RAG pipelines  
- Teams who want local, private alternatives to API-driven search  

**Recommendation**  
Use **Docker Compose** for reliable deployments.  
Run **Ollama** with Qwen3 models for local LLMs.  
If integrating with Claude Desktop, keep Redis + Extractor always active.  

---

## Next Steps  

🧩 Add automatic summarization for extracted content.  
📚 Add long-term memory management in ChromaDB.  
🧠 Integrate LLM-based ranking for better search results.  
🌐 Add multi-language extraction and translation support.  
📦 Publish pre-built Docker images.  
⚡ Add GPU acceleration for embedding generation.  
🧰 Add unit tests for all MCP endpoints.  
