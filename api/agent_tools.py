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
            "description": "Store user information (name and email) in the confab's knowledge base.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "confab_id": {"type": "integer"},
                    "user_name": {"type": "string"},
                    "email": {"type": "string"}
                },
                "required": ["confab_id", "user_name", "email"]
            }
        },
        {
            "name": "get_user_information",
            "description": "Retrieve user information from the confab's knowledge base.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "confab_id": {"type": "integer"},
                    "email": {"type": "string"}
                },
                "required": ["confab_id"]
            }
        },
        # Document Store Tools
        {
            "name": "upload_document",
            "description": "Upload and index a document for RAG retrieval. Supports text, markdown, and PDF.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "confab_id": {"type": "integer", "description": "The confab to add the document to"},
                    "content": {"type": "string", "description": "Document content (text/markdown) or base64-encoded (PDF)"},
                    "filename": {"type": "string", "description": "Original filename with extension"},
                    "content_type": {"type": "string", "enum": ["text/plain", "text/markdown", "application/pdf"]},
                    "metadata": {"type": "object", "description": "Optional metadata (author, date, tags)"}
                },
                "required": ["confab_id", "content", "filename", "content_type"]
            }
        },
        {
            "name": "list_documents",
            "description": "List all documents in a confab's document store.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "confab_id": {"type": "integer", "description": "The confab ID"}
                },
                "required": ["confab_id"]
            }
        },
        {
            "name": "delete_document",
            "description": "Remove a document from the confab's document store.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "confab_id": {"type": "integer"},
                    "document_id": {"type": "integer", "description": "The document to delete"}
                },
                "required": ["confab_id", "document_id"]
            }
        },
        {
            "name": "search_documents",
            "description": "Semantic search across a confab's documents. Returns relevant chunks.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "confab_id": {"type": "integer"},
                    "query": {"type": "string", "description": "Search query (natural language)"},
                    "top_k": {"type": "integer", "default": 5, "description": "Number of results to return"},
                    "filter_type": {"type": "string", "enum": ["document", "learning"], "description": "Filter by source type"}
                },
                "required": ["confab_id", "query"]
            }
        },
        {
            "name": "get_context_for_query",
            "description": "Retrieve and format relevant document context for answering a user query. Combines search with context assembly for RAG.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "confab_id": {"type": "integer"},
                    "query": {"type": "string"},
                    "max_tokens": {"type": "integer", "default": 2000, "description": "Maximum context length"}
                },
                "required": ["confab_id", "query"]
            }
        },
        {
            "name": "reindex_documents",
            "description": "Re-index all documents in a confab (useful after embedding model change).",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "confab_id": {"type": "integer"}
                },
                "required": ["confab_id"]
            }
        },
        {
            "name": "sync_learnings",
            "description": "Index all approved learnings for a confab into the vector store.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "confab_id": {"type": "integer"}
                },
                "required": ["confab_id"]
            }
        },
        {
            "name": "clear_document_store",
            "description": "Delete all documents and vectors from a confab's store.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "confab_id": {"type": "integer"},
                    "confirm": {"type": "boolean", "description": "Must be true to execute"}
                },
                "required": ["confab_id", "confirm"]
            }
        },
        {
            "name": "get_guardrails",
            "description": "Get the guardrails markdown for a confab from GitHub repo's GUARDRAILS.md file or database.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "confab_id": {"type": "integer"}
                },
                "required": ["confab_id"]
            }
        },
        {
            "name": "update_guardrails",
            "description": "Update the guardrails markdown for a confab in GitHub repo's GUARDRAILS.md file and database.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "confab_id": {"type": "integer"},
                    "guardrails_markdown": {"type": "string"}
                },
                "required": ["confab_id", "guardrails_markdown"]
            }
        },
        {
            "name": "get_elicitation",
            "description": "Get the elicitation markdown for a confab from GitHub repo's ELICITATION.md file or database.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "confab_id": {"type": "integer"}
                },
                "required": ["confab_id"]
            }
        },
        {
            "name": "update_elicitation",
            "description": "Update the elicitation markdown for a confab in GitHub repo's ELICITATION.md file and database.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "confab_id": {"type": "integer"},
                    "elicitation_markdown": {"type": "string"}
                },
                "required": ["confab_id", "elicitation_markdown"]
            }
        },
        {
            "name": "get_tests",
            "description": "Get the tests markdown for a confab from GitHub repo's TESTS.md file or database.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "confab_id": {"type": "integer"}
                },
                "required": ["confab_id"]
            }
        },
        {
            "name": "update_tests",
            "description": "Update the tests markdown for a confab in GitHub repo's TESTS.md file and database.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "confab_id": {"type": "integer"},
                    "tests_markdown": {"type": "string"}
                },
                "required": ["confab_id", "tests_markdown"]
            }
        },
        {
            "name": "create_confab_folder",
            "description": "Create a confab folder structure in GitHub repository with confab name as folder.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "confab_id": {"type": "integer"}
                },
                "required": ["confab_id"]
            }
        }
    ]

