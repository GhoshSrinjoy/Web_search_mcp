@ECHO OFF
CD /D "D:\src\websearch_mcp"
ECHO WebSearch MCP Quick Start
ECHO =========================
SET /P MODEL="Enter model (press Enter for gpt-oss:20b): "
IF "%MODEL%"=="" SET MODEL=gpt-oss:20b
ECHO Starting services...
docker-compose up -d redis searxng extractor
TIMEOUT /T 5 /NOBREAK >NUL
ECHO Starting chat with %MODEL%...
python simple_ollama_chat.py %MODEL%
PAUSE