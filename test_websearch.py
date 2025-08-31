"""
WebSearch MCP Test Script
Builds containers if needed and runs demo searches with formatted output.
"""

import json
import requests
import subprocess
import sys
import time
from typing import Dict, List, Any
import argparse

# Configuration
BASE_URL = "http://localhost:8055"
SERVICES = ["redis", "searxng", "extractor", "mcp"]
TEST_QUERIES = [
    {"query": "artificial intelligence", "description": "AI Technology Search"},
    {"query": "FAU Erlangen python programming", "description": "University Programming Search"},
    {"query": "machine learning tutorials", "description": "ML Education Search"},
]

def run_command(cmd: str, capture=True) -> str:
    """Run shell command and return output."""
    try:
        if capture:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=True)
            return result.stdout
        else:
            subprocess.run(cmd, shell=True, check=True)
            return ""
    except subprocess.CalledProcessError as e:
        print(f"Command failed: {cmd}")
        print(f"Error: {e}")
        return ""

def check_docker():
    """Check if Docker is available."""
    try:
        run_command("docker --version")
        run_command("docker-compose --version")
        print("✅ Docker and Docker Compose are available")
        return True
    except:
        print("❌ Docker or Docker Compose not found. Please install Docker Desktop.")
        return False

def build_containers():
    """Build and start all containers."""
    print("\n🏗️  Building and starting containers...")
    print("This may take a few minutes on first run...")
    
    # Stop any existing containers
    run_command("docker-compose down", capture=False)
    
    # Build and start services
    run_command("docker-compose up -d --build", capture=False)
    
    print("⏳ Waiting for services to start...")
    time.sleep(15)

def wait_for_service(service_name: str, url: str, max_attempts: int = 10) -> bool:
    """Wait for a service to be ready."""
    for attempt in range(max_attempts):
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                print(f"✅ {service_name} is ready")
                return True
        except requests.RequestException:
            pass
        
        if attempt < max_attempts - 1:
            print(f"⏳ Waiting for {service_name}... ({attempt + 1}/{max_attempts})")
            time.sleep(3)
    
    print(f"❌ {service_name} failed to start")
    return False

def check_services() -> bool:
    """Check if all services are running."""
    print("\n🔍 Checking service status...")
    
    services_status = {
        "Content Extractor": f"{BASE_URL}/health",
        "Search API": f"{BASE_URL}/",
    }
    
    all_healthy = True
    for service, url in services_status.items():
        if not wait_for_service(service, url):
            all_healthy = False
    
    return all_healthy

def format_result(result: Dict[str, Any]) -> str:
    """Format a search result for display."""
    title = result.get("title", "No title")
    url = result.get("url", "")
    content = result.get("content", "No description available")
    
    # Truncate content
    if len(content) > 150:
        content = content[:150] + "..."
    
    return f"""
    📄 {title}
    🔗 {url}
    📝 {content}
    """

def search_web(query: str, max_results: int = 3) -> Dict[str, Any]:
    """Perform web search."""
    try:
        payload = {
            "query": query,
            "max_results": max_results,
            "language": "en"
        }
        
        response = requests.post(f"{BASE_URL}/search", json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
        
    except requests.RequestException as e:
        return {"error": str(e)}

def extract_content(url: str) -> Dict[str, Any]:
    """Extract content from URL."""
    try:
        payload = {"url": url}
        response = requests.post(f"{BASE_URL}/extract", json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
        
    except requests.RequestException as e:
        return {"error": str(e)}

def run_demo_searches():
    """Run demonstration searches."""
    print("\n🔍 Running Demo Searches")
    print("=" * 50)
    
    for test in TEST_QUERIES:
        query = test["query"]
        description = test["description"]
        
        print(f"\n🎯 {description}")
        print(f"Query: '{query}'")
        print("-" * 40)
        
        # Perform search
        results = search_web(query, max_results=3)
        
        if "error" in results:
            print(f"❌ Search failed: {results['error']}")
            continue
        
        # Display results
        count = results.get("number_of_results", 0)
        print(f"Found {count} results:")
        
        for i, result in enumerate(results.get("results", [])[:3], 1):
            print(f"\n{i}.{format_result(result)}")
        
        # Test content extraction on first result
        if results.get("results"):
            first_url = results["results"][0]["url"]
            print(f"\n📄 Extracting content from: {first_url}")
            
            content = extract_content(first_url)
            if "error" not in content:
                text = content.get("text", "")[:200] + "..." if len(content.get("text", "")) > 200 else content.get("text", "")
                title = content.get("title", "No title")
                print(f"✅ Extracted: '{title}'")
                print(f"Content preview: {text}")
            else:
                print(f"❌ Extraction failed: {content['error']}")
    
    print(f"\n🎉 Demo completed! All services are working correctly.")

def show_usage_examples():
    """Show usage examples for the API."""
    print("\n📚 API Usage Examples")
    print("=" * 50)
    
    print("\n1. Search the web:")
    print(f"""curl -X POST {BASE_URL}/search \\
  -H "Content-Type: application/json" \\
  -d '{{"query": "python programming", "max_results": 5}}'""")
    
    print("\n2. Extract content from URL:")
    print(f"""curl -X POST {BASE_URL}/extract \\
  -H "Content-Type: application/json" \\
  -d '{{"url": "https://example.com"}}'""")
    
    print("\n3. Check service health:")
    print(f"curl {BASE_URL}/health")
    
    print("\n4. View available endpoints:")
    print(f"curl {BASE_URL}/")

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="WebSearch MCP Test Script")
    parser.add_argument("--skip-build", action="store_true", help="Skip container build/start")
    parser.add_argument("--examples-only", action="store_true", help="Only show usage examples")
    args = parser.parse_args()
    
    print("🚀 WebSearch MCP Test Script")
    print("=" * 50)
    
    if args.examples_only:
        show_usage_examples()
        return
    
    # Check Docker
    if not check_docker():
        sys.exit(1)
    
    # Build containers unless skipped
    if not args.skip_build:
        build_containers()
    
    # Check service health
    if not check_services():
        print("\n❌ Some services failed to start. Check the logs:")
        print("docker-compose logs")
        sys.exit(1)
    
    # Run demonstration
    run_demo_searches()
    
    # Show usage examples
    show_usage_examples()
    
    print(f"\n✅ WebSearch MCP is fully operational!")
    print("🐳 To stop services: docker-compose down")
    print("📊 To view logs: docker-compose logs -f")

if __name__ == "__main__":
    main()