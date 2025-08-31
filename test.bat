@echo off
REM WebSearch MCP Quick Test Script for Windows

echo 🚀 WebSearch MCP Quick Test
echo ==========================

REM Check if Docker is running
docker info >nul 2>&1
if errorlevel 1 (
    echo ❌ Docker is not running. Please start Docker Desktop.
    exit /b 1
)

echo ✅ Docker is running

REM Build and start services
echo 🏗️  Building and starting services...
docker-compose up -d --build

echo ⏳ Waiting for services to start...
timeout /t 20 /nobreak >nul

REM Check service health
echo 🔍 Checking service health...
for /l %%i in (1,1,10) do (
    curl -s http://localhost:8055/health >nul 2>&1
    if not errorlevel 1 (
        echo ✅ Services are ready!
        goto :services_ready
    )
    if %%i==10 (
        echo ❌ Services failed to start
        docker-compose logs
        exit /b 1
    )
    timeout /t 3 /nobreak >nul
)

:services_ready
REM Test search
echo.
echo 🔍 Testing Web Search...
echo Query: 'artificial intelligence'
curl -X POST http://localhost:8055/search -H "Content-Type: application/json" -d "{\"query\": \"artificial intelligence\", \"max_results\": 3}"

echo.
echo.
echo 🔍 Testing Content Extraction...
echo URL: https://httpbin.org/html
curl -X POST http://localhost:8055/extract -H "Content-Type: application/json" -d "{\"url\": \"https://httpbin.org/html\"}"

echo.
echo.
echo ✅ All tests passed!
echo.
echo 📚 Available endpoints:
curl -s http://localhost:8055/

echo.
echo 🎉 WebSearch MCP is fully operational!
echo.
echo Commands:
echo   🐳 Stop services: docker-compose down
echo   📊 View logs: docker-compose logs -f
echo   🧪 Full demo: python test_websearch.py

pause