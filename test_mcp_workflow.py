"""
Test script to demonstrate the complete MCP workflow
"""
import asyncio
from src.client.mcp_multi_client import MCPMultiClient

async def test_workflow():
    """Test the complete workflow with the original query"""
    client = MCPMultiClient()
    
    try:
        # Start all MCP servers
        await client.start_all_mcp_servers()
        print(f"\n[SUCCESS] Started {len(client.mcp_servers)} MCP servers")
        print(f"[SUCCESS] Available tools: {len(client.available_tools)}")
        
        if len(client.available_tools) == 0:
            print("[ERROR] No tools available")
            return
        
        # Test the original complex query
        test_query = "Who is the main contact person for RX-Systems GMBH and where is their office located?"
        print(f"\n[TEST] Testing with query: '{test_query}'")
        
        # Process with Ollama and MCP tools
        result = await client.chat_with_ollama(test_query)
        
        print(f"\n[RESULT] Final response:")
        print(result)
        
    except Exception as e:
        print(f"[ERROR] Test failed: {e}")
    finally:
        client.cleanup()

if __name__ == "__main__":
    asyncio.run(test_workflow())