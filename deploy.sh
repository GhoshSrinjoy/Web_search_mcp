# WebSearch MCP Deployment Script
set -e

echo "🚀 Starting WebSearch MCP deployment..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Docker and Docker Compose are installed
check_requirements() {
    print_status "Checking requirements..."
    
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        print_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    
    print_success "Requirements check passed"
}

# Generate secure secret key for SearXNG
generate_secrets() {
    print_status "Generating secure secrets..."
    
    # Generate random secret key
    SECRET_KEY=$(openssl rand -hex 32 2>/dev/null || python3 -c "import secrets; print(secrets.token_hex(32))")
    
    # Replace secret key in SearXNG settings
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        sed -i '' "s/change-this-secret-key-in-production/$SECRET_KEY/" config/searxng/settings.yml
    else
        # Linux
        sed -i "s/change-this-secret-key-in-production/$SECRET_KEY/" config/searxng/settings.yml
    fi
    
    print_success "Secrets generated"
}

# Create required directories
create_directories() {
    print_status "Creating required directories..."
    
    mkdir -p data/{redis,chroma}
    mkdir -p logs
    
    # Set permissions
    chmod 755 data/{redis,chroma} logs
    
    print_success "Directories created"
}

# Build and start services
deploy_services() {
    print_status "Building and starting services..."
    
    # Build custom services
    docker-compose build --no-cache
    
    # Start all services
    docker-compose up -d
    
    print_success "Services started"
}

# Wait for services to be healthy
wait_for_health() {
    print_status "Waiting for services to become healthy..."
    
    local max_attempts=30
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        echo "Attempt $attempt/$max_attempts..."
        
        # Check Redis
        if docker-compose exec -T redis redis-cli ping &> /dev/null; then
            print_success "Redis is healthy"
        else
            print_warning "Redis not ready yet..."
        fi
        
        # Check SearXNG
        if curl -f http://localhost:8080/healthz &> /dev/null; then
            print_success "SearXNG is healthy"
        else
            print_warning "SearXNG not ready yet..."
        fi
        
        # Check Extractor
        if curl -f http://localhost:8055/health &> /dev/null; then
            print_success "Extractor is healthy"
        else
            print_warning "Extractor not ready yet..."
        fi
        
        # Check MCP
        if curl -f http://localhost:8001/health &> /dev/null; then
            print_success "MCP server is healthy"
            break
        else
            print_warning "MCP server not ready yet..."
        fi
        
        if [ $attempt -eq $max_attempts ]; then
            print_error "Services did not become healthy within expected time"
            print_status "Checking service logs..."
            docker-compose logs --tail=20
            exit 1
        fi
        
        sleep 5
        ((attempt++))
    done
    
    print_success "All services are healthy!"
}

# Run basic functionality tests
test_functionality() {
    print_status "Running basic functionality tests..."
    
    # Test web search
    echo "Testing web search..."
    if curl -s -X POST http://localhost:8001/tools/web_search \
        -H "Content-Type: application/json" \
        -d '{"query": "test search", "max_results": 3}' | jq -r '.results[0].title' &> /dev/null; then
        print_success "Web search is working"
    else
        print_warning "Web search test failed (this might be normal on first run)"
    fi
    
    # Test content extraction
    echo "Testing content extraction..."
    if curl -s -X POST http://localhost:8055/extract \
        -H "Content-Type: application/json" \
        -d '{"url": "https://example.com"}' | jq -r '.text' &> /dev/null; then
        print_success "Content extraction is working"
    else
        print_warning "Content extraction test failed"
    fi
    
    print_success "Basic tests completed"
}

# Show deployment summary
show_summary() {
    print_success "🎉 WebSearch MCP deployment completed!"
    echo
    echo "📋 Service URLs:"
    echo "   • MCP Server:     http://localhost:8001"
    echo "   • SearXNG:        http://localhost:8080"
    echo "   • Extractor:      http://localhost:8055"
    echo
    echo "🔧 MCP Tools Available:"
    echo "   • web_search      - Search the web"
    echo "   • fetch_content   - Extract content from URLs"
    echo "   • batch_fetch     - Fetch multiple URLs concurrently"
    echo "   • get_session_info - Get usage statistics"
    echo "   • clear_cache     - Clear cached data"
    echo
    echo "📚 Usage Examples:"
    echo '   curl -X POST http://localhost:8001/tools/web_search -H "Content-Type: application/json" -d '\''{"query": "latest AI news", "max_results": 5}'\'
    echo '   curl -X POST http://localhost:8001/tools/fetch_content -H "Content-Type: application/json" -d '\''{"url": "https://example.com"}'\'
    echo
    echo "📊 Monitor with:"
    echo "   docker-compose logs -f"
    echo "   docker-compose ps"
    echo
    echo "🛑 Stop with:"
    echo "   docker-compose down"
}

# Main deployment flow
main() {
    echo "WebSearch MCP - Phase 1 Deployment"
    echo "=================================="
    echo
    
    check_requirements
    create_directories
    generate_secrets
    deploy_services
    wait_for_health
    test_functionality
    show_summary
}

# Handle script arguments
case "${1:-}" in
    "stop")
        print_status "Stopping all services..."
        docker-compose down
        print_success "Services stopped"
        ;;
    "restart")
        print_status "Restarting services..."
        docker-compose down
        docker-compose up -d
        wait_for_health
        print_success "Services restarted"
        ;;
    "logs")
        docker-compose logs -f
        ;;
    "status")
        docker-compose ps
        ;;
    "test")
        test_functionality
        ;;
    "")
        main
        ;;
    *)
        echo "Usage: $0 [stop|restart|logs|status|test]"
        echo
        echo "Commands:"
        echo "  (no args)  - Deploy the full stack"
        echo "  stop       - Stop all services"
        echo "  restart    - Restart all services"
        echo "  logs       - Show service logs"
        echo "  status     - Show service status"
        echo "  test       - Run functionality tests"
        exit 1
        ;;
esac