@ECHO OFF
CD /D "D:\src\websearch_mcp"
ECHO ==========================================
ECHO   MCP Interactive Chat with Tool Calling
ECHO ==========================================
ECHO.
ECHO Choose your mode:
ECHO [1] Local Mode - Run directly with local Ollama (faster, fewer dependencies)
ECHO [2] Docker Mode - Full containerized environment with web search
ECHO [3] Exit
ECHO.
SET /P choice="Enter your choice (1, 2, or 3): "

IF "%choice%"=="1" GOTO LOCAL_MODE
IF "%choice%"=="2" GOTO DOCKER_MODE
IF "%choice%"=="3" GOTO END
ECHO Invalid choice. Exiting...
GOTO END

:LOCAL_MODE
ECHO.
ECHO ==========================================
ECHO   Starting LOCAL MODE
ECHO ==========================================
ECHO.
ECHO Requirements:
ECHO - Ollama running locally (ollama serve)
ECHO - Conda environment 'thesis_env'
ECHO.
ECHO Note: Web search will be limited without external services
ECHO Press any key to continue, or Ctrl+C to cancel...
PAUSE >NUL

ECHO.
ECHO Activating conda environment and starting MCP client...
CALL conda activate thesis_env
python src/client/mcp_multi_client.py
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