@mcp.call_tool()
async def call_tool(name: str, arguments: dict):
    """Handle tool calls."""
    print(f"[TOOL CALL] Calling tool: {name} with arguments: {arguments}")
    if name == "get_purpose":
        result = get_purpose(arguments.get("confab_id"))
        print(f"[TOOL RESULT] get_purpose completed: {len(str(result))} characters returned")
        return {"content": [{"type": "text", "text": result or "No purpose found"}]}
    elif name == "update_purpose":
        success = update_purpose(arguments.get("confab_id"), arguments.get("purpose_markdown"))
        print(f"[TOOL RESULT] update_purpose completed: {success}")
        return {"content": [{"type": "text", "text": "Purpose updated successfully" if success else "Failed to update purpose"}]}
    elif name == "update_file_tool":
        result = update_file_tool(arguments.get("confab_id"), arguments.get("file_path"), arguments.get("content"))
        print(f"[TOOL RESULT] update_file_tool completed: {result}")
        return {"content": [{"type": "text", "text": result}]}
    elif name == "create_commit_tool":
        result = create_commit_tool(arguments.get("confab_id"), arguments.get("file_path"), arguments.get("content"), arguments.get("message", "Update file"))
        print(f"[TOOL RESULT] create_commit_tool completed: {result}")
        return {"content": [{"type": "text", "text": result}]}
    elif name == "create_pull_request_tool":
        result = create_pull_request_tool(arguments.get("confab_id"), arguments.get("file_path"), arguments.get("content"), arguments.get("title", "File Update"))
        print(f"[TOOL RESULT] create_pull_request_tool completed: {result}")
        return {"content": [{"type": "text", "text": result}]}
    elif name == "store_user_information":
        success = store_user_information(arguments.get("confab_id"), arguments.get("user_name"), arguments.get("email"))
        print(f"[TOOL RESULT] store_user_information completed: {success}")
        return {"content": [{"type": "text", "text": "User information stored successfully" if success else "Failed to store user information"}]}
    elif name == "get_user_information":
        results = get_user_information(arguments.get("confab_id"), arguments.get("email"))
        print(f"[TOOL RESULT] get_user_information completed: {len(results)} results")
        if results:
            if arguments.get("email") and len(results) == 1:
                user = results[0]
                return {"content": [{"type": "text", "text": f"Found user: {user.get('name', 'Unknown')} - {user.get('email', 'Unknown')}"}]}
            else:
                user_list = "\n".join([f"- {user.get('name', 'Unknown')}: {user.get('email', 'Unknown')}" for user in results])
                return {"content": [{"type": "text", "text": f"Found {len(results)} users:\n{user_list}"}]}
        else:
            return {"content": [{"type": "text", "text": "No user information found"}]}
    # Document Store Tools
    elif name == "upload_document":
        result = await upload_document_tool(
            arguments.get("confab_id"),
            arguments.get("content"),
            arguments.get("filename"),
            arguments.get("content_type"),
            arguments.get("metadata")
        )
        print(f"[TOOL RESULT] upload_document completed: {result}")
        return {"content": [{"type": "text", "text": result}]}
    elif name == "list_documents":
        result = await list_documents_tool(arguments.get("confab_id"))
        print(f"[TOOL RESULT] list_documents completed: {result}")
        return {"content": [{"type": "text", "text": result}]}
    elif name == "delete_document":
        result = await delete_document_tool(arguments.get("confab_id"), arguments.get("document_id"))
        print(f"[TOOL RESULT] delete_document completed: {result}")
        return {"content": [{"type": "text", "text": result}]}
    elif name == "search_documents":
        result = await search_documents_tool(
            arguments.get("confab_id"),
            arguments.get("query"),
            arguments.get("top_k", 5),
            arguments.get("filter_type")
        )
        print(f"[TOOL RESULT] search_documents completed: {result}")
        return {"content": [{"type": "text", "text": result}]}
    elif name == "get_context_for_query":
        result = await get_context_tool(
            arguments.get("confab_id"),
            arguments.get("query"),
            arguments.get("max_tokens", 2000)
        )
        print(f"[TOOL RESULT] get_context_for_query completed: {len(str(result))} characters returned")
        return {"content": [{"type": "text", "text": result}]}
    elif name == "reindex_documents":
        result = await reindex_documents_tool(arguments.get("confab_id"))
        print(f"[TOOL RESULT] reindex_documents completed: {result}")
        return {"content": [{"type": "text", "text": result}]}
    elif name == "sync_learnings":
        result = await sync_learnings_tool(arguments.get("confab_id"))
        print(f"[TOOL RESULT] sync_learnings completed: {result}")
        return {"content": [{"type": "text", "text": result}]}
    elif name == "clear_document_store":
        if not arguments.get("confirm"):
            print(f"[TOOL RESULT] clear_document_store aborted: confirmation required")
            return {"content": [{"type": "text", "text": "Confirm must be true to clear document store."}]}
        result = await clear_document_store_tool(arguments.get("confab_id"))
        print(f"[TOOL RESULT] clear_document_store completed: {result}")
        return {"content": [{"type": "text", "text": result}]}
    elif name == "get_guardrails":
        result = get_guardrails(arguments.get("confab_id"))
        print(f"[TOOL RESULT] get_guardrails completed: {len(str(result))} characters returned")
        return {"content": [{"type": "text", "text": result or "No guardrails found"}]}
    elif name == "update_guardrails":
        success = update_guardrails(arguments.get("confab_id"), arguments.get("guardrails_markdown"))
        print(f"[TOOL RESULT] update_guardrails completed: {success}")
        return {"content": [{"type": "text", "text": "Guardrails updated successfully" if success else "Failed to update guardrails"}]}
    elif name == "get_elicitation":
        result = get_elicitation(arguments.get("confab_id"))
        print(f"[TOOL RESULT] get_elicitation completed: {len(str(result))} characters returned")
        return {"content": [{"type": "text", "text": result or "No elicitation found"}]}
    elif name == "update_elicitation":
        success = update_elicitation(arguments.get("confab_id"), arguments.get("elicitation_markdown"))
        print(f"[TOOL RESULT] update_elicitation completed: {success}")
        return {"content": [{"type": "text", "text": "Elicitation updated successfully" if success else "Failed to update elicitation"}]}
    elif name == "get_tests":
        result = get_tests(arguments.get("confab_id"))
        print(f"[TOOL RESULT] get_tests completed: {len(str(result))} characters returned")
        return {"content": [{"type": "text", "text": result or "No tests found"}]}
    elif name == "update_tests":
        success = update_tests(arguments.get("confab_id"), arguments.get("tests_markdown"))
        print(f"[TOOL RESULT] update_tests completed: {success}")
        return {"content": [{"type": "text", "text": "Tests updated successfully" if success else "Failed to update tests"}]}
    elif name == "create_confab_folder":
        success = create_confab_folder_structure(arguments.get("confab_id"))
        print(f"[TOOL RESULT] create_confab_folder completed: {success}")
        return {"content": [{"type": "text", "text": "Confab folder created successfully" if success else "Failed to create confab folder"}]}
    else:
        print(f"[TOOL ERROR] Unknown tool: {name}")
        return {"content": [{"type": "text", "text": f"Unknown tool: {name}"}]}

