@ECHO OFF
CD /D "D:\src\websearch_mcp"
ECHO ==========================================
ECHO   MCP Interactive Chat with Tool Calling
ECHO ==========================================
ECHO.
ECHO Choose your mode:
ECHO [1] Docker Mode - Full containerized environment with web search
ECHO [2] Exit
ECHO.
SET /P choice="Enter your choice (1 or 2): "

IF "%choice%"=="1" GOTO DOCKER_MODE
IF "%choice%"=="2" GOTO END
ECHO Invalid choice. Exiting...
GOTO END

:DOCKER_MODE
ECHO.
ECHO ==========================================
ECHO   Starting DOCKER MODE
ECHO ==========================================
ECHO.
ECHO This will start full containerized environment with:
ECHO - Web search (SearXNG)
ECHO - Content extraction
ECHO - Vector database (ChromaDB)
ECHO.
ECHO Make sure Ollama is running on your host machine first!
ECHO Press any key to continue, or Ctrl+C to cancel...
PAUSE >NUL

ECHO.
ECHO Building/Rebuilding MCP-enabled containers...
docker-compose build --quiet

ECHO Starting required services (Redis, SearXNG, Extractor)...
docker-compose up -d redis searxng extractor

ECHO Waiting for services to initialize...
TIMEOUT /T 12 /NOBREAK >NUL

ECHO Testing extractor service...
docker-compose exec -T extractor curl -f http://localhost:8055/health || echo "Extractor not ready yet, waiting more..."
TIMEOUT /T 5 /NOBREAK >NUL

ECHO Starting vectorstore service...
docker-compose up -d vectorstore

ECHO Waiting for vectorstore to initialize...
TIMEOUT /T 8 /NOBREAK >NUL

ECHO Launching interactive MCP client...
ECHO (The LLM can now autonomously decide when to use tools!)
ECHO.
docker-compose run --rm mcp-client

:END
PAUSE