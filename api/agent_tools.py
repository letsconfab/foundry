from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from models import Confab, GitHubAccount
import logging
import asyncio
import os
import datetime
from github import Github
from mcp.server import Server
from langchain_core.tools import tool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Initialize MCP server for tool management
mcp = Server("ConfabAgent")

# Database tools for Purpose management
@mcp.list_tools()
async def list_tools():
    """List available tools."""
    return [
        {
            "name": "get_purpose",
            "description": "Get the purpose markdown for a confab from GitHub repo's PURPOSE.md file or database.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "confab_id": {"type": "integer"}
                },
                "required": ["confab_id"]
            }
        },
        {
            "name": "update_purpose",
            "description": "Update the purpose markdown for a confab in GitHub repo's PURPOSE.md file and database.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "confab_id": {"type": "integer"},
                    "purpose_markdown": {"type": "string"}
                },
                "required": ["confab_id", "purpose_markdown"]
            }
        },
        {
            "name": "update_file_tool",
            "description": "Update a file in the GitHub repository and commit changes. This instruction is for updating any file and committing changes. Its primary objective is to facilitate the process of modifying or adding content to files in a structured manner within a project repository.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "confab_id": {"type": "integer"},
                    "file_path": {"type": "string"},
                    "content": {"type": "string"}
                },
                "required": ["confab_id", "file_path", "content"]
            }
        },
        {
            "name": "create_commit_tool",
            "description": "Create a commit for a file in the GitHub repository. This tool is designed for committing file changes to version control. Use cases include saving progress, creating checkpoints, and documenting changes in the project history.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "confab_id": {"type": "integer"},
                    "file_path": {"type": "string"},
                    "content": {"type": "string"},
                    "message": {"type": "string"}
                },
                "required": ["confab_id", "file_path", "content"]
            }
        },
        {
            "name": "create_pull_request_tool",
            "description": "Create a pull request for file changes in the GitHub repository. This tool facilitates code review and collaboration by creating pull requests for proposed changes.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "confab_id": {"type": "integer"},
                    "file_path": {"type": "string"},
                    "content": {"type": "string"},
                    "title": {"type": "string"}
                },
                "required": ["confab_id", "file_path", "content"]
            }
        },
        {
            "name": "store_user_information",
            "description": "Store user information (name and phone number) in the confab's knowledge base.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "confab_id": {"type": "integer"},
                    "user_name": {"type": "string"},
                    "phone_number": {"type": "string"}
                },
                "required": ["confab_id", "user_name", "phone_number"]
            }
        },
        {
            "name": "get_user_information",
            "description": "Retrieve user information from the confab's knowledge base.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "confab_id": {"type": "integer"},
                    "phone_number": {"type": "string"}
                },
                "required": ["confab_id"]
            }
        }
    ]

@mcp.call_tool()
async def call_tool(name: str, arguments: dict):
    """Handle tool calls."""
    if name == "get_purpose":
        result = get_purpose(arguments.get("confab_id"))
        return {"content": [{"type": "text", "text": result or "No purpose found"}]}
    elif name == "update_purpose":
        success = update_purpose(arguments.get("confab_id"), arguments.get("purpose_markdown"))
        return {"content": [{"type": "text", "text": "Purpose updated successfully" if success else "Failed to update purpose"}]}
    elif name == "update_file_tool":
        result = update_file_tool(arguments.get("confab_id"), arguments.get("file_path"), arguments.get("content"))
        return {"content": [{"type": "text", "text": result}]}
    elif name == "create_commit_tool":
        result = create_commit_tool(arguments.get("confab_id"), arguments.get("file_path"), arguments.get("content"), arguments.get("message", "Update file"))
        return {"content": [{"type": "text", "text": result}]}
    elif name == "create_pull_request_tool":
        result = create_pull_request_tool(arguments.get("confab_id"), arguments.get("file_path"), arguments.get("content"), arguments.get("title", "File Update"))
        return {"content": [{"type": "text", "text": result}]}
    elif name == "store_user_information":
        success = store_user_information(arguments.get("confab_id"), arguments.get("user_name"), arguments.get("phone_number"))
        return {"content": [{"type": "text", "text": "User information stored successfully" if success else "Failed to store user information"}]}
    elif name == "get_user_information":
        results = get_user_information(arguments.get("confab_id"), arguments.get("phone_number"))
        if results:
            if arguments.get("phone_number") and len(results) == 1:
                user = results[0]
                return {"content": [{"type": "text", "text": f"Found user: {user.get('name', 'Unknown')} - {user.get('phone_number', 'Unknown')}"}]}
            else:
                user_list = "\n".join([f"- {user.get('name', 'Unknown')}: {user.get('phone_number', 'Unknown')}" for user in results])
                return {"content": [{"type": "text", "text": f"Found {len(results)} users:\n{user_list}"}]}
        else:
            return {"content": [{"type": "text", "text": "No user information found"}]}
    else:
        return {"content": [{"type": "text", "text": f"Unknown tool: {name}"}]}