def get_purpose(confab_id: int) -> Optional[str]:
    """Get the purpose markdown for a confab from GitHub repo's confabs/{confab.name}/PURPOSE.md file."""
    print("get_purpose working successfully")
    try:
        from database import get_db
        db = next(get_db())
        
        confab = db.query(Confab).filter(Confab.id == confab_id).first()
        if not confab:
            print(f"Confab with ID {confab_id} not found")
            return None
        
        # Ensure confab has a proper name
        confab_name = confab.name
        if not confab_name or confab_name.startswith("Agent Chat –"):
            print(f"Confab {confab_id} has improper name: {confab_name}")
            return None
            
        # Try to get from GitHub first (confabs/{confab.name}/PURPOSE.md)
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
                purpose_file_path = f"confabs/{confab_name}/PURPOSE.md"
                purpose_file = repo.get_contents(purpose_file_path)
                print(f"Successfully retrieved PURPOSE.md from {purpose_file_path}")
                return purpose_file.decoded_content.decode('utf-8')
            except Exception as e:
                logger.warning(f"Could not fetch PURPOSE.md from GitHub: {e}")
                print(f"GitHub access failed: {e}")
                # Try backward compatibility - check root PURPOSE.md
                try:
                    purpose_file = repo.get_contents("PURPOSE.md")
                    print("Successfully retrieved PURPOSE.md from root (backward compatibility)")
                    return purpose_file.decoded_content.decode('utf-8')
                except Exception as fallback_error:
                    print(f"Root PURPOSE.md also not found: {fallback_error}")
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

def get_guardrails(confab_id: int) -> Optional[str]:
    """Get the guardrails markdown for a confab from GitHub repo's confabs/{confab.name}/GUARDRAILS.md file."""
    print("get_guardrails working successfully")
    try:
        from database import get_db
        db = next(get_db())
        
        confab = db.query(Confab).filter(Confab.id == confab_id).first()
        if not confab:
            print(f"Confab with ID {confab_id} not found")
            return None
        
        # Ensure confab has a proper name
        confab_name = confab.name
        if not confab_name or confab_name.startswith("Agent Chat –"):
            print(f"Confab {confab_id} has improper name: {confab_name}")
            return None
            
        # Try to get from GitHub first (confabs/{confab.name}/GUARDRAILS.md)
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
                guardrails_file_path = f"confabs/{confab_name}/GUARDRAILS.md"
                guardrails_file = repo.get_contents(guardrails_file_path)
                print(f"Successfully retrieved GUARDRAILS.md from {guardrails_file_path}")
                return guardrails_file.decoded_content.decode('utf-8')
            except Exception as e:
                logger.warning(f"Could not fetch GUARDRAILS.md from GitHub: {e}")
                print(f"GitHub access failed: {e}")
                return None
        else:
            print("No GitHub account connected for this user")
            return None
        
    except Exception as e:
        logger.error(f"Error in get_guardrails: {e}")
        print(f"Error in get_guardrails: {e}")
        return None
    finally:
        if 'db' in locals():
            db.close()

def update_file_tool_function(confab_id: int, file_path: str, content: str) -> str:
    """Internal function to update a file in GitHub repository without LangChain tool wrapper."""
    try:
        from database import get_db
        from agent_runner import slugify
        db = next(get_db())
        
        confab = db.query(Confab).filter(Confab.id == confab_id).first()
        if not confab:
            return "Confab not found"
        
        # Ensure confab has a proper slugified name
        if not confab.name or confab.name.startswith("Agent Chat –"):
            return "Confab has invalid name. Please set a proper confab name first."
        
        # Ensure confab name is slugified
        confab_name = slugify(confab.name)
        if confab.name != confab_name:
            confab.name = confab_name
            db.commit()
            print(f"Updated confab name to slugified version: {confab_name}")
            
        github_account = db.query(GitHubAccount).filter(GitHubAccount.user_id == confab.user_id).first()
        if not github_account:
            return "No GitHub account connected"
            
        repo_owner = github_account.selected_org or github_account.github_username
        repo_name = github_account.selected_repo
        full_repo_name = f"{repo_owner}/{repo_name}"
        
        # For PURPOSE.md, ensure it goes to confabs/{confab_name}/PURPOSE.md
        if file_path == "PURPOSE.md":
            file_path = f"confabs/{confab_name}/PURPOSE.md"
            print(f"Set PURPOSE.md path to: {file_path}")
        # For other files, if they don't already include the confabs prefix, add it
        # Check if the path already starts with confabs/{confab_name}/ to prevent double prefixing
        elif not file_path.startswith(f"confabs/{confab_name}/"):
            original_path = file_path
            file_path = f"confabs/{confab_name}/{file_path}"
            print(f"Added confabs prefix to path: {original_path} -> {file_path}")
        else:
            print(f"Path already has confabs prefix: {file_path}")
        
        # Use the new branch-based workflow
        try:
            from github import Github
            
            g = Github(github_account.access_token)
            repo = g.get_repo(full_repo_name)
            
            # Create or get confab-specific branch
            branch_name = create_confab_branch(repo, confab_id)
            
            # Update/create file in the confab branch
            try:
                # Try to get file from the confab branch
                existing_file = repo.get_contents(file_path, ref=branch_name)
                repo.update_file(
                    file_path, 
                    f"Update {file_path} for confab {confab_name}", 
                    content, 
                    existing_file.sha,
                    branch=branch_name
                )
                print(f"{file_path} updated successfully in branch {branch_name}")
            except:
                # File might not exist in the branch, try to create it
                repo.create_file(
                    file_path, 
                    f"Create {file_path} for confab {confab_name}", 
                    content,
                    branch=branch_name
                )
                print(f"{file_path} created successfully in branch {branch_name}")
            
            # Handle pull request logic (similar to ensure_repo_and_purpose but for general files)
            existing_pr = check_pull_request_exists(repo, branch_name)
            if existing_pr:
                print(f"File updated in existing PR #{existing_pr.number}")
                return f"File {file_path} updated successfully in existing PR #{existing_pr.number}"
            else:
                # Create new PR for the file update
                pr = create_or_update_pull_request(repo, branch_name, confab_name, confab_id)
                if pr:
                    return f"File {file_path} updated successfully in new PR #{pr.number}"
                else:
                    return f"File {file_path} updated successfully but failed to create PR"
            
        except Exception as e:
            return f"Failed to update file: {str(e)}"
        
    except Exception as e:
        return f"Failed to update file: {str(e)}"
    finally:
        if 'db' in locals():
            db.close()

