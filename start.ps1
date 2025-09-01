Write-Host "Starting WebSearch MCP..." -ForegroundColor Green
Set-Location "D:\src\websearch_mcp"

Write-Host "Starting Docker services..." -ForegroundColor Yellow
docker-compose up -d redis searxng extractor

Write-Host "Waiting for services to start..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

$model = Read-Host "Enter Ollama model (press Enter for gpt-oss:20b)"
if ([string]::IsNullOrWhiteSpace($model)) {
    $model = "gpt-oss:20b"
}

Write-Host "Starting chat with $model..." -ForegroundColor Green
python simple_ollama_chat.py $model

Read-Host "Press Enter to exit"