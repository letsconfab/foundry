#!/usr/bin/env python3
"""
Test script to verify agent tools work with purpose.md files and GitHub integration.
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import get_db
from models import Confab
from agent_tools import get_purpose, update_purpose, get_langchain_tools
from agent_runner import run_langgraph_agent
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_purpose_functions():
    """Test get_purpose and update_purpose functions."""
    print("=== Testing Purpose Functions ===")
    
    try:
        db = next(get_db())
        
        # Get a test confab (you may need to adjust this ID)
        confab = db.query(Confab).first()
        if not confab:
            print("No confab found in database. Please create one first.")
            return False
            
        confab_id = confab.id
        print(f"Testing with confab ID: {confab_id}")
        
        # Test 1: Get existing purpose
        print("\n1. Testing get_purpose...")
        existing_purpose = get_purpose(confab_id)
        if existing_purpose:
            print(f"✓ Found existing purpose: {existing_purpose[:100]}...")
        else:
            print("✓ No existing purpose found (expected for new confab)")
        
        # Test 2: Update purpose
        print("\n2. Testing update_purpose...")
        test_purpose = """Purpose: Agent Chat – 2/27/26, 4:25 PM
Overview
This confab is designed to assist users with intelligent conversation and task management.

Goals
Provide helpful and accurate information
Maintain professional and respectful communication
Assist with task organization and completion

Use Cases
Customer support interactions
Task management and scheduling
Information retrieval and analysis

Updated: 9305.0"""
        
        success = update_purpose(confab_id, test_purpose)
        if success:
            print("✓ Purpose updated successfully")
        else:
            print("✗ Failed to update purpose")
            return False
        
        # Test 3: Verify purpose was saved
        print("\n3. Verifying purpose was saved...")
        saved_purpose = get_purpose(confab_id)
        if saved_purpose and "Agent Chat" in saved_purpose:
            print("✓ Purpose saved and retrieved successfully")
        else:
            print("✗ Failed to retrieve saved purpose")
            return False
            
        return True
        
    except Exception as e:
        print(f"✗ Error in test_purpose_functions: {e}")
        return False
    finally:
        if 'db' in locals():
            db.close()

async def test_agent_runner():
    """Test the agent runner with purpose.md integration."""
    print("\n=== Testing Agent Runner ===")
    
    try:
        db = next(get_db())
        
        # Get a test confab
        confab = db.query(Confab).first()
        if not confab:
            print("No confab found in database.")
            return False
            
        confab_id = confab.id
        print(f"Testing agent with confab ID: {confab_id}")
        
        # Test agent with a simple question
        test_message = "What is this tool designed for?"
        print(f"\nTesting with message: '{test_message}'")
        
        result = await run_langgraph_agent(confab_id, test_message, db)
        
        if result["success"]:
            print("✓ Agent executed successfully")
            print(f"Response: {result['response'][:200]}...")
            print(f"Purpose stored: {result.get('purpose_stored', False)}")
            print(f"Purpose source: {result.get('purpose_source', 'Unknown')}")
        else:
            print(f"✗ Agent failed: {result.get('error', 'Unknown error')}")
            return False
            
        return True
        
    except Exception as e:
        print(f"✗ Error in test_agent_runner: {e}")
        return False
    finally:
        if 'db' in locals():
            db.close()

def test_tools_list():
    """Test that all tools are properly loaded."""
    print("\n=== Testing Tools List ===")
    
    try:
        tools = get_langchain_tools()
        print(f"✓ Loaded {len(tools)} tools:")
        
        for tool in tools:
            print(f"  - {tool.name}: {tool.description[:50]}...")
            
        return True
        
    except Exception as e:
        print(f"✗ Error loading tools: {e}")
        return False

async def main():
    """Run all tests."""
    print("Starting Agent Tools Integration Tests")
    print("=" * 50)
    
    # Test 1: Tools list
    if not test_tools_list():
        print("Tools list test failed!")
        return
    
    # Test 2: Purpose functions
    if not await test_purpose_functions():
        print("Purpose functions test failed!")
        return
    
    # Test 3: Agent runner
    if not await test_agent_runner():
        print("Agent runner test failed!")
        return
    
    print("\n" + "=" * 50)
    print("✓ All tests passed successfully!")
    print("\nThe system is working correctly:")
    print("- GitHub integration with purpose.md files")
    print("- Groq LLM integration")
    print("- Agent tools based on actual purpose data")

if __name__ == "__main__":
    asyncio.run(main())
