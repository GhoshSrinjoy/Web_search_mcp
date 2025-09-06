@echo off
echo Starting WebSearch MCP RAG System...
echo.
echo This will start:
echo - Redis (caching)
echo - SearXNG (web search engine)  
echo - Extractor (content extraction service)
echo - Vectorstore (ChromaDB vector database)
echo - MCP Client (with dynamic tool selection)
echo.
echo Make sure Ollama is running on your host machine first!
echo Press any key to continue, or Ctrl+C to cancel...
pause >nul

echo.
echo Building and starting services...
docker-compose up --build

echo.
echo System stopped.
pause