def get_purpose(confab_id: int) -> Optional[str]:
    """Get the purpose markdown for a confab from GitHub repo's purpose.md file."""
    print("get_purpose working successfully")
    try:
        from database import get_db
        db = next(get_db())
        
        confab = db.query(Confab).filter(Confab.id == confab_id).first()
        if not confab:
            print(f"Confab with ID {confab_id} not found")
            return None
            
        # Try to get from GitHub first (purpose.md)
        github_account = db.query(GitHubAccount).filter(GitHubAccount.user_id == confab.user_id).first()
        if github_account:
            try:
                print(f"Attempting to connect to GitHub for user {confab.user_id}")
                
                # Validate token before using it
                if not github_account.access_token:
                    print("No GitHub access token found")
                    raise Exception("No GitHub access token available")
                
                g = Github(github_account.access_token)
                
                # Test the token validity
                try:
                    user = g.get_user()
                    print(f"GitHub token valid for user: {user.login}")
                except Exception as token_error:
                    print(f"Invalid GitHub token: {token_error}")
                    raise Exception("GitHub token is invalid or expired")
                
                repo_name = f"{github_account.selected_org or github_account.github_username}/{github_account.selected_repo}"
                print(f"Looking for repository: {repo_name}")
                
                repo = g.get_repo(repo_name)
                purpose_file = repo.get_contents("PURPOSE.md")
                print("Successfully retrieved PURPOSE.md from GitHub")
                return purpose_file.decoded_content.decode('utf-8')
            except Exception as e:
                logger.warning(f"Could not fetch PURPOSE.md from GitHub: {e}")
                print(f"GitHub access failed: {e}")
                return None
        else:
            print("No GitHub account connected for this user")
            return None
        
    except Exception as e:
        logger.error(f"Error in get_purpose: {e}")
        print(f"Error in get_purpose: {e}")
        return None
    finally:
        if 'db' in locals():
            db.close()

def update_purpose(confab_id: int, purpose_markdown: str) -> bool:
    """Update the purpose markdown for a confab in GitHub repo's purpose.md file."""
    print("update_purpose working successfully")
    try:
        # Use the helper function to ensure repo exists and create/update purpose.md
        github_success = ensure_repo_and_purpose(confab_id, purpose_markdown)
        if github_success:
            print("GitHub update completed successfully")
            return True
        else:
            print("GitHub update failed")
            return False
            
    except Exception as e:
        logger.error(f"Error in update_purpose: {e}")
        print(f"Error in update_purpose: {e}")
        return False

# Database tools for User Information Management (Phone Numbers and Names)
def store_user_information(confab_id: int, user_name: str, phone_number: str) -> bool:
    """Store user information (name and phone number) in the confab's knowledge base."""
    print("store_user_information working successfully")
    try:
        from database import get_db
        db = next(get_db())
        
        confab = db.query(Confab).filter(Confab.id == confab_id).first()
        if not confab:
            print(f"Confab with ID {confab_id} not found")
            return False
            
        # Store in knowledge base
        cfg = confab.config or {}
        if "user_information" not in cfg:
            cfg["user_information"] = []
        
        # Check if user already exists
        user_info = cfg["user_information"]
        for user in user_info:
            if user.get("phone_number") == phone_number:
                user["name"] = user_name  # Update name if phone exists
                print(f"Updated existing user information for phone: {phone_number}")
                break
        else:
            # Add new user
            user_info.append({
                "name": user_name,
                "phone_number": phone_number,
                "created_at": datetime.datetime.now().isoformat()
            })
            print(f"Added new user information: {user_name} - {phone_number}")
        
        cfg["user_information"] = user_info
        confab.config = cfg
        db.commit()
        print("User information stored successfully in database")
        return True
        
    except Exception as e:
        logger.error(f"Error in store_user_information: {e}")
        print(f"Error in store_user_information: {e}")
        return False
    finally:
        if 'db' in locals():
            db.close()

