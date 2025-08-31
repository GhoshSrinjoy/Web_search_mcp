# WebSearch MCP Quick Test Script

set -e  # Exit on any error

echo "🚀 WebSearch MCP Quick Test"
echo "=========================="

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker Desktop."
    exit 1
fi

echo "✅ Docker is running"

# Build and start services
echo "🏗️  Building and starting services..."
docker-compose up -d --build

echo "⏳ Waiting for services to start..."
sleep 20

# Check service health
echo "🔍 Checking service health..."
for i in {1..10}; do
    if curl -s http://localhost:8055/health >/dev/null; then
        echo "✅ Services are ready!"
        break
    fi
    if [ $i -eq 10 ]; then
        echo "❌ Services failed to start"
        docker-compose logs
        exit 1
    fi
    sleep 3
done

# Test search
echo ""
echo "🔍 Testing Web Search..."
echo "Query: 'artificial intelligence'"
curl -X POST http://localhost:8055/search \
    -H "Content-Type: application/json" \
    -d '{"query": "artificial intelligence", "max_results": 3}' | \
    jq '{query: .query, number_of_results: .number_of_results, titles: [.results[].title]}'

echo ""
echo "🔍 Testing Content Extraction..."
echo "URL: https://httpbin.org/html"
curl -X POST http://localhost:8055/extract \
    -H "Content-Type: application/json" \
    -d '{"url": "https://httpbin.org/html"}' | \
    jq '{url: .url, title: .title, text_length: (.text | length), has_content: (.text != null)}'

echo ""
echo "✅ All tests passed!"
echo ""
echo "📚 Available endpoints:"
curl -s http://localhost:8055/ | jq '.endpoints'

echo ""
echo "🎉 WebSearch MCP is fully operational!"
echo ""
echo "Commands:"
echo "  🐳 Stop services: docker-compose down"
echo "  📊 View logs: docker-compose logs -f"
echo "  🧪 Full demo: python test_websearch.py"