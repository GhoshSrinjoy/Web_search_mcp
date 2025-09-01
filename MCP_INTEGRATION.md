# WebSearch MCP - Integration Guide

Complete guide for integrating WebSearch MCP with Claude Desktop, Ollama, and other LLM clients.

## 🛠️ Available MCP Tools

The WebSearch MCP server provides 6 powerful tools:

### 1. **web_search** - Multi-Engine Web Search
- **Purpose**: Search the web using SearXNG metasearch engine
- **Parameters**:
  - `query` (required): Search query string
  - `max_results` (default: 10): Number of results to return
  - `categories` (default: "general"): general, images, videos, news, files, science
  - `time_range` (optional): day, week, month, year
  - `language` (default: "en"): Language code 
  - `safe_search` (default: 1): 0=off, 1=moderate, 2=strict

### 2. **fetch_content** - Intelligent Content Extraction
- **Purpose**: Extract readable content from any URL
- **Parameters**:
  - `url` (required): URL to extract content from
  - `use_javascript` (default: false): Enable JS rendering
  - `extract_images` (default: false): Include image URLs
  - `timeout` (default: 30): Request timeout in seconds

### 3. **batch_fetch** - Concurrent Content Extraction
- **Purpose**: Extract content from multiple URLs efficiently
- **Parameters**:
  - `urls` (required): List of URLs to process
  - `max_concurrent` (default: 5): Concurrent request limit
  - `use_javascript` (default: false): Enable JS rendering

### 4. **get_session_info** - Session Statistics
- **Purpose**: Get current session usage statistics
- **Parameters**: None

### 5. **clear_cache** - Cache Management
- **Purpose**: Clear Redis cache with optional pattern matching
- **Parameters**:
  - `pattern` (optional): Cache key pattern (default: clears all)

### 6. **health_check** - Service Health
- **Purpose**: Check health status of all services
- **Parameters**: None

## 🔧 Integration Methods

### Method 1: Claude Desktop Integration

**Configuration File**: `claude_desktop_config.json`

```json
{
  "mcpServers": {
    "websearch": {
      "command": "docker",
      "args": [
        "compose", 
        "-f", "docker-compose.yml", 
        "exec", "-T", "mcp", 
        "python", "server.py"
      ],
      "cwd": "D:/src/websearch_mcp",
      "env": {
        "SEARXNG_URL": "http://searxng:8080",
        "EXTRACTOR_URL": "http://extractor:8055",
        "REDIS_URL": "redis://redis:6379"
      }
    }
  }
}
```

**Setup Steps**:
1. Start WebSearch MCP: `docker-compose up -d`
2. Copy configuration to Claude Desktop settings
3. Restart Claude Desktop
4. Tools will be available in conversations

### Method 2: Docker Standalone Integration

**Configuration File**: `mcp_client_docker.json`

```json
{
  "mcpServers": {
    "websearch": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "--network", "websearch_mcp_default",
        "websearch_mcp-mcp:latest",
        "python", "server.py"
      ]
    }
  }
}
```

**Prerequisites**:
- Docker services running: `docker-compose up -d`
- Network: `websearch_mcp_default` exists

### Method 3: Python Direct Integration

**Configuration File**: `mcp_client_python.json`

```json
{
  "mcpServers": {
    "websearch": {
      "command": "python",
      "args": ["services/mcp/server.py"],
      "cwd": "D:/src/websearch_mcp",
      "env": {
        "SEARXNG_URL": "http://localhost:8080",
        "EXTRACTOR_URL": "http://localhost:8055",
        "REDIS_URL": "redis://localhost:6379"
      }
    }
  }
}
```

**Prerequisites**:
```bash
# Start supporting services
docker-compose up -d redis searxng extractor

# Install Python dependencies
pip install -r services/mcp/requirements.txt
```

### Method 4: Ollama Integration

**Configuration File**: `mcp_client_ollama.json`

Optimized for local LLM usage with host networking:

```json
{
  "mcpServers": {
    "websearch": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i", 
        "--network", "host",
        "websearch_mcp-mcp:latest"
      ],
      "timeout": 60
    }
  }
}
```

**Ollama Usage Example**:
```bash
# Start WebSearch MCP
docker-compose up -d

# Configure Ollama model with MCP tools
ollama run llama3.2 --mcp-config mcp_client_ollama.json
```

## 🚀 Quick Start Examples

### Search and Extract Workflow
```python
# 1. Search for information
results = web_search("AI developments 2024", max_results=5, time_range="month")

# 2. Extract detailed content from top result
content = fetch_content(results.results[0].url, use_javascript=False)

# 3. Process multiple URLs
batch_content = batch_fetch([
    results.results[0].url,
    results.results[1].url,
    results.results[2].url
], max_concurrent=2)
```

### Performance Optimization
```python
# Check session statistics
session_info = get_session_info()

# Clear cache if needed
cache_status = clear_cache("search:*")

# Health check
health = health_check()
```

## ⚙️ Configuration Options

### Environment Variables
- `SEARXNG_URL`: SearXNG service endpoint
- `EXTRACTOR_URL`: Content extractor service endpoint  
- `REDIS_URL`: Redis cache connection
- `RATE_LIMIT_PER_DOMAIN`: Request rate limit (default: 2/sec)
- `CACHE_TTL`: Cache expiration time (default: 3600s)
- `USE_DISTRIBUTED_RATE_LIMIT`: Enable Redis-based rate limiting
- `MAX_CONCURRENT_REQUESTS`: Concurrent request limit (default: 5)

### Network Configurations
- **Docker Compose**: Uses `websearch_mcp_default` network
- **Host Network**: Direct localhost access for Ollama
- **Bridge Network**: Isolated container networking

## 🔍 Troubleshooting

### Common Issues

1. **"Command not found" Error**
   - Ensure Docker is installed and running
   - Check docker-compose services: `docker-compose ps`

2. **Network Connection Issues**
   - Verify network: `docker network ls | grep websearch`
   - Check service health: `curl http://localhost:8055/health`

3. **Rate Limiting**
   - Reduce request frequency
   - Enable distributed rate limiting for multiple instances

4. **Cache Issues**
   - Clear cache: Use `clear_cache()` tool
   - Check Redis: `docker-compose logs redis`

### Debug Commands
```bash
# Check all services
docker-compose ps

# View logs
docker-compose logs mcp
docker-compose logs extractor
docker-compose logs searxng

# Test MCP server directly
docker-compose exec mcp python server.py

# Test individual services
curl http://localhost:8055/health
curl http://localhost:8080/
```

## 📊 Performance Metrics

- **Search Speed**: ~2-5 seconds per query (varies by engines)
- **Content Extraction**: ~1-3 seconds per URL
- **Batch Processing**: 2-5 concurrent URLs
- **Cache Hit Rate**: 70-90% for repeated queries
- **Memory Usage**: ~200MB per service container

## 🔒 Security Considerations

- **API Keys**: Not required for basic search engines
- **Rate Limiting**: Prevents abuse with configurable limits
- **Network Isolation**: Docker networking provides isolation
- **Content Filtering**: Safe search options available
- **Cache Security**: Redis cache contains search results only

---

## 📚 Additional Resources

- **SearXNG Documentation**: https://docs.searxng.org/
- **Trafilatura Guide**: https://trafilatura.readthedocs.io/
- **MCP Specification**: https://modelcontextprotocol.io/
- **Docker Compose Reference**: https://docs.docker.com/compose/

**Ready to integrate WebSearch MCP with your LLM workflow!** 🚀