def get_user_information(confab_id: int, phone_number: str = None) -> List[Dict[str, Any]]:
    """Retrieve user information from the confab's knowledge base."""
    print("get_user_information working successfully")
    try:
        from database import get_db
        db = next(get_db())
        
        confab = db.query(Confab).filter(Confab.id == confab_id).first()
        if not confab:
            print(f"Confab with ID {confab_id} not found")
            return []
            
        cfg = confab.config or {}
        user_info = cfg.get("user_information", [])
        
        if phone_number:
            # Return specific user
            for user in user_info:
                if user.get("phone_number") == phone_number:
                    print(f"Found user information for phone: {phone_number}")
                    return [user]
            print(f"No user found with phone: {phone_number}")
            return []
        else:
            # Return all users
            print(f"Retrieved {len(user_info)} user records")
            return user_info
        
    except Exception as e:
        logger.error(f"Error in get_user_information: {e}")
        print(f"Error in get_user_information: {e}")
        return []
    finally:
        if 'db' in locals():
            db.close()

# LangChain tool wrappers for user information management
class StoreUserInformationInput(BaseModel):
    confab_id: int = Field(description="The ID of the confab to store user information for")
    user_name: str = Field(description="The name of the user")
    phone_number: str = Field(description="The phone number of the user")

@tool(args_schema=StoreUserInformationInput)
def store_user_information_tool(confab_id: int, user_name: str, phone_number: str) -> str:
    """Store user information (name and phone number) in the confab's knowledge base."""
    success = store_user_information(confab_id, user_name, phone_number)
    return "User information stored successfully" if success else "Failed to store user information"

class GetUserInformationInput(BaseModel):
    confab_id: int = Field(description="The ID of the confab to search in")
    phone_number: Optional[str] = Field(default=None, description="The phone number to search for (optional)")

@tool(args_schema=GetUserInformationInput)
def get_user_information_tool(confab_id: int, phone_number: str = None) -> str:
    """Retrieve user information from the confab's knowledge base."""
    results = get_user_information(confab_id, phone_number)
    if results:
        if phone_number and len(results) == 1:
            user = results[0]
            return f"Found user: {user.get('name', 'Unknown')} - {user.get('phone_number', 'Unknown')}"
        else:
            return f"Found {len(results)} users:\n" + "\n".join([f"- {user.get('name', 'Unknown')}: {user.get('phone_number', 'Unknown')}" for user in results])
    return "No user information found"

# Database tools for Memory management
def search_knowledge_base(confab_id: int, query: str) -> List[Dict[str, Any]]:
    """Search the knowledge base for information matching the query."""
    print("search_knowledge_base working succefuly")
    try:
        from database import get_db
        db = next(get_db())
        
        confab = db.query(Confab).filter(Confab.id == confab_id).first()
        if not confab:
            return []
            
        cfg = confab.config or {}
        docs = cfg.get("knowledge_documents", [])
        q = query.lower()
        results = [d for d in docs if q in (d.get("content","") + d.get("title","")).lower()]
        return results
        
    except Exception as e:
        logger.error(f"Error in search_knowledge_base: {e}")
        return []
    finally:
        if 'db' in locals():
            db.close()

def update_knowledge_base(confab_id: int, file_name: str, information: str) -> bool:
    """Update or add information to the knowledge base."""
    print("update_knowledge_base working succefuly")
    try:
        from database import get_db
        db = next(get_db())
        
        confab = db.query(Confab).filter(Confab.id == confab_id).first()
        if not confab:
            return False
            
        cfg = confab.config or {}
        docs = cfg.get("knowledge_documents", [])
        
        # Find existing document
        for d in docs:
            if d.get("file_name") == file_name:
                d["content"] = information
                break
        else:
            # Add new document
            docs.append({"file_name": file_name, "title": file_name, "content": information})
            
        cfg["knowledge_documents"] = docs
        confab.config = cfg
        db.commit()
        return True
        
    except Exception as e:
        logger.error(f"Error in update_knowledge_base: {e}")
        return False
    finally:
        if 'db' in locals():
            db.close()

