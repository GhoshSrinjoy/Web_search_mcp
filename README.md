# WebSearch MCP RAG - Dockerized AI Assistant

A complete dockerized implementation of Model Context Protocol (MCP) for autonomous web search, content extraction, and Retrieval-Augmented Generation (RAG) using ChromaDB and local LLMs.

## 🏗️ Architecture

This system implements MCP 2025 specification with dynamic tool selection, allowing AI models to autonomously decide which tools to use based on the query context.

```
websearch_mcp/
├── src/
│   ├── client/              # MCP Client for LLM integration  
│   │   ├── mcp_client.py    # Main MCP client with dynamic tool calling
│   │   └── mcp_client_config.json # Client configuration
│   └── mcp/                 # MCP Server exposing RAG tools
│       └── mcp_server.py    # Server with web_search, extract_content, rag_search tools
├── services/
│   ├── extractor/           # Content extraction service (FastAPI)
│   │   ├── app.py           # Trafilatura-based content extraction
│   │   ├── Dockerfile       # Container definition
│   │   └── requirements.txt # Python dependencies
│   ├── vectorstore/         # ChromaDB vector database service
│   │   ├── content_vectorizer.py # Smart chunking & embedding
│   │   ├── Dockerfile       # Container definition  
│   │   └── requirements.txt # Python dependencies
│   └── websearch/           # Web search service wrapper
│       └── websearch_service.py # SearXNG integration
├── data/
│   └── chroma_db/           # Persistent vector database
├── config/
│   └── searxng/
│       └── settings.yml     # SearXNG search engine configuration
├── docker-compose.yml       # Complete service orchestration
├── Dockerfile              # MCP client container
├── START_MCP_RAG.BAT       # Windows launch script
└── requirements.txt        # Main dependencies
```

## 🔧 Services Architecture

### Core Services
1. **Redis** - Caching and session management
2. **SearXNG** - Privacy-focused search engine
3. **Extractor** - Advanced content extraction using Trafilatura
4. **Vectorstore** - ChromaDB with intelligent chunking and embeddings  
5. **MCP Client** - Dynamic tool orchestration with local LLMs

### MCP Tools (Auto-Selected by AI)

#### 🧠 **Intelligent Tools (AI Auto-Selects Based on Query)**
- **`research_query`** - Comprehensive research with parallel searches, smart content processing, and RAG synthesis
- **`smart_answer`** - Intelligent answering: checks knowledge base first, supplements with web search when needed

#### 🔧 **Core Tools (Building Blocks)**  
- **`web_search`** - Search internet for current information (with Redis caching)
- **`extract_content`** - Extract full text from webpages 
- **`rag_search`** - Search stored knowledge base with semantic similarity
- **`store_content`** - Store content in vector database with smart chunking
- **`knowledge_stats`** - View knowledge base statistics and health

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- Ollama running on host machine (port 11434)
- At least 8GB RAM recommended

### 1. Launch the System
```bash
# Windows
START_MCP_RAG.BAT

# Linux/Mac  
docker-compose up --build
```

### 2. Supported Models
The system works with any Ollama model:
- `gpt-oss:20b` (default) 
- `qwen3:0.6b`
- `qwen3:8b`
- `llama3:latest`
- Any other Ollama model

### 3. Intelligent Query Processing

The AI automatically chooses the optimal strategy based on your query:

#### 🔍 **Simple Questions → `smart_answer`**
```
You: "What is Tesla's current stock price?"

🤔 Analyzing query...
📚 Checking knowledge base... (no recent data)
🔍 Getting current web info...
📄 Direct answer with source (content < 2KB)

🤖 Tesla (TSLA) is currently trading at $248.50...
Source: https://finance.yahoo.com/quote/TSLA
```

#### 🧠 **Complex Research → `research_query`**  
```
You: "Research the latest developments in quantum computing and store findings"

🤔 Complex research query detected...
🔧 research_query: parallel searches across multiple sources
🔗 Found 3 sources
📄 Extracting content in parallel...
💾 Stored 2 large articles (>500 chars each)  
📄 Direct summary from 1 small article
📚 RAG synthesis from stored content

🤖 Comprehensive quantum computing report with:
- Current breakthrough summaries
- Stored knowledge synthesis  
- Full source attribution
```