def update_guardrails(confab_id: int, guardrails_markdown: str) -> bool:
    """Update the guardrails markdown for a confab in GitHub repo's GUARDRAILS.md file."""
    print("update_guardrails working successfully")
    try:
        # Use the update_file_tool function directly to ensure proper GitHub integration
        result = update_file_tool_function(confab_id, "GUARDRAILS.md", guardrails_markdown)
        print(f"Guardrails update result: {result}")
        return "successfully" in result.lower()
    except Exception as e:
        logger.error(f"Error in update_guardrails: {e}")
        print(f"Error in update_guardrails: {e}")
        return False

def get_elicitation(confab_id: int) -> Optional[str]:
    """Get the elicitation markdown for a confab from GitHub repo's confabs/{confab.name}/ELICITATION.md file."""
    print("get_elicitation working successfully")
    try:
        from database import get_db
        db = next(get_db())
        
        confab = db.query(Confab).filter(Confab.id == confab_id).first()
        if not confab:
            print(f"Confab with ID {confab_id} not found")
            return None
        
        # Ensure confab has a proper name
        confab_name = confab.name
        if not confab_name or confab_name.startswith("Agent Chat –"):
            print(f"Confab {confab_id} has improper name: {confab_name}")
            return None
            
        # Try to get from GitHub first (confabs/{confab.name}/ELICITATION.md)
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
                elicitation_file_path = f"confabs/{confab_name}/ELICITATION.md"
                elicitation_file = repo.get_contents(elicitation_file_path)
                print(f"Successfully retrieved ELICITATION.md from {elicitation_file_path}")
                return elicitation_file.decoded_content.decode('utf-8')
            except Exception as e:
                logger.warning(f"Could not fetch ELICITATION.md from GitHub: {e}")
                print(f"GitHub access failed: {e}")
                return None
        else:
            print("No GitHub account connected for this user")
            return None
        
    except Exception as e:
        logger.error(f"Error in get_elicitation: {e}")
        print(f"Error in get_elicitation: {e}")
        return None
    finally:
        if 'db' in locals():
            db.close()

def update_elicitation(confab_id: int, elicitation_markdown: str) -> bool:
    """Update the elicitation markdown for a confab in GitHub repo's ELICITATION.md file."""
    print("update_elicitation working successfully")
    try:
        # Use the update_file_tool_function directly to ensure proper GitHub integration
        result = update_file_tool_function(confab_id, "ELICITATION.md", elicitation_markdown)
        print(f"Elicitation update result: {result}")
        return "successfully" in result.lower()
    except Exception as e:
        logger.error(f"Error in update_elicitation: {e}")
        print(f"Error in update_elicitation: {e}")
        return False

def get_tests(confab_id: int) -> Optional[str]:
    """Get the tests markdown for a confab from GitHub repo's confabs/{confab.name}/TESTS.md file."""
    print("get_tests working successfully")
    try:
        from database import get_db
        db = next(get_db())
        
        confab = db.query(Confab).filter(Confab.id == confab_id).first()
        if not confab:
            print(f"Confab with ID {confab_id} not found")
            return None
        
        # Ensure confab has a proper name
        confab_name = confab.name
        if not confab_name or confab_name.startswith("Agent Chat –"):
            print(f"Confab {confab_id} has improper name: {confab_name}")
            return None
            
        # Try to get from GitHub first (confabs/{confab.name}/TESTS.md)
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
                tests_file_path = f"confabs/{confab_name}/TESTS.md"
                tests_file = repo.get_contents(tests_file_path)
                print(f"Successfully retrieved TESTS.md from {tests_file_path}")
                return tests_file.decoded_content.decode('utf-8')
            except Exception as e:
                logger.warning(f"Could not fetch TESTS.md from GitHub: {e}")
                print(f"GitHub access failed: {e}")
                return None
        else:
            print("No GitHub account connected for this user")
            return None
        
    except Exception as e:
        logger.error(f"Error in get_tests: {e}")
        print(f"Error in get_tests: {e}")
        return None
    finally:
        if 'db' in locals():
            db.close()

def update_tests(confab_id: int, tests_markdown: str) -> bool:
    """Update the tests markdown for a confab in GitHub repo's TESTS.md file."""
    print("update_tests working successfully")
    try:
        # Use the update_file_tool_function directly to ensure proper GitHub integration
        result = update_file_tool_function(confab_id, "TESTS.md", tests_markdown)
        print(f"Tests update result: {result}")
        return "successfully" in result.lower()
    except Exception as e:
        logger.error(f"Error in update_tests: {e}")
        print(f"Error in update_tests: {e}")
        return False