# LangChain tool wrappers for database integration
class GetPurposeInput(BaseModel):
    confab_id: int = Field(description="The ID of the confab to get purpose for")

@tool(args_schema=GetPurposeInput)
def get_purpose_tool(confab_id: int) -> str:
    """Get the purpose for a confab from GitHub repo or database."""
    result = get_purpose(confab_id)
    return result or "No purpose found"

class UpdatePurposeInput(BaseModel):
    confab_id: int = Field(description="The ID of the confab to update purpose for")
    purpose_markdown: str = Field(description="The purpose markdown content")

@tool(args_schema=UpdatePurposeInput)
def update_purpose_tool(confab_id: int, purpose_markdown: str) -> str:
    """Update the purpose for a confab in GitHub repo and database."""
    success = update_purpose(confab_id, purpose_markdown)
    return "Purpose updated successfully" if success else "Failed to update purpose"

class SearchKnowledgeBaseInput(BaseModel):
    confab_id: int = Field(description="The ID of the confab to search in")
    query: str = Field(description="The search query")

@tool(args_schema=SearchKnowledgeBaseInput)
def search_knowledge_base_tool(confab_id: int, query: str) -> str:
    """Search the knowledge base for information."""
    results = search_knowledge_base(confab_id, query)
    if results:
        return f"Found {len(results)} results:\n" + "\n".join([f"- {r.get('title', r.get('file_name', 'Untitled'))}: {r.get('content', '')[:200]}..." for r in results])
    return "No results found"

class UpdateKnowledgeBaseInput(BaseModel):
    confab_id: int = Field(description="The ID of the confab to update")
    file_name: str = Field(description="The name of the file/document")
    information: str = Field(description="The information to store")

@tool(args_schema=UpdateKnowledgeBaseInput)
def update_knowledge_base_tool(confab_id: int, file_name: str, information: str) -> str:
    """Update or add information to the knowledge base."""
    success = update_knowledge_base(confab_id, file_name, information)
    return "Knowledge base updated successfully" if success else "Failed to update knowledge base"

def ensure_repo_and_purpose(confab_id: int, purpose_markdown: str) -> bool:
    """Ensure repository exists and purpose.md file is created."""
    try:
        from database import get_db
        from confab_manager import create_github_repository, initialize_confab_repository
        db = next(get_db())
        
        confab = db.query(Confab).filter(Confab.id == confab_id).first()
        if not confab:
            print(f"Confab with ID {confab_id} not found in ensure_repo_and_purpose")
            return False
            
        github_account = db.query(GitHubAccount).filter(GitHubAccount.user_id == confab.user_id).first()
        if not github_account:
            print("No GitHub account connected in ensure_repo_and_purpose")
            return False
            
        try:
            print(f"Checking/creating repository for user {confab.user_id}")
            
            # Validate token before using it
            if not github_account.access_token:
                print("No GitHub access token found in ensure_repo_and_purpose")
                return False
            
            g = Github(github_account.access_token)
            
            # Test the token validity first
            try:
                user = g.get_user()
                print(f"GitHub token valid for user: {user.login}")
            except Exception as token_error:
                print(f"Invalid GitHub token in ensure_repo_and_purpose: {token_error}")
                return False
            
            repo_name = github_account.selected_repo
            repo_owner = github_account.selected_org or github_account.github_username
            full_repo_name = f"{repo_owner}/{repo_name}"
            
            # Try to get the repository first
            try:
                repo = g.get_repo(full_repo_name)
                print(f"Repository {full_repo_name} exists")
            except Exception as repo_error:
                print(f"Repository {full_repo_name} not found or access denied: {repo_error}")
                # Repository doesn't exist or no access, try to create it
                try:
                    print(f"Creating repository {full_repo_name}")
                    from confab_manager import create_github_repository
                    repo_info = create_github_repository(
                        repo_name=repo_name,
                        access_token=github_account.access_token,
                        description=f"Confabs repository for {repo_owner}",
                        private=False
                    )
                    repo = g.get_repo(full_repo_name)
                    print(f"Repository {full_repo_name} created successfully")
                except Exception as create_error:
                    print(f"Failed to create repository {full_repo_name}: {create_error}")
                    return False
            
            # Now create/update PURPOSE.md (changed from purpose.md)
            try:
                file = repo.get_contents("PURPOSE.md")
                repo.update_file("PURPOSE.md", "Update purpose", purpose_markdown, file.sha)
                print("PURPOSE.md updated successfully")
            except Exception as file_error:
                # File might not exist, try to create it
                try:
                    repo.create_file("PURPOSE.md", "Create purpose", purpose_markdown)
                    print("PURPOSE.md created successfully")
                except Exception as create_file_error:
                    print(f"Failed to create PURPOSE.md: {create_file_error}")
                    return False
                
            return True
            
        except Exception as e:
            logger.error(f"Error ensuring repo and purpose: {e}")
            print(f"Repository operation failed: {e}")
            return False
            
    except Exception as e:
        logger.error(f"Error in ensure_repo_and_purpose: {e}")
        print(f"Error in ensure_repo_and_purpose: {e}")
        return False
    finally:
        if 'db' in locals():
            db.close()

