#!/usr/bin/env python3
"""
Test script for the enhanced agent_tools.py functionality.
Tests the Foreman integration and GitHub workflow.
"""

import asyncio
import sys
import os

# Add the API directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'api'))

from database import get_db
from models import Confab, User, GitHubAccount
from agent_tools import (
    _get_purpose_internal, 
    _generate_name_internal, 
    _create_spec_internal,
    _save_spec_locally_internal,
    _github_push_internal
)

async def test_purpose_extraction():
    """Test purpose extraction through Foreman system."""
    print("=== Testing Purpose Extraction ===")
    
    try:
        # Create a test confab if needed
        db = next(get_db())
        
        # Check if we have a test confab
        test_confab = db.query(Confab).filter(Confab.name == "test-confab").first()
        if not test_confab:
            # Create a test user and confab
            test_user = db.query(User).filter(User.email == "test@example.com").first()
            if not test_user:
                test_user = User(
                    name="Test User",
                    email="test@example.com",
                    password_hash="test_hash",
                    country="US",
                    timezone="UTC"
                )
                db.add(test_user)
                db.commit()
                db.refresh(test_user)
            
            test_confab = Confab(
                name="test-confab",
                user_id=test_user.id,
                status="building"
            )
            db.add(test_confab)
            db.commit()
            db.refresh(test_confab)
        
        print(f"Using test confab: {test_confab.id} - {test_confab.name}")
        
        # Test purpose extraction
        user_input = "I want to create an AI assistant that helps with customer support for my e-commerce store"
        result = await _get_purpose_internal(test_confab.id, user_input)
        
        print(f"Purpose extraction result: {result}")
        
        if result.get("status") == "success":
            print("✅ Purpose extraction successful")
            print(f"Extracted purpose: {result['data']['purpose']}")
        else:
            print(f"❌ Purpose extraction failed: {result.get('error')}")
        
        db.close()
        return result.get("status") == "success"
        
    except Exception as e:
        print(f"❌ Purpose extraction test failed: {e}")
        return False

async def test_spec_generation():
    """Test spec file generation."""
    print("\n=== Testing Spec Generation ===")
    
    try:
        db = next(get_db())
        
        test_confab = db.query(Confab).filter(Confab.name == "test-confab").first()
        if not test_confab:
            print("❌ Test confab not found")
            return False
        
        purpose_text = "AI assistant for customer support in e-commerce"
        confab_name = "support-assistant"
        
        result = await _create_spec_internal(test_confab.id, purpose_text, confab_name)
        
        print(f"Spec generation result: {result}")
        
        if result.get("status") == "success":
            print("✅ Spec generation successful")
            spec_files = result['data']['spec_files']
            print(f"Generated {len(spec_files)} spec files:")
            for filename in spec_files.keys():
                print(f"  - {filename}")
        else:
            print(f"❌ Spec generation failed: {result.get('error')}")
        
        db.close()
        return result.get("status") == "success"
        
    except Exception as e:
        print(f"❌ Spec generation test failed: {e}")
        return False

async def test_local_save():
    """Test local spec file saving."""
    print("\n=== Testing Local Save ===")
    
    try:
        db = next(get_db())
        
        test_confab = db.query(Confab).filter(Confab.name == "test-confab").first()
        if not test_confab:
            print("❌ Test confab not found")
            return False
        
        spec_files = {
            "PURPOSE.md": "# Test Purpose\nThis is a test purpose file.",
            "Confab.toml": "[confab]\nname = \"test-confab\"\nversion = \"1.0.0\"\n"
        }
        
        result = await _save_spec_locally_internal(test_confab.id, "test-confab", spec_files)
        
        print(f"Local save result: {result}")
        
        if result.get("status") == "success":
            print("✅ Local save successful")
            print(f"Saved files: {result['data']['saved_files']}")
        else:
            print(f"❌ Local save failed: {result.get('error')}")
        
        db.close()
        return result.get("status") == "success"
        
    except Exception as e:
        print(f"❌ Local save test failed: {e}")
        return False

async def main():
    """Run all tests."""
    print("Testing Enhanced Agent Tools")
    print("=" * 50)
    
    tests = [
        ("Purpose Extraction", test_purpose_extraction),
        ("Spec Generation", test_spec_generation),
        ("Local Save", test_local_save),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} test crashed: {e}")
            results.append((test_name, False))
    
    print("\n" + "=" * 50)
    print("Test Results Summary:")
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status} {test_name}")
    
    total_passed = sum(1 for _, passed in results if passed)
    total_tests = len(results)
    print(f"\nOverall: {total_passed}/{total_tests} tests passed")

if __name__ == "__main__":
    asyncio.run(main())