def create_confab_folder_structure(confab_id: int) -> bool:
    """Create the confab folder structure in GitHub repository based on confab name."""
    print("create_confab_folder_structure working successfully")
    try:
        from database import get_db
        from agent_runner import slugify
        db = next(get_db())
        
        confab = db.query(Confab).filter(Confab.id == confab_id).first()
        if not confab:
            print(f"Confab with ID {confab_id} not found")
            return False
        
        # Ensure confab has a proper slugified name
        if not confab.name or confab.name.startswith("Agent Chat –"):
            print(f"Confab {confab_id} has invalid name: {confab.name}")
            return False
        
        # Ensure the confab name is slugified
        confab_name = slugify(confab.name)
        if confab.name != confab_name:
            confab.name = confab_name
            db.commit()
            print(f"Updated confab name to slugified version: {confab_name}")
            
        github_account = db.query(GitHubAccount).filter(GitHubAccount.user_id == confab.user_id).first()
        if not github_account:
            print("No GitHub account connected in create_confab_folder_structure")
            return False
            
        try:
            print(f"Creating confab folder structure for user {confab.user_id}")
            
            # Validate token before using it
            if not github_account.access_token:
                print("No GitHub access token found in create_confab_folder_structure")
                return False
            
            g = Github(github_account.access_token)
            
            # Test the token validity first
            try:
                user = g.get_user()
                print(f"GitHub token valid for user: {user.login}")
            except Exception as token_error:
                print(f"Invalid GitHub token in create_confab_folder_structure: {token_error}")
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
                return False
            
            # Create or get confab-specific branch
            branch_name = create_confab_branch(repo, confab_id)
            
            # Create the confab folder structure by creating a README.md file
            folder_readme_path = f"confabs/{confab_name}/README.md"
            readme_content = f"""# {confab_name}

This folder contains the configuration and documentation for the **{confab.name}** confab.

## Files

- **PURPOSE.md** - Defines the purpose and objectives of this confab
- **GUARDRAILS.md** - Safety constraints and behavioral boundaries
- **ELICITATION.md** - Requirements gathering and specification
- **TESTS.md** - Test scenarios and validation cases

## Generated

This confab structure was automatically generated by Let's Confab.
"""
            
            try:
                # Try to get file from the confab branch
                existing_file = repo.get_contents(folder_readme_path, ref=branch_name)
                repo.update_file(
                    folder_readme_path, 
                    f"Update confab folder README for {confab_name}", 
                    readme_content, 
                    existing_file.sha,
                    branch=branch_name
                )
                print(f"Confab folder README updated successfully in branch {branch_name}")
            except:
                # File might not exist in the branch, try to create it
                repo.create_file(
                    folder_readme_path, 
                    f"Create confab folder README for {confab_name}", 
                    readme_content,
                    branch=branch_name
                )
                print(f"Confab folder README created successfully in branch {branch_name}")
            
            # Create pull request for the folder structure
            pr = create_or_update_pull_request(repo, branch_name, confab_name, confab_id)
            if pr:
                import time
                time.sleep(2)
                safe_merge_pull_request(repo, pr)
                print(f"Confab folder structure created and PR merged successfully")
            else:
                print("Failed to create PR for confab folder structure")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error creating confab folder structure: {e}")
            print(f"Repository operation failed: {e}")
            return False
            
    except Exception as e:
        logger.error(f"Error in create_confab_folder_structure: {e}")
        print(f"Error in create_confab_folder_structure: {e}")
        return False
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

# Database tools for User Information Management (Email and Names)
def store_user_information(confab_id: int, user_name: str, email: str) -> bool:
    """Store user information (name and email) in the confab's knowledge base."""
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
            if user.get("email") == email:
                user["name"] = user_name  # Update name if email exists
                print(f"Updated existing user information for email: {email}")
                break
        else:
            # Add new user
            user_info.append({
                "name": user_name,
                "email": email,
                "created_at": datetime.datetime.now().isoformat()
            })
            print(f"Added new user information: {user_name} - {email}")
        
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

def get_user_information(confab_id: int, email: str = None) -> List[Dict[str, Any]]:
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
        
        if email:
            # Return specific user
            for user in user_info:
                if user.get("email") == email:
                    print(f"Found user information for email: {email}")
                    return [user]
            print(f"No user found with email: {email}")
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
    email: str = Field(description="The email of the user")

@tool(args_schema=StoreUserInformationInput)
def store_user_information_tool(confab_id: int, user_name: str, email: str) -> str:
    """Store user information (name and email) in the confab's knowledge base."""
    success = store_user_information(confab_id, user_name, email)
    return "User information stored successfully" if success else "Failed to store user information"

class GetUserInformationInput(BaseModel):
    confab_id: int = Field(description="The ID of the confab to search in")
    email: Optional[str] = Field(default=None, description="The email to search for (optional)")

@tool(args_schema=GetUserInformationInput)
def get_user_information_tool(confab_id: int, email: str = None) -> str:
    """Retrieve user information from the confab's knowledge base."""
    results = get_user_information(confab_id, email)
    if results:
        if email and len(results) == 1:
            user = results[0]
            return f"Found user: {user.get('name', 'Unknown')} - {user.get('email', 'Unknown')}"
        else:
            return f"Found {len(results)} users:\n" + "\n".join([f"- {user.get('name', 'Unknown')}: {user.get('email', 'Unknown')}" for user in results])
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

def handle_branch_deleted(repo, branch_name: str, confab_id: int) -> str:
    """Handle case where branch was deleted - recreate it."""
    print(f"Branch {branch_name} was deleted, recreating it")
    try:
        # Get default branch and recreate the confab branch
        default_branch = repo.default_branch
        source_branch = repo.get_branch(default_branch)
        
        repo.create_git_ref(
            ref=f'refs/heads/{branch_name}',
            sha=source_branch.commit.sha
        )
        print(f"Recreated branch {branch_name} from {default_branch}")
        return branch_name
    except Exception as e:
        print(f"Failed to recreate branch {branch_name}: {e}")
        raise e

def handle_merge_conflicts(repo, pr) -> bool:
    """Handle merge conflicts by updating PR body with conflict information."""
    try:
        if not pr.mergeable:
            # Check if there are conflicts
            if pr.mergeable_state == "dirty":
                conflict_message = f"""
⚠️ **Merge Conflicts Detected**

This pull request has merge conflicts that need to be resolved manually.

**Conflicting files:**
- Please check the Files Changed tab to see conflicts
- Resolve conflicts locally or in GitHub UI
- Update the branch with conflict resolution

**Branch:** {pr.head.ref}
**Base Branch:** {pr.base.ref}

Once conflicts are resolved, this PR can be merged automatically.
"""
                pr.create_issue_comment(conflict_message)
                print(f"Added conflict comment to PR #{pr.number}")
                return False
        return True
    except Exception as e:
        print(f"Error handling merge conflicts: {e}")
        return False

def check_branch_exists(repo, branch_name: str) -> bool:
    """Check if a branch exists in the repository."""
    try:
        repo.get_branch(branch_name)
        return True
    except:
        return False

def check_pull_request_exists(repo, branch_name: str) -> Optional[Any]:
    """Check if there's an open pull request for the given branch."""
    try:
        pulls = repo.get_pulls(state='open', head=branch_name)
        for pr in pulls:
            if pr.head.ref == branch_name:
                return pr
        return None
    except:
        return None