class UpdateFileInput(BaseModel):
    confab_id: int = Field(description="The ID of the confab to update file for")
    file_path: str = Field(description="The path of the file to update (e.g., PURPOSE.md, GUARDRAILS.md)")
    content: str = Field(description="The content to write to the file")

@tool(args_schema=UpdateFileInput)
def update_file_tool(confab_id: int, file_path: str, content: str) -> str:
    """Update a file in the GitHub repository and commit changes. This instruction is for updating any file and committing changes. Its primary objective is to facilitate the process of modifying or adding content to files in a structured manner within a project repository."""
    try:
        from database import get_db
        db = next(get_db())
        
        confab = db.query(Confab).filter(Confab.id == confab_id).first()
        if not confab:
            return "Confab not found"
            
        github_account = db.query(GitHubAccount).filter(GitHubAccount.user_id == confab.user_id).first()
        if not github_account:
            return "No GitHub account connected"
            
        confab_name = confab.name or f"confab-{confab_id}"
        repo_owner = github_account.selected_org or github_account.github_username
        repo_name = github_account.selected_repo
        
        # Use the existing update_purpose function for PURPOSE.md
        if file_path == "PURPOSE.md":
            success = update_purpose(confab_id, content)
            return "PURPOSE.md updated successfully" if success else "Failed to update PURPOSE.md"
        
        # For other files, use direct GitHub API
        try:
            from github import Github
            import datetime
            
            g = Github(github_account.access_token)
            repo = g.get_repo(f"{repo_owner}/{repo_name}")
            
            # Create or update file directly in main branch
            try:
                existing_file = repo.get_contents(file_path)
                repo.update_file(file_path, f"Update {file_path}", content, existing_file.sha)
                print(f"{file_path} updated successfully")
                return f"File {file_path} updated successfully"
            except:
                repo.create_file(file_path, f"Create {file_path}", content)
                print(f"{file_path} created successfully")
                return f"File {file_path} created successfully"
            
        except Exception as e:
            return f"Failed to update file: {str(e)}"
        
    except Exception as e:
        return f"Failed to update file: {str(e)}"
    finally:
        if 'db' in locals():
            db.close()

class CreateCommitInput(BaseModel):
    confab_id: int = Field(description="The ID of the confab to create commit for")
    file_path: str = Field(description="The path of the confab file to commit")
    content: str = Field(description="The content to commit")
    message: str = Field(default="Update confab file", description="Commit message")

@tool(args_schema=CreateCommitInput)
def create_commit_tool(confab_id: int, file_path: str, content: str, message: str = "Update confab file") -> str:
    """Create a commit for a confab file in the GitHub repository. This tool is designed for version control of confab files, allowing users to save progress and document changes in the project history."""
    return update_file_tool(confab_id, file_path, content)

class CreatePullRequestInput(BaseModel):
    confab_id: int = Field(description="The ID of the confab to create PR for")
    file_path: str = Field(description="The path of the confab file for the PR")
    content: str = Field(description="The content for the PR")
    title: str = Field(default="Confab File Update", description="PR title")

@tool(args_schema=CreatePullRequestInput)
def create_pull_request_tool(confab_id: int, file_path: str, content: str, title: str = "Confab File Update") -> str:
    """Create a pull request for confab file changes in the GitHub repository. This tool facilitates code review and collaboration by creating pull requests for proposed confab changes."""
    return update_file_tool(confab_id, file_path, content)