#### 📚 **Knowledge Questions → RAG-First**
```
You: "What do we know about Tesla from our previous research?"

🤔 Knowledge-based query...
📚 High relevance match found (similarity: 0.89)
✅ Answered from knowledge base only

🤖 Based on stored research: Tesla's Q3 2024 results showed...
Sources: 3 previously stored articles
```

## 🧠 Advanced Features

### Dynamic Tool Selection & Content Processing
Based on MCP 2025 specification with intelligent decision making:

#### 🎯 **Query Analysis & Tool Routing:**
- **Simple/Direct questions** → `smart_answer` (RAG-first, web supplement)
- **Complex research** → `research_query` (parallel search + extraction + RAG)
- **Knowledge-only queries** → `rag_search` (pure knowledge base)
- **Specific URL extraction** → `extract_content` + conditional storage

#### 📊 **Content Size Intelligence:**
- **Small content (<2KB)** → Direct consumption and immediate response
- **Medium content (2KB-10KB)** → Store in knowledge base + provide summary  
- **Large content (>10KB)** → Smart chunking + embedding + RAG synthesis
- **Too large (>10MB)** → Truncation with warning

#### ⚡ **Parallel Processing with Redis Coordination:**
- **Multiple URLs** → Concurrent extraction via asyncio.gather()
- **Search caching** → 30-minute TTL to avoid duplicate searches
- **Duplicate prevention** → Content hash checking before storage
- **Load balancing** → Redis-coordinated task distribution

### Intelligent Content Processing
- **Smart Chunking** - Semantic boundary detection
- **Embedding Generation** - Using Ollama's nomic-embed-text
- **Similarity Search** - Cosine similarity with configurable thresholds
- **Source Tracking** - Full provenance and citation management

### Data Persistence
- **ChromaDB** - Persistent vector storage in `./data/chroma_db/`
- **Redis** - Fast caching and session data
- **Docker Volumes** - Automatic data persistence across restarts

## 🔍 Example Workflows

### 1. Research Assistant
```
"Research the company Tesla's recent quarterly results and store the findings"
→ web_search → extract_content → store_content → summarize
```

### 2. Knowledge Synthesis  
```  
"What do we know about climate change impacts from our knowledge base?"
→ rag_search → synthesize from stored content
```

### 3. Fact Verification
```
"Is this claim about AI development accurate: [claim]"
→ rag_search (stored knowledge) → web_search (current info) → compare
```

## 📊 Monitoring & Health

- **Health Checks** - All services have built-in health monitoring
- **Service Dependencies** - Proper startup order and dependency management
- **Logging** - Comprehensive logging across all services
- **Performance** - Optimized for low-latency tool selection

## 🛠️ Configuration

### Environment Variables
```yaml
# MCP Client
OLLAMA_URL: "http://host.docker.internal:11434"
WEBSEARCH_URL: "http://extractor:8055"

# Extractor Service  
MAX_CONTENT_LENGTH: "10485760"  # 10MB
REQUEST_TIMEOUT: "30"

# SearXNG
SEARXNG_SECRET: "change_this_searxng_secret_key"
```

### Customization
- **Search Engines** - Modify `config/searxng/settings.yml`
- **Embedding Models** - Change model in `content_vectorizer.py`
- **Chunking Strategy** - Adjust parameters in smart_chunk()
- **Tool Behavior** - Customize MCP tools in `mcp_server.py`

## 📈 System Requirements

### Minimum
- 4GB RAM
- 2 CPU cores  
- 10GB disk space

### Recommended
- 8GB+ RAM
- 4+ CPU cores
- 50GB+ disk space (for vector storage)
- SSD storage for better performance

## 🔐 Security Notes

- SearXNG runs with minimal privileges
- Content extraction has size limits
- No external API keys required
- All data stored locally

## 🤝 Model Context Protocol (MCP) 2025

This implementation follows MCP 2025 specification:
- **Dynamic Tool Discovery** - Runtime tool registration and updates
- **Resource Management** - Efficient context and resource handling  
- **Standardized Interface** - Universal AI-tool communication
- **Extensible Architecture** - Easy addition of new tools and services

The AI model autonomously decides which tools to use based on the query, making it truly autonomous and context-aware.