def create_confab_branch(repo, confab_id: int) -> str:
    """Create or get the confab-specific branch with edge case handling."""
    branch_name = f"confab-{confab_id}"
    
    try:
        if check_branch_exists(repo, branch_name):
            print(f"Branch {branch_name} already exists")
            return branch_name
        
        # Get default branch
        default_branch = repo.default_branch
        source_branch = repo.get_branch(default_branch)
        
        # Create new branch from default
        repo.create_git_ref(
            ref=f'refs/heads/{branch_name}',
            sha=source_branch.commit.sha
        )
        print(f"Created branch {branch_name} from {default_branch}")
        return branch_name
        
    except Exception as e:
        print(f"Error creating branch {branch_name}: {e}")
        # Try to handle the case where branch might have been deleted
        try:
            return handle_branch_deleted(repo, branch_name, confab_id)
        except Exception as fallback_error:
            print(f"Failed to handle branch creation error: {fallback_error}")
            raise e

def create_or_update_pull_request(repo, branch_name: str, confab_name: str, confab_id: int) -> Optional[Any]:
    """Create a new PR or update existing one."""
    # Check if PR already exists
    existing_pr = check_pull_request_exists(repo, branch_name)
    
    if existing_pr:
        print(f"PR already exists: #{existing_pr.number}")
        return existing_pr
    
    # Create new PR
    try:
        pr = repo.create_pull(
            title=f"Update confab {confab_name} (ID: {confab_id})",
            body=f"Automated update for confab {confab_name} (ID: {confab_id})\n\nChanges made in the confabs/{confab_name}/ directory.",
            head=branch_name,
            base=repo.default_branch
        )
        print(f"Created PR #{pr.number}")
        return pr
    except Exception as e:
        print(f"Failed to create PR: {e}")
        return None

def safe_merge_pull_request(repo, pr) -> bool:
    """Safely merge a pull request if possible, with conflict handling."""
    try:
        # Refresh PR status
        pr.update()
        
        if not pr.mergeable:
            print(f"PR #{pr.number} is not mergeable (state: {pr.mergeable_state})")
            # Handle merge conflicts
            if not handle_merge_conflicts(repo, pr):
                return False
            
            # Wait a moment and check again
            import time
            time.sleep(3)
            pr.update()
            
            if not pr.mergeable:
                print(f"PR #{pr.number} still not mergeable after conflict handling")
                return False
        
        # Attempt merge
        result = pr.merge()
        if result.merged:
            print(f"Successfully merged PR #{pr.number}")
            return True
        else:
            print(f"Failed to merge PR #{pr.number}: {result.message}")
            return False
            
    except Exception as e:
        print(f"Error merging PR: {e}")
        return False

def ensure_repo_and_purpose(confab_id: int, purpose_markdown: str) -> bool:
    """Ensure repository exists and purpose.md file is created using confab-specific branch workflow."""
    try:
        from database import get_db
        from confab_manager import create_github_repository
        from agent_runner import slugify
        db = next(get_db())
        
        confab = db.query(Confab).filter(Confab.id == confab_id).first()
        if not confab:
            print(f"Confab with ID {confab_id} not found in ensure_repo_and_purpose")
            return False
        
        # Ensure confab has a proper slugified name
        if not confab.name or confab.name.startswith("Agent Chat –"):
            print(f"Confab {confab_id} has invalid name: {confab.name}")
            return False
        
        # Ensure the confab name is slugified
        confab_name = slugify(confab.name)
        if confab.name != confab_name:
            confab.name = confab_name
            db.commit()
            print(f"Updated confab name to slugified version: {confab_name}")
            
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
            
            # Create or get confab-specific branch
            branch_name = create_confab_branch(repo, confab_id)
            
            # Check if this is the first time creating PURPOSE.md for this confab
            purpose_file_path = f"confabs/{confab_name}/PURPOSE.md"
            is_first_time = False
            
            try:
                # Try to get file from main branch to check if it exists
                main_file = repo.get_contents(purpose_file_path, ref=repo.default_branch)
                print(f"PURPOSE.md already exists in main branch")
            except:
                print(f"PURPOSE.md does not exist in main branch - first time creation")
                is_first_time = True
            
            # Update/create file in the confab branch
            try:
                # Try to get file from the confab branch
                file = repo.get_contents(purpose_file_path, ref=branch_name)
                repo.update_file(
                    purpose_file_path, 
                    f"Update purpose for confab {confab_name}", 
                    purpose_markdown, 
                    file.sha,
                    branch=branch_name
                )
                print(f"PURPOSE.md updated successfully in branch {branch_name}")
            except Exception as file_error:
                # File might not exist in the branch, try to create it
                try:
                    repo.create_file(
                        purpose_file_path, 
                        f"Create purpose for confab {confab_name}", 
                        purpose_markdown,
                        branch=branch_name
                    )
                    print(f"PURPOSE.md created successfully in branch {branch_name}")
                except Exception as create_file_error:
                    print(f"Failed to create PURPOSE.md at {purpose_file_path}: {create_file_error}")
                    return False
            
            # Handle pull request logic
            if is_first_time:
                # First time - create PR and merge
                print("First time creation - creating PR and merging")
                pr = create_or_update_pull_request(repo, branch_name, confab_name, confab_id)
                if pr:
                    # Wait a moment for PR to be processed
                    import time
                    time.sleep(2)
                    safe_merge_pull_request(repo, pr)
                else:
                    print("Failed to create PR for first-time setup")
                    return False
            else:
                # Subsequent updates - check if PR exists and is open
                existing_pr = check_pull_request_exists(repo, branch_name)
                if existing_pr:
                    print(f"Updating existing PR #{existing_pr.number}")
                    # PR exists and is open, no need to create new one
                else:
                    # Check if there was a merged PR for this branch
                    try:
                        pulls = repo.get_pulls(state='closed', head=branch_name)
                        merged_pr_found = False
                        for pr in pulls:
                            if pr.head.ref == branch_name and pr.merged:
                                merged_pr_found = True
                                break
                        
                        if merged_pr_found:
                            print("Previous PR was merged, creating new PR for updates")
                            pr = create_or_update_pull_request(repo, branch_name, confab_name, confab_id)
                            if pr:
                                import time
                                time.sleep(2)
                                safe_merge_pull_request(repo, pr)
                        else:
                            print("No existing PR found and no merged PR - creating new PR")
                            pr = create_or_update_pull_request(repo, branch_name, confab_name, confab_id)
                            
                    except Exception as pr_check_error:
                        print(f"Error checking PR history: {pr_check_error}")
                        # Fallback: create new PR
                        pr = create_or_update_pull_request(repo, branch_name, confab_name, confab_id)
                
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
    """Update a file in GitHub repository using confab-specific branch workflow. This instruction is for updating any file and committing changes. Its primary objective is to facilitate the process of modifying or adding content to files in a structured manner within a project repository."""
    try:
        from database import get_db
        from agent_runner import slugify
        db = next(get_db())
        
        confab = db.query(Confab).filter(Confab.id == confab_id).first()
        if not confab:
            return "Confab not found"
        
        # Ensure confab has a proper slugified name
        if not confab.name or confab.name.startswith("Agent Chat –"):
            return "Confab has invalid name. Please set a proper confab name first."
        
        # Ensure confab name is slugified
        confab_name = slugify(confab.name)
        if confab.name != confab_name:
            confab.name = confab_name
            db.commit()
            print(f"Updated confab name to slugified version: {confab_name}")
            
        github_account = db.query(GitHubAccount).filter(GitHubAccount.user_id == confab.user_id).first()
        if not github_account:
            return "No GitHub account connected"
            
        repo_owner = github_account.selected_org or github_account.github_username
        repo_name = github_account.selected_repo
        full_repo_name = f"{repo_owner}/{repo_name}"
        
        # For PURPOSE.md, ensure it goes to confabs/{confab_name}/PURPOSE.md
        if file_path == "PURPOSE.md":
            file_path = f"confabs/{confab_name}/PURPOSE.md"
            print(f"Set PURPOSE.md path to: {file_path}")
        # For other files, if they don't already include the confabs prefix, add it
        # Check if the path already starts with confabs/{confab_name}/ to prevent double prefixing
        elif not file_path.startswith(f"confabs/{confab_name}/"):
            original_path = file_path
            file_path = f"confabs/{confab_name}/{file_path}"
            print(f"Added confabs prefix to path: {original_path} -> {file_path}")
        else:
            print(f"Path already has confabs prefix: {file_path}")
        
        # Use the new branch-based workflow
        try:
            from github import Github
            
            g = Github(github_account.access_token)
            repo = g.get_repo(full_repo_name)
            
            # Create or get confab-specific branch
            branch_name = create_confab_branch(repo, confab_id)
            
            # Update/create file in the confab branch
            try:
                # Try to get file from the confab branch
                existing_file = repo.get_contents(file_path, ref=branch_name)
                repo.update_file(
                    file_path, 
                    f"Update {file_path} for confab {confab_name}", 
                    content, 
                    existing_file.sha,
                    branch=branch_name
                )
                print(f"{file_path} updated successfully in branch {branch_name}")
            except:
                # File might not exist in the branch, try to create it
                repo.create_file(
                    file_path, 
                    f"Create {file_path} for confab {confab_name}", 
                    content,
                    branch=branch_name
                )
                print(f"{file_path} created successfully in branch {branch_name}")
            
            # Handle pull request logic (similar to ensure_repo_and_purpose but for general files)
            existing_pr = check_pull_request_exists(repo, branch_name)
            if existing_pr:
                print(f"File updated in existing PR #{existing_pr.number}")
                return f"File {file_path} updated successfully in existing PR #{existing_pr.number}"
            else:
                # Create new PR for the file update
                pr = create_or_update_pull_request(repo, branch_name, confab_name, confab_id)
                if pr:
                    return f"File {file_path} updated successfully in new PR #{pr.number}"
                else:
                    return f"File {file_path} updated successfully but failed to create PR"
            
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

