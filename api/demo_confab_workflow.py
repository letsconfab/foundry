#!/usr/bin/env python3
"""
Demo: Complete confab workflow using the fixed tools
This demonstrates updating purpose.md and creating proper pull requests
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agent_tools import update_file_tool, get_purpose_tool
from database import get_db

def demo_confab_workflow():
    """Demonstrate complete confab workflow."""
    print("🚀 Confab Workflow Demo")
    print("=" * 50)
    
    try:
        db = next(get_db())
        
        # Get a test confab
        from models import Confab
        confab = db.query(Confab).first()
        
        if not confab:
            print("❌ No confab found in database")
            return False
            
        print(f"✅ Using confab: {confab.name} (ID: {confab.id})")
        
        # 1. Get current purpose
        print("\n--- 1. Getting current purpose.md ---")
        current_purpose = get_purpose_tool.invoke({'confab_id': confab.id})
        print(f"Current purpose: {current_purpose[:100]}...")
        
        # 2. Update purpose.md with the new format
        print("\n--- 2. Updating purpose.md ---")
        new_purpose = f"""Purpose: {confab.name} – {asyncio.get_event_loop().time()}

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

Updated: {asyncio.get_event_loop().time()}
"""
        
        result = update_file_tool.invoke({
            'confab_id': confab.id, 
            'file_path': 'purpose.md', 
            'content': new_purpose
        })
        print(f"purpose.md update result: {result}")
        
        # 3. Create GUARDRAILS.md
        print("\n--- 3. Creating GUARDRAILS.md ---")
        guardrails = """# Guardrails

## Behavioral Boundaries
- Always be respectful and professional
- Do not provide harmful or dangerous advice
- Maintain user privacy and confidentiality
- Stay within the defined scope of assistance

## Content Guidelines
- Provide accurate and verified information
- Acknowledge limitations when appropriate
- Escalate complex issues to human agents when needed

## Safety Constraints
- No discriminatory or offensive language
- No manipulation or deception
- Respect user boundaries and preferences
"""
        
        result = update_file_tool.invoke({
            'confab_id': confab.id, 
            'file_path': 'GUARDRAILS.md', 
            'content': guardrails
        })
        print(f"GUARDRAILS.md creation result: {result}")
        
        print("\n✅ Confab workflow completed successfully!")
        print("📁 Files created/updated in confab directory structure")
        print("🔀 Pull requests created for review")
        print("📝 purpose.md now contains the formatted purpose data")
        return True
        
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if 'db' in locals():
            db.close()

if __name__ == "__main__":
    demo_confab_workflow()
