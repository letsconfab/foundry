#!/usr/bin/env python3
"""
Test script to verify tool tracking implementation in agent_tools.py
This script tests the print statements and tool functionality.
"""

import asyncio
import sys
import os

# Add the api directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'api'))

from agent_tools import call_tool

async def test_tool_tracking():
    """Test all tool functions to verify print statements work"""
    
    print("=" * 60)
    print("TESTING TOOL TRACKING IMPLEMENTATION")
    print("=" * 60)
    
    # Test data
    test_confab_id = 1
    test_purpose = "Test purpose for customer support agent"
    test_file_path = "PURPOSE.md"
    test_content = "# Test Purpose\n\nThis is a test purpose document."
    
    # Test 1: update_purpose
    print("\n1. Testing update_purpose...")
    result = await call_tool("update_purpose", {
        "confab_id": test_confab_id,
        "purpose_markdown": test_purpose
    })
    print(f"Result: {result}")
    
    # Test 2: get_purpose
    print("\n2. Testing get_purpose...")
    result = await call_tool("get_purpose", {
        "confab_id": test_confab_id
    })
    print(f"Result: {result}")
    
    # Test 3: update_file_tool
    print("\n3. Testing update_file_tool...")
    result = await call_tool("update_file_tool", {
        "confab_id": test_confab_id,
        "file_path": test_file_path,
        "content": test_content
    })
    print(f"Result: {result}")
    
    # Test 4: store_user_information
    print("\n4. Testing store_user_information...")
    result = await call_tool("store_user_information", {
        "confab_id": test_confab_id,
        "user_name": "Test User",
        "email": "test@example.com"
    })
    print(f"Result: {result}")
    
    # Test 5: get_user_information
    print("\n5. Testing get_user_information...")
    result = await call_tool("get_user_information", {
        "confab_id": test_confab_id,
        "email": "test@example.com"
    })
    print(f"Result: {result}")
    
    # Test 6: Unknown tool (should show error)
    print("\n6. Testing unknown tool...")
    result = await call_tool("unknown_tool", {
        "confab_id": test_confab_id
    })
    print(f"Result: {result}")
    
    print("\n" + "=" * 60)
    print("TOOL TRACKING TEST COMPLETED")
    print("=" * 60)
    print("\n✅ All print statements should be visible above")
    print("✅ Tool calls and results should be logged")
    print("✅ Error handling should work for unknown tools")
    print("\n🔍 Check the server logs to see:")
    print("   - [TOOL CALL] messages for each tool invocation")
    print("   - [TOOL RESULT] messages for each tool completion")
    print("   - [TOOL ERROR] messages for unknown tools")

if __name__ == "__main__":
    asyncio.run(test_tool_tracking())