class GetGuardrailsInput(BaseModel):
    confab_id: int = Field(description="The ID of the confab to get guardrails for")

@tool(args_schema=GetGuardrailsInput)
def get_guardrails_tool(confab_id: int) -> str:
    """Get the guardrails for a confab from GitHub repo or database."""
    result = get_guardrails(confab_id)
    return result or "No guardrails found"

class UpdateGuardrailsInput(BaseModel):
    confab_id: int = Field(description="The ID of the confab to update guardrails for")
    guardrails_markdown: str = Field(description="The guardrails markdown content")

@tool(args_schema=UpdateGuardrailsInput)
def update_guardrails_tool(confab_id: int, guardrails_markdown: str) -> str:
    """Update the guardrails for a confab in GitHub repo and database."""
    success = update_guardrails(confab_id, guardrails_markdown)
    return "Guardrails updated successfully" if success else "Failed to update guardrails"

class GetElicitationInput(BaseModel):
    confab_id: int = Field(description="The ID of the confab to get elicitation for")

@tool(args_schema=GetElicitationInput)
def get_elicitation_tool(confab_id: int) -> str:
    """Get the elicitation for a confab from GitHub repo or database."""
    result = get_elicitation(confab_id)
    return result or "No elicitation found"

class UpdateElicitationInput(BaseModel):
    confab_id: int = Field(description="The ID of the confab to update elicitation for")
    elicitation_markdown: str = Field(description="The elicitation markdown content")

@tool(args_schema=UpdateElicitationInput)
def update_elicitation_tool(confab_id: int, elicitation_markdown: str) -> str:
    """Update the elicitation for a confab in GitHub repo and database."""
    success = update_elicitation(confab_id, elicitation_markdown)
    return "Elicitation updated successfully" if success else "Failed to update elicitation"

class GetTestsInput(BaseModel):
    confab_id: int = Field(description="The ID of the confab to get tests for")

@tool(args_schema=GetTestsInput)
def get_tests_tool(confab_id: int) -> str:
    """Get the tests for a confab from GitHub repo or database."""
    result = get_tests(confab_id)
    return result or "No tests found"

class UpdateTestsInput(BaseModel):
    confab_id: int = Field(description="The ID of the confab to update tests for")
    tests_markdown: str = Field(description="The tests markdown content")

@tool(args_schema=UpdateTestsInput)
def update_tests_tool(confab_id: int, tests_markdown: str) -> str:
    """Update the tests for a confab in GitHub repo and database."""
    success = update_tests(confab_id, tests_markdown)
    return "Tests updated successfully" if success else "Failed to update tests"