# Get all tools for LangGraph integration
def get_langchain_tools():
    """Return all available tools for LangGraph agent."""
    return [
        get_purpose_tool,
        update_purpose_tool,
        update_file_tool,
        create_commit_tool,
        create_pull_request_tool,
        store_user_information_tool,
        get_user_information_tool,
        search_knowledge_base_tool,
        update_knowledge_base_tool,
    ]

# Legacy setup step utilities (kept for backward compatibility)
def mark_step_complete(db: Session, confab_id: int, step: int) -> bool:
    """Record that the given configuration step has been finished on the confab."""
    confab = db.query(Confab).filter(Confab.id == confab_id).first()
    if not confab:
        return False
    cfg = confab.config or {}
    completed = cfg.get("setup_steps_completed", [])
    if step not in completed:
        completed.append(step)
    cfg["setup_steps_completed"] = completed
    confab.config = cfg
    db.commit()
    return True

def define_purpose(db: Session, confab_id: int, purpose_text: str) -> str:
    """Tool: save purpose and mark step 1."""
    update_purpose(confab_id, purpose_text)
    mark_step_complete(db, confab_id, 1)
    return "Purpose defined successfully."

def add_participant(db: Session, confab_id: int, email: str) -> str:
    """Tool: add a participant email (step 2)."""
    confab = db.query(Confab).filter(Confab.id == confab_id).first()
    if not confab:
        return "Confab not found."
    cfg = confab.config or {}
    parts = cfg.get("participants", [])
    if email not in parts:
        parts.append(email)
    cfg["participants"] = parts
    confab.config = cfg
    db.commit()
    mark_step_complete(db, confab_id, 2)
    return "Participant added."

def configure_memory(db: Session, confab_id: int, memory_notes: str, enable: bool = True) -> str:
    """Tool: configure memory settings (step 3)."""
    confab = db.query(Confab).filter(Confab.id == confab_id).first()
    if not confab:
        return "Confab not found."
    cfg = confab.config or {}
    if "conversation" not in cfg:
        cfg["conversation"] = {}
    cfg["conversation"]["memory_enabled"] = enable
    if "custom_settings" not in cfg:
        cfg["custom_settings"] = {}
    cfg["custom_settings"]["memory_notes"] = memory_notes
    confab.config = cfg
    db.commit()
    mark_step_complete(db, confab_id, 3)
    return "Memory configuration updated."

def add_tools_and_apis(db: Session, confab_id: int, tool_name: str, api_key: str) -> str:
    """Tool: register external tool/api (step 4)."""
    confab = db.query(Confab).filter(Confab.id == confab_id).first()
    if not confab:
        return "Confab not found."
    cfg = confab.config or {}
    integrations = cfg.get("integrations", {}).get("apis", [])
    integrations.append({"name": tool_name, "key": api_key})
    if "integrations" not in cfg:
        cfg["integrations"] = {}
    cfg["integrations"]["apis"] = integrations
    confab.config = cfg
    db.commit()
    mark_step_complete(db, confab_id, 4)
    return "Tool/API added."

def guardrails(db: Session, confab_id: int, guardrails_text: str) -> str:
    """Tool: record guardrails (step 5)."""
    confab = db.query(Confab).filter(Confab.id == confab_id).first()
    if not confab:
        return "Confab not found."
    cfg = confab.config or {}
    if "custom_settings" not in cfg:
        cfg["custom_settings"] = {}
    cfg["custom_settings"]["guardrails"] = guardrails_text
    confab.config = cfg
    db.commit()
    mark_step_complete(db, confab_id, 5)
    return "Guardrails saved."

def sample_io(db: Session, confab_id: int, sample_text: str) -> str:
    """Tool: save sample inputs/outputs (step 6)."""
    confab = db.query(Confab).filter(Confab.id == confab_id).first()
    if not confab:
        return "Confab not found."
    cfg = confab.config or {}
    if "custom_settings" not in cfg:
        cfg["custom_settings"] = {}
    cfg["custom_settings"]["sample_io"] = sample_text
    confab.config = cfg
    db.commit()
    mark_step_complete(db, confab_id, 6)
    return "Sample I/O recorded."

def review_and_save(db: Session, confab_id: int) -> str:
    """Tool: final review/save action (step 7)."""
    confab = db.query(Confab).filter(Confab.id == confab_id).first()
    if not confab:
        return "Confab not found."
    confab.status = "ready"
    db.commit()
    mark_step_complete(db, confab_id, 7)
    return "Review complete; confab marked ready."
