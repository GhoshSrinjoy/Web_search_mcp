# WebSearch MCP with Ollama - Universal Setup

Universal configuration for using WebSearch MCP with **any Ollama model** that supports tools.

## 🚀 Quick Start (3 Steps)

### 1. Start WebSearch Services
```bash
cd /path/to/websearch_mcp
docker-compose up -d redis searxng extractor
```

### 2. Install Python Dependencies  
```bash
pip install fastmcp httpx redis[hiredis] pydantic
```

### 3. Choose Your Model & Start MCP

#### Option A: Python-based MCP (Recommended)
```bash
# Use the universal config with any model
mcphost -m ollama:gpt-oss:20b --config ollama_universal_mcp.json
mcphost -m ollama:deepseek-r1:7b --config ollama_universal_mcp.json  
mcphost -m ollama:qwen3:8b --config ollama_universal_mcp.json
mcphost -m ollama:llama3.1:8b --config ollama_universal_mcp.json
mcphost -m ollama:llama3.2:3b --config ollama_universal_mcp.json
mcphost -m ollama:mistral:7b --config ollama_universal_mcp.json
```

#### Option B: Docker-based MCP
```bash
# Start WebSearch MCP services first
docker-compose up -d

# Use with any Ollama model
mcphost -m ollama:gpt-oss:20b --config mcp_client_ollama.json
```

## 📋 Supported Models

All Ollama models with tool support work with the same configuration:

### 🔥 **Top Recommended Models**
- **`gpt-oss:20b`** - Best for agentic tasks, native tool calling
- **`deepseek-r1:7b`** - Superior reasoning, complex analysis  
- **`qwen3:8b`** - Balanced performance
- **`llama3.1:8b`** - Reliable, general purpose

### 📚 **Complete Model List**
```
gpt-oss:20b, gpt-oss:120b
deepseek-r1:1.5b, deepseek-r1:7b, deepseek-r1:8b, deepseek-r1:14b, deepseek-r1:32b, deepseek-r1:70b, deepseek-r1:671b
qwen3:0.6b, qwen3:1.7b, qwen3:4b, qwen3:8b, qwen3:14b, qwen3:30b, qwen3:32b, qwen3:235b
llama3.1:8b, llama3.1:70b, llama3.1:405b
llama3.2:1b, llama3.2:3b
mistral:7b
```

## 🛠️ Available WebSearch Tools

All models get access to these 6 tools:

1. **`web_search`** - Multi-engine web search
2. **`fetch_content`** - Extract content from URLs
3. **`batch_fetch`** - Process multiple URLs  
4. **`get_session_info`** - Session statistics
5. **`clear_cache`** - Cache management
6. **`health_check`** - Service status

## 💡 Usage Examples

### Basic Search & Extract
```python
# Search for information
results = web_search("AI developments 2024", max_results=5)

# Extract detailed content  
content = fetch_content(results.results[0].url)
```

### Model-Specific Optimizations

#### For gpt-oss:20b (Agentic Tasks)
```python
web_search("complex research query", max_results=10, time_range="week")
batch_fetch(multiple_urls, max_concurrent=3)
```

#### For deepseek-r1:7b (Deep Analysis)  
```python  
web_search("scientific research topic", max_results=5)
fetch_content(url, use_javascript=True)  # For complex sites
```

#### For qwen3:8b (Balanced Use)
```python
web_search("general query", max_results=7)
fetch_content(url, extract_images=True)
```

## 🔧 Configuration Files

- **`ollama_universal_mcp.json`** - Python-based, works with all models
- **`mcp_client_ollama.json`** - Docker-based, works with all models
- **`claude_desktop_config.json`** - For Claude Desktop integration
- **`mcp_client_docker.json`** - Standalone Docker setup

## ⚡ Performance Tips

### Model Selection by Use Case
- **Research/Analysis**: `deepseek-r1:7b` or `gpt-oss:20b`  
- **General Tasks**: `qwen3:8b` or `llama3.1:8b`
- **Fast Responses**: `llama3.2:3b` or `qwen3:4b`
- **Heavy Workloads**: `gpt-oss:120b` or `deepseek-r1:70b`

### System Resources
- **8GB RAM**: llama3.2:1b, llama3.2:3b, qwen3:0.6b
- **16GB RAM**: gpt-oss:20b, deepseek-r1:7b, qwen3:8b, llama3.1:8b
- **32GB+ RAM**: deepseek-r1:32b, qwen3:14b, llama3.1:70b

## 🎯 Ready to Use!

1. **Pick any model**: `ollama pull gpt-oss:20b`
2. **Start services**: `docker-compose up -d redis searxng extractor`  
3. **Launch MCP**: `mcphost -m ollama:gpt-oss:20b --config ollama_universal_mcp.json`

**All Ollama tool-capable models work with the same configuration!** 🚀