class CreateConfabFolderInput(BaseModel):
    confab_id: int = Field(description="The ID of the confab to create folder structure for")

@tool(args_schema=CreateConfabFolderInput)
def create_confab_folder_tool(confab_id: int) -> str:
    """Create the confab folder structure in GitHub repository."""
    success = create_confab_folder_structure(confab_id)
    return "Confab folder created successfully" if success else "Failed to create confab folder"

# Get all tools for LangGraph integration
def get_langchain_tools():
    """Return all available tools for LangGraph agent."""
    return [
        get_purpose_tool,
        update_purpose_tool,
        get_guardrails_tool,
        update_guardrails_tool,
        get_elicitation_tool,
        update_elicitation_tool,
        get_tests_tool,
        update_tests_tool,
        create_confab_folder_tool,
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

def set_confab_name(db: Session, confab_id: int, name: str) -> str:
    """Tool: set a descriptive placeholder name for the confab.

    The name should be short (1-2 words) and descriptive of the agent's purpose.
    A timestamp suffix will be added automatically if not present.
    """
    confab = db.query(Confab).filter(Confab.id == confab_id).first()
    if not confab:
        return "Confab not found."

    # Add timestamp suffix if not already present (format: -YYYYMMDD-HHMM)
    if not any(c.isdigit() for c in name[-8:]):
        timestamp = datetime.datetime.now().strftime("-%Y%m%d-%H%M")
        name = f"{name}{timestamp}"

    confab.name = name
    db.commit()
    logger.info(f"Set confab {confab_id} name to: {name}")
    return f"Confab name set to: {name}"


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


# =============================================================================
# Document Store Tools
# =============================================================================

def _get_document_service():
    """Get a DocumentService instance with a database session."""
    from database import SessionLocal
    from document_store import DocumentService
    db = SessionLocal()
    return DocumentService(db), db


async def upload_document_tool(
    confab_id: int,
    content: str,
    filename: str,
    content_type: str,
    metadata: dict = None
) -> str:
    """Upload and index a document for RAG retrieval."""
    try:
        service, db = _get_document_service()
        result = await service.upload_document(
            confab_id=confab_id,
            content=content,
            filename=filename,
            content_type=content_type,
            metadata=metadata
        )
        db.close()

        if result.status == "indexed":
            return f"Document '{filename}' uploaded successfully with {result.chunk_count} chunks."
        elif result.status == "duplicate":
            return f"Document already exists (duplicate content detected)."
        else:
            return f"Failed to upload document: {result.error_message}"
    except Exception as e:
        logger.error(f"Error uploading document: {e}")
        return f"Error uploading document: {str(e)}"


async def list_documents_tool(confab_id: int) -> str:
    """List all documents in a confab's document store."""
    try:
        service, db = _get_document_service()
        docs = await service.list_documents(confab_id)
        db.close()

        if not docs:
            return "No documents found in this confab's document store."

        lines = [f"Found {len(docs)} document(s):"]
        for doc in docs:
            status_icon = "✓" if doc["status"] == "indexed" else "⏳" if doc["status"] == "pending" else "✗"
            lines.append(f"  {status_icon} [{doc['id']}] {doc['filename']} ({doc['chunk_count']} chunks)")
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Error listing documents: {e}")
        return f"Error listing documents: {str(e)}"


async def delete_document_tool(confab_id: int, document_id: int) -> str:
    """Remove a document from the confab's document store."""
    try:
        service, db = _get_document_service()
        success = await service.delete_document(confab_id, document_id)
        db.close()

        if success:
            return f"Document {document_id} deleted successfully."
        else:
            return f"Document {document_id} not found."
    except Exception as e:
        logger.error(f"Error deleting document: {e}")
        return f"Error deleting document: {str(e)}"


async def search_documents_tool(
    confab_id: int,
    query: str,
    top_k: int = 5,
    filter_type: str = None
) -> str:
    """Semantic search across a confab's documents."""
    try:
        service, db = _get_document_service()
        results = await service.search(confab_id, query, top_k, filter_type)
        db.close()

        if not results:
            return "No relevant documents found for this query."

        lines = [f"Found {len(results)} relevant chunk(s):"]
        for r in results:
            score_pct = int(r.score * 100)
            preview = r.content[:100] + "..." if len(r.content) > 100 else r.content
            lines.append(f"\n[{r.source_type}] {r.filename} (score: {score_pct}%)")
            lines.append(f"  {preview}")
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Error searching documents: {e}")
        return f"Error searching documents: {str(e)}"


async def get_context_tool(confab_id: int, query: str, max_tokens: int = 2000) -> str:
    """Get formatted context for RAG."""
    try:
        service, db = _get_document_service()
        result = await service.get_context_for_query(confab_id, query, max_tokens)
        db.close()

        if not result.context:
            return "No relevant context found for this query."

        # Return just the context for RAG use
        return result.context
    except Exception as e:
        logger.error(f"Error getting context: {e}")
        return f"Error getting context: {str(e)}"


async def reindex_documents_tool(confab_id: int) -> str:
    """Re-index all documents for a confab."""
    try:
        service, db = _get_document_service()
        count = await service.reindex_documents(confab_id)
        db.close()
        return f"Re-indexed {count} document(s) for confab {confab_id}."
    except Exception as e:
        logger.error(f"Error reindexing documents: {e}")
        return f"Error reindexing documents: {str(e)}"


async def sync_learnings_tool(confab_id: int) -> str:
    """Index all approved learnings for a confab."""
    try:
        service, db = _get_document_service()
        count = await service.sync_learnings(confab_id)
        db.close()
        return f"Indexed {count} learning(s) for confab {confab_id}."
    except Exception as e:
        logger.error(f"Error syncing learnings: {e}")
        return f"Error syncing learnings: {str(e)}"


async def clear_document_store_tool(confab_id: int) -> str:
    """Delete all documents and vectors for a confab."""
    try:
        service, db = _get_document_service()
        success = await service.clear_document_store(confab_id)
        db.close()

        if success:
            return f"Document store cleared for confab {confab_id}."
        else:
            return "Failed to clear document store."
    except Exception as e:
        logger.error(f"Error clearing document store: {e}")
        return f"Error clearing document store: {str(e)}"
