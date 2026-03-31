from typing import Any, Dict
from sqlalchemy.orm import Session
from models import Confab
import logging
import asyncio
import os
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.tools import Tool
from agent_tools import get_langchain_tools
import datetime
import re


def generate_placeholder_confab_name(user_id: int, db: Session) -> str:
    """Generate 'untitled-confab' or 'untitled-confab-N' based on existing confabs."""
    existing = db.query(Confab).filter(
        Confab.user_id == user_id,
        Confab.name.like('untitled-confab%')
    ).count()
    if existing == 0:
        return 'untitled-confab'
    # Second confab should be untitled-confab-1, not untitled-confab-2
    return f'untitled-confab-{existing}'


def slugify(text: str) -> str:
    """
    Convert text to a clean, URL-friendly slug.
    
    Args:
        text: The input text to slugify
        
    Returns:
        A slugified string suitable for folder names
    """
    text = text.lower()
    text = re.sub(r'[^a-z0-9 ]', '', text)
    text = text.strip()
    text = text.replace(" ", "-")
    text = re.sub(r'-+', '-', text)
    return text

def generate_confab_name_from_purpose(purpose_text: str) -> str:
    """
    Generate a meaningful confab name from extracted purpose.
    
    Args:
        purpose_text: The purpose description from AI
        
    Returns:
        A clean, slugified confab name
    """
    # Extract key information from purpose
    purpose_text = purpose_text.strip()
    
    # Look for patterns like "Create X agent", "Build Y bot", etc.
    patterns = [
        r'create\s+(.+?)\s+(?:agent|bot|assistant|system)',
        r'build\s+(.+?)\s+(?:agent|bot|assistant|system)',
        r'design\s+(.+?)\s+(?:agent|bot|assistant|system)',
        r'develop\s+(.+?)\s+(?:agent|bot|assistant|system)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, purpose_text.lower())
        if match:
            name = match.group(1).strip()
            return slugify(name)
    
    # If no pattern matches, extract first meaningful phrase
    sentences = purpose_text.split('.')
    if sentences:
        first_sentence = sentences[0].strip()
        # Take first 3-4 words and clean them
        words = first_sentence.split()[:4]
        return slugify(' '.join(words))
    
    # Fallback to generic name
    return slugify("agent-assistant")

logger = logging.getLogger(__name__)

def format_purpose_markdown(purpose_text: str, confab_name: str = None) -> str:
    """
    Format purpose data in the specified format.
    
    Args:
        purpose_text: The purpose description from AI
        confab_name: Optional confab name for the title
        
    Returns:
        Formatted markdown string
    """
    # Clean and extract key information from purpose_text
    purpose_text = purpose_text.strip()
    
    # Create title
    title = f"Purpose: {confab_name or 'Agent Chat'} – {datetime.datetime.now().strftime('%m/%d/%y, %I:%M %p')}"
    
    # Extract overview (first paragraph or main description)
    overview = purpose_text.split('\n')[0] if '\n' in purpose_text else purpose_text
    if len(overview) > 200:
        overview = overview[:200] + "..."
    
    # Extract goals (look for numbered lists or bullet points)
    goals = []
    lines = purpose_text.split('\n')
    for line in lines:
        line = line.strip()
        if re.match(r'^\d+\.', line) or line.startswith('-') or line.startswith('*'):
            goals.append(line)
    
    # If no structured goals found, create default ones
    if not goals:
        goals = [
            "Provide helpful and accurate information",
            "Maintain professional and respectful communication", 
            "Assist with task organization and completion"
        ]
    
    # Extract use cases (look for specific use case patterns)
    use_cases = []
    for line in lines:
        line_lower = line.lower()
        if any(keyword in line_lower for keyword in ['use case', 'application', 'scenario', 'example']):
            use_cases.append(line.strip('- *'))
    
    # If no use cases found, create default ones
    if not use_cases:
        use_cases = [
            "Customer support interactions",
            "Task management and scheduling",
            "Information retrieval and analysis"
        ]
    
    # Format the markdown
    formatted = f"""{title}

Overview
{overview}

Goals
{chr(10).join(goals)}

Use Cases
{chr(10).join(['- ' + uc for uc in use_cases])}

Updated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    
    return formatted

def store_purpose_to_file(confab_id: int, user_message: str, ai_response: str, db: Session) -> bool:
    """
    Store user purpose and AI response to PURPOSE.md file in confab folder.
    
    Args:
        confab_id: The confab ID
        user_message: The user's original message
        ai_response: The AI's purpose description
        db: Database session
        
    Returns:
        True if successful, False otherwise
    """
    try:
        from agent_tools import update_file_tool
        
        # Get confab and ensure it has a slugified name
        confab = db.query(Confab).filter(Confab.id == confab_id).first()
        if not confab:
            logger.error(f"Confab {confab_id} not found")
            return False
        
        # Ensure confab has a proper name and slugify it
        if not confab.name or confab.name.startswith("Agent Chat –"):
            generated_name = generate_confab_name_from_purpose(ai_response)
            confab.name = generated_name
            confab.status = 'draft'
            db.commit()
            logger.info(f"Generated confab name: {generated_name}")
        
        # Use slugified version to maintain consistency with update_file_tool
        confab_name = slugify(confab.name)
        
        # Update confab name if it's not already slugified
        if confab.name != confab_name:
            confab.name = confab_name
            confab.status = 'draft'
            db.commit()
            logger.info(f"Updated confab name to slugified version: {confab_name}")
        
        # Format the purpose data
        formatted_purpose = format_purpose_markdown(ai_response, confab_name)
        
        # Store in confabs/{confab.name}/PURPOSE.md
        file_path = f"confabs/{confab_name}/PURPOSE.md"
        result = update_file_tool.invoke({
            'confab_id': confab_id,
            'file_path': file_path,
            'content': formatted_purpose
        })
        
        logger.info(f"Stored purpose to {file_path} for confab {confab_id}: {result}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to store purpose to file: {e}")
        return False

# Lazy-initialized LLM instance
_llm_instance = None

def get_llm():
    """
    Get the LLM instance, initializing lazily on first use.
    Uses Groq API with qwen3-32b model and bound tools.
    """
    global _llm_instance
    if _llm_instance is None:
        try:
            from langchain_groq import ChatGroq
            api_key = os.getenv("GROQ_API_KEY")
            model_name = os.getenv("GROQ_MODEL_NAME", "qwen/qwen3-32b")
            if not api_key:
                logger.error("GROQ_API_KEY environment variable is not set")
                raise ValueError("GROQ_API_KEY is required")
            
            # Create base ChatGroq instance
            llm = ChatGroq(api_key=api_key, model=model_name, temperature=0.7)
            
            # Get tools and bind them to the model
            from agent_tools import get_langchain_tools
            tools = get_langchain_tools()
            
            # Bind tools to the model so it can access them
            _llm_instance = llm.bind_tools(tools)
            
            logger.info(f"LLM initialized with {len(tools)} tools bound")
            
        except ImportError:
            logger.error("ChatGroq not found. Please install langchain-groq")
            raise
    return _llm_instance

async def run_langgraph_agent(confab_id: int, user_message: str, db: Session) -> Dict[str, Any]:
    """
    Run a simple agent with tool integration.
    
    Architecture:
    User message -> LLM thinks -> Calls Tool (DB / GitHub / API) -> Gets result -> Final response
    
    Args:
        confab_id: The ID of the confab to run the agent for
        user_message: The user's input message
        db: Database session
        
    Returns:
        Dict containing the agent's response and metadata
    """
    try:
        # Get confab
        confab = db.query(Confab).filter(Confab.id == confab_id).first()
        if not confab:
            return {
                "success": False,
                "error": f"Confab {confab_id} not found"
            }
        
        # Get purpose from GitHub PURPOSE.md file
        from agent_tools import get_purpose
        system_prompt = get_purpose(confab_id)
        if not system_prompt:
            system_prompt = "You are an AI agent that describes purposes and objectives. Focus only on explaining what something is for, not how to implement solutions."
        
        # Get tools from agent_tools
        from agent_tools import get_langchain_tools
        tools = get_langchain_tools()
        
        # Create tool mapping for execution
        tool_map = {tool.name: tool for tool in tools}
        
        # Simple agent implementation - focus on purpose description only
        tool_descriptions = []
        for tool in tools:
            tool_descriptions.append(f"- {tool.name}: {tool.description}")
        
        prompt = f"""{system_prompt}

IMPORTANT: You are a PURPOSE-ONLY agent. When asked about anything, only describe:
- What it is designed for
- Its main objectives and goals
- Its intended purpose and use cases

DO NOT provide:
- Solutions or implementations
- Technical how-to instructions  
- Tool recommendations or setup guidance
- Problem-solving advice

User: {user_message}

Available tools:
{chr(10).join(tool_descriptions)}

Respond ONLY with purpose description:"""
        
        # Run the model with tools
        logger.info(f"Running agent for confab {confab_id} with message: {user_message}")
        
        # Get the LLM with bound tools
        llm = get_llm()
        
        # Create a message format for the LLM
        from langchain_core.messages import HumanMessage
        messages = [HumanMessage(content=prompt)]
        
        # Invoke the LLM - it will have access to bound tools
        response = llm.invoke(messages)
        
        # Check if the model called any tools
        tool_calls = []
        if hasattr(response, 'tool_calls') and response.tool_calls:
            # Execute tool calls
            for tool_call in response.tool_calls:
                tool_name = tool_call.get('name')
                tool_args = tool_call.get('args', {})
                
                if tool_name in tool_map:
                    try:
                        # Execute the tool
                        tool_result = await tool_map[tool_name].ainvoke(tool_args)
                        tool_calls.append({
                            "tool": tool_name,
                            "args": tool_args,
                            "result": str(tool_result)
                        })
                        logger.info(f"Tool {tool_name} executed successfully")
                    except Exception as tool_error:
                        logger.error(f"Tool {tool_name} failed: {tool_error}")
                        tool_calls.append({
                            "tool": tool_name,
                            "args": tool_args,
                            "error": str(tool_error)
                        })
        
        # Store the purpose data to purpose.md file
        store_purpose_to_file(confab_id, user_message, str(response.content), db)
        
        return {
            "success": True,
            "response": str(response.content),
            "tool_calls": tool_calls,
            "confab_id": confab_id,
            "timestamp": str(datetime.datetime.now()),
            "architecture": "LangChain LLM with tool execution",
            "purpose_stored": True,
            "purpose_source": "GitHub PURPOSE.md" if get_purpose(confab_id) else "Generated"
        }
            
    except Exception as e:
        logger.error(f"Error running agent: {e}")
        return {
            "success": False,
            "error": str(e)
        }

# Legacy function for backward compatibility
async def run_stage(db: Session, confab_id: int, stage_id: str, user_input: str, temperature: float = 0.7) -> Dict[str, Any]:
    """
    Legacy function for backward compatibility with existing stage-based system.
    This now uses the new LangGraph agent under the hood.
    """
    try:
        # Get confab configuration
        confab = db.query(Confab).filter(Confab.id == confab_id).first()
        if not confab:
            raise ValueError("Confab not found")

        cfg = confab.config or {}
        stages = cfg.get("stages", [])
        
        # Find the stage
        stage = None
        stage_idx = None
        try:
            idx = int(stage_id)
            if 0 <= idx - 1 < len(stages):
                stage_idx = idx - 1
                stage = stages[stage_idx]
        except Exception:
            # fallback: find by name or id
            for i, s in enumerate(stages):
                if str(s.get("id")) == str(stage_id) or s.get("name") == stage_id:
                    stage_idx = i
                    stage = s
                    break

        if stage is None:
            raise ValueError("Stage not found in confab config")

        # Use LangGraph agent instead of direct LLM call
        prompt_template = stage.get("prompt_template") or "{input}"
        prompt = prompt_template.replace("{input}", user_input)
        
        # Add stage context to the message
        stage_context = f"You are processing stage '{stage.get('name')}' of the confab setup. "
        stage_context += f"Stage description: {stage.get('description', 'No description')}. "
        full_message = stage_context + prompt
        
        # Run the LangGraph agent
        result = await run_langgraph_agent(confab_id, full_message, db)
        
        # Save result into confab.config (for backward compatibility)
        if result["success"]:
            result_obj = {
                "output": result["response"],
                "input": user_input,
                "tool_calls": result.get("tool_calls", []),
            }
            stages[stage_idx]["result"] = result_obj
            cfg["stages"] = stages
            confab.config = cfg
            db.commit()
            
            return {
                "stage": stage.get("name"), 
                "stage_id": stage.get("id") or stage_idx + 1, 
                "result": result_obj,
                "agent_response": result["response"]
            }
        else:
            raise ValueError(result.get("error", "Agent execution failed"))
            
    except Exception as e:
        logger.error(f"Error in legacy run_stage: {e}")
        raise

# Helper function to get agent status
def get_agent_status() -> Dict[str, Any]:
    """Get the current status of the agent system."""
    try:
        llm = get_llm() if _llm_instance else None
        return {
            "status": "active" if llm else "not_initialized",
            "llm_provider": type(llm).__name__ if llm else "ChatGroq (not initialized)",
            "tools_count": len(get_langchain_tools()),
            "architecture": "LangGraph with MCP integration"
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }
