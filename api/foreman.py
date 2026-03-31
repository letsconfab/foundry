"""
Foreman Agent - Top-level orchestrator for confabs in 'building' status
Handles context loading, resume prompts, and proactive conversation guidance.
"""

import logging
import json
import re
from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy.orm import Session

from models import Confab, GitHubAccount
from context_loader import ContextLoader, ForemanContext
from resume_generator import ResumePromptGenerator, STAGE_PROMPTS, STEP_DESCRIPTIONS
from llm_service import ask_llm
from document_store.service import DocumentService

# Import tool functions at module level (not runtime)
from agent_tools import (
    define_purpose, add_participant, configure_memory,
    add_tools_and_apis, guardrails, sample_io, review_and_save,
    update_purpose, set_confab_name
)

logger = logging.getLogger(__name__)

# Tools registry - maps tool names to functions
# Tools that require db session are marked with requires_db=True
SETUP_TOOLS = {
    "set_confab_name": {"fn": set_confab_name, "requires_db": True},
    "define_purpose": {"fn": define_purpose, "requires_db": True},
    "add_participant": {"fn": add_participant, "requires_db": True},
    "configure_memory": {"fn": configure_memory, "requires_db": True},
    "add_tools_and_apis": {"fn": add_tools_and_apis, "requires_db": True},
    "guardrails": {"fn": guardrails, "requires_db": True},
    "sample_io": {"fn": sample_io, "requires_db": True},
    "review_and_save": {"fn": review_and_save, "requires_db": True},
    "update_purpose": {"fn": update_purpose, "requires_db": False},  # Different signature
}


# System prompt for the Foreman agent
FOREMAN_SYSTEM_PROMPT = """You are the Foreman, the lead orchestrator in the Agent Foundry. You guide users through building AI agents (called "confabs").

IMPORTANT: You must actively lead this conversation. Do not wait passively for the user to drive the process. After each user response, acknowledge what they said, save the relevant information, then proactively move to the next step.

## The 7-Step Process
1. **Define purpose** - What should the agent do? (CURRENT FOCUS if just starting)
2. **Add participants** - Who can access it?
3. **Configure memory** - Should it remember conversations?
4. **Set up tools** - What external capabilities does it need?
5. **Establish guardrails** - What are its safety boundaries?
6. **Sample I/O** - Provide example interactions
7. **Review** - Finalize the configuration

## Naming the Confab
IMPORTANT: After the user describes what their agent should do (step 1), you MUST generate a short placeholder name.
- The name should be 1-2 words, descriptive of the agent's purpose
- Examples: "SupportBot", "DataAnalyzer", "CodeReviewer", "MeetingSummarizer"
- Use the set_confab_name tool to save it: {{"tool": "set_confab_name", "args": {{"name": "YourChosenName"}}}}
- A timestamp will be added automatically (e.g., "SupportBot-20260326-1430")
- The user can change this name later via the UI

## Your Behavior
- LEAD the conversation - always end your response with a clear question for the next step
- Focus on ONE step at a time - don't overwhelm the user
- After receiving information, briefly confirm what you understood, then IMMEDIATELY ask about the next step
- Keep responses concise and action-oriented
- If the user's response is vague, ask ONE specific clarifying question
- If the user wants to skip a step, acknowledge it and move to the next step
- When all steps are complete, summarize the configuration and confirm they're ready to save

## Response Format
1. Brief acknowledgment of what the user said (1-2 sentences)
2. Confirmation of what you're saving/recording (if applicable)
3. Clear transition to the next step with a specific question

## Document Uploads
When the user uploads documents, they are automatically chunked and indexed into the confab's knowledge base (ChromaDB vector store). You should:
- Acknowledge when documents are uploaded and indexed
- Mention the document name and chunk count when relevant
- Explain that these documents will be available to the confab for RAG retrieval once it's deployed

{documents_context}

Current confab context:
{context}

Current stage: {current_stage}
Completed steps: {completed_steps}
"""


class Foreman:
    """Top-level orchestrator for building confabs."""

    def __init__(self, confab_id: int, db: Session):
        self.confab_id = confab_id
        self.db = db
        self.confab: Optional[Confab] = None
        self.context: Optional[ForemanContext] = None
        self.initialized = False

    async def initialize(self) -> bool:
        """
        Load confab and validate status == 'building'.
        Returns True if initialization successful, False otherwise.
        """
        # Load confab
        self.confab = self.db.query(Confab).filter(
            Confab.id == self.confab_id
        ).first()

        if not self.confab:
            logger.error(f"Confab {self.confab_id} not found")
            return False

        # Validate status
        if self.confab.status != "building":
            logger.warning(f"Confab {self.confab_id} has status '{self.confab.status}', expected 'building'")
            return False

        # Load full context
        loader = ContextLoader(self.db)
        self.context = await loader.load_full_context(self.confab)

        self.initialized = True
        logger.info(f"Foreman initialized for confab {self.confab_id}")
        return True

    async def generate_resume_prompt(self) -> Dict[str, Any]:
        """
        Generate a resume prompt based on current context.
        Returns ForemanChatResponse-compatible dict.
        """
        if not self.initialized:
            raise RuntimeError("Foreman not initialized. Call initialize() first.")

        generator = ResumePromptGenerator(self.context)
        resume_text = generator.generate()

        # Store resume as assistant message if we have a thread
        thread_id = self.context.thread_id
        if thread_id:
            resume_msg = Message(
                thread_id=thread_id,
                content=resume_text,
                role="assistant",
                sender_type="system",
                sender_name="Foreman",
            )
            self.db.add(resume_msg)
            self.db.commit()
            self.db.refresh(resume_msg)

        return {
            "response": resume_text,
            "confab_id": self.confab_id,
            "thread_id": thread_id,
            "is_resume": True,
            "setup_progress": {
                "completed_steps": self.context.setup_progress.completed_steps,
                "current_stage": self.context.setup_progress.current_stage,
                "total_steps": self.context.setup_progress.total_steps,
                "remaining_steps": self.context.setup_progress.remaining_steps
            },
            "timestamp": datetime.now().isoformat()
        }

    async def process_message(self, user_message: str) -> Dict[str, Any]:
        """
        Process a user message through the Foreman.
        Returns ForemanChatResponse-compatible dict.

        NOTE: This method only generates the response. It does NOT save messages
        to the database. The /chat endpoint in main.py handles all message
        persistence to avoid duplicate messages.
        """
        if not self.initialized:
            raise RuntimeError("Foreman not initialized. Call initialize() first.")

        # Check if user is confirming purpose (Yes response)
        if self._is_purpose_confirmed(user_message):
            # Auto-trigger spec generation workflow
            return await self._auto_generate_spec_workflow(user_message)

        # Build contextual prompt (uses thread history from context)
        prompt = await self._build_contextual_prompt(user_message)

        # Call LLM
        try:
            response = await ask_llm(prompt, temperature=0.7)
        except Exception as e:
            logger.error(f"LLM error: {e}")
            response = f"I apologize, but I encountered an error processing your request. Please try again."

        # Parse for tool calls (optional enhancement)
        tool_calls = self._parse_tool_calls(response)
        if tool_calls:
            # Execute tools and get enriched response
            response = await self._execute_tools_and_respond(tool_calls, response, user_message)

        # Update progress if needed
        await self._update_progress_from_response(user_message, response)

        return {
            "response": response,
            "confab_id": self.confab_id,
            "is_resume": False,
            "setup_progress": {
                "completed_steps": self.context.setup_progress.completed_steps,
                "current_stage": self.context.setup_progress.current_stage,
                "total_steps": self.context.setup_progress.total_steps,
                "remaining_steps": self.context.setup_progress.remaining_steps
            },
            "tool_calls": tool_calls,
            "timestamp": datetime.now().isoformat(),
        }

    async def _get_documents_context(self) -> str:
        """Get formatted context about uploaded documents for this confab."""
        try:
            doc_service = DocumentService(self.db)
            documents = await doc_service.list_documents(self.confab_id)

            if not documents:
                return "No documents have been uploaded to this confab yet."

            doc_lines = [f"**Uploaded Documents ({len(documents)}):**"]
            for doc in documents:
                doc_lines.append(f"- {doc['filename']} ({doc['content_type']}, {doc['chunk_count']} chunks, status: {doc['status']})")

            return "\n".join(doc_lines)
        except Exception as e:
            logger.warning(f"Failed to load documents for confab {self.confab_id}: {e}")
            return "Unable to load document information."

    async def _build_contextual_prompt(self, user_message: str) -> str:
        """Build a prompt with full context for the LLM."""
        # Get system context from GitHub files
        generator = ResumePromptGenerator(self.context)
        system_context = generator.get_system_context()

        # Get document context
        documents_context = await self._get_documents_context()

        # Build conversation history (last 10 messages)
        history_lines = []
        for msg in self.context.thread_history[-10:]:
            role = "User" if msg.role == "user" else "Assistant"
            history_lines.append(f"{role}: {msg.content}")

        history_text = "\n".join(history_lines) if history_lines else "No previous messages."

        # Format system prompt
        system_prompt = FOREMAN_SYSTEM_PROMPT.format(
            context=system_context,
            current_stage=self.context.setup_progress.current_stage,
            completed_steps=self.context.setup_progress.completed_steps,
            documents_context=documents_context
        )

        # Combine into final prompt
        return f"""{system_prompt}

## Recent Conversation History
{history_text}

## Current User Message
User: {user_message}

Respond helpfully as the Foreman. Guide the user through building their agent."""

    def _parse_tool_calls(self, response: str) -> List[Dict[str, Any]]:
        """Parse tool calls from LLM response (JSON embedded in text)."""
        tool_calls = []

        # Look for JSON tool call pattern: {"tool": "...", "args": {...}}
        json_pattern = r'\{["\']tool["\']\s*:\s*["\'](\w+)["\'].*?\}'
        matches = re.findall(json_pattern, response, re.DOTALL)

        for match in matches:
            try:
                # Try to extract full JSON object
                start = response.find('{"tool"')
                if start == -1:
                    start = response.find("{'tool")
                if start != -1:
                    # Find matching closing brace
                    depth = 0
                    end = start
                    for i, char in enumerate(response[start:], start):
                        if char == '{':
                            depth += 1
                        elif char == '}':
                            depth -= 1
                            if depth == 0:
                                end = i + 1
                                break

                    json_str = response[start:end]
                    tool_call = json.loads(json_str.replace("'", '"'))
                    tool_calls.append(tool_call)
            except (json.JSONDecodeError, ValueError) as e:
                logger.debug(f"Could not parse tool call: {e}")

        return tool_calls

    async def _execute_tools_and_respond(
        self,
        tool_calls: List[Dict[str, Any]],
        original_response: str,
        user_message: str
    ) -> str:
        """Execute tool calls and generate enriched response."""
        results = []

        for call in tool_calls:
            tool_name = call.get("tool")
            args = call.get("args", {})

            if tool_name in SETUP_TOOLS:
                try:
                    tool_config = SETUP_TOOLS[tool_name]
                    tool_fn = tool_config["fn"]

                    # Add confab_id to args if not present
                    if "confab_id" not in args:
                        args["confab_id"] = self.confab_id

                    # Pass db to tools that require it (fixes the missing db bug)
                    if tool_config["requires_db"]:
                        result = tool_fn(db=self.db, **args)
                    else:
                        result = tool_fn(**args)

                    results.append(f"Tool '{tool_name}' executed: {result}")
                    logger.info(f"Executed tool {tool_name} for confab {self.confab_id}")
                except Exception as e:
                    results.append(f"Tool '{tool_name}' failed: {str(e)}")
                    logger.error(f"Tool {tool_name} error: {e}")
            else:
                logger.warning(f"Unknown tool: {tool_name}")
                results.append(f"Tool '{tool_name}' not found")

        # If tools were executed, append results to response
        if results:
            return original_response + "\n\n[Tool execution results: " + "; ".join(results) + "]"

        return original_response

    async def _update_progress_from_response(
        self,
        user_message: str,
        assistant_response: str
    ) -> None:
        """Update setup progress based on conversation content."""
        # Simple heuristic: detect when a step seems complete
        current_stage = self.context.setup_progress.current_stage
        step_num = None

        # Map stage to step number
        stage_to_step = {
            "purpose": 1,
            "participants": 2,
            "memory": 3,
            "tools": 4,
            "guardrails": 5,
            "sample_io": 6,
            "review": 7
        }

        # Check for completion signals in response
        completion_signals = [
            "got it", "understood", "perfect", "great", "recorded",
            "saved", "moving on", "next step", "let's continue"
        ]

        response_lower = assistant_response.lower()
        if any(signal in response_lower for signal in completion_signals):
            step_num = stage_to_step.get(current_stage)

            if step_num and step_num not in self.context.setup_progress.completed_steps:
                # Update progress
                self.context.setup_progress.completed_steps.append(step_num)

                # Determine next stage
                for next_step in range(step_num + 1, 8):
                    if next_step not in self.context.setup_progress.completed_steps:
                        next_stage = {v: k for k, v in stage_to_step.items()}.get(next_step)
                        if next_stage:
                            self.context.setup_progress.current_stage = next_stage
                        break

                # Persist to confab config
                await self._persist_progress()

    def _is_purpose_confirmed(self, user_message: str) -> bool:
        """Check if user is confirming the purpose with a Yes response."""
        confirmation_indicators = [
            "yes", "yep", "correct", "that's right", "that is right", 
            "looks good", "perfect", "sounds good", "confirmed"
        ]
        
        message_lower = user_message.lower().strip()
        return any(indicator in message_lower for indicator in confirmation_indicators)

    async def _auto_generate_spec_workflow(self, user_message: str) -> Dict[str, Any]:
        """Automatically trigger the full spec generation workflow when purpose is confirmed."""
        try:
            # Get current purpose from confab
            purpose_text = self.confab.purpose or ""
            if not purpose_text:
                return {
                    "response": "I don't see a purpose defined yet. Let me help you define one first.",
                    "confab_id": self.confab_id,
                    "is_resume": False,
                    "setup_progress": self.context.setup_progress.__dict__,
                    "tool_calls": [],
                    "timestamp": datetime.now().isoformat(),
                }
            
            # Step 1: Generate name from purpose
            from agent_tools import _generate_name_internal
            name_result = await _generate_name_internal(self.confab_id, purpose_text)
            
            if name_result.get("status") != "success":
                return {
                    "response": f"I had trouble generating a name for your confab: {name_result.get('error', 'Unknown error')}",
                    "confab_id": self.confab_id,
                    "is_resume": False,
                    "setup_progress": self.context.setup_progress.__dict__,
                    "tool_calls": ["generate_name"],
                    "timestamp": datetime.now().isoformat(),
                }
            
            confab_name = name_result["data"]["confab_name"]
            
            # Step 2: Create spec files
            from agent_tools import _create_spec_internal
            spec_result = await _create_spec_internal(self.confab_id, purpose_text, confab_name)
            
            if spec_result.get("status") != "success":
                return {
                    "response": f"I had trouble generating the spec files: {spec_result.get('error', 'Unknown error')}",
                    "confab_id": self.confab_id,
                    "is_resume": False,
                    "setup_progress": self.context.setup_progress.__dict__,
                    "tool_calls": ["generate_name", "create_spec"],
                    "timestamp": datetime.now().isoformat(),
                }
            
            spec_files = spec_result["data"]["spec_files"]
            
            # Step 3: Save spec files locally
            from agent_tools import _save_spec_locally_internal
            save_result = await _save_spec_locally_internal(self.confab_id, confab_name, spec_files)
            
            # Step 4: Push to GitHub
            from agent_tools import _github_push_internal
            github_result = await _github_push_internal(self.confab_id, confab_name, spec_files)
            
            # Prepare response message
            response_parts = [
                f"Great! I've created your confab '{confab_name}' and generated all the specification files.",
                f"",
                f"**Files Generated:**",
                f"- PURPOSE.md: Defines your confab's purpose and scope",
                f"- Confab.toml: Configuration file with all settings",
                f"- GUARDRAILS.md: Safety and behavioral guidelines", 
                f"- TESTS.md: Comprehensive test cases",
                f""
            ]
            
            if save_result.get("status") == "success":
                response_parts.append(f"✅ **Local Save:** Files saved to {save_result['data']['confab_dir']}")
            
            if github_result.get("status") == "success":
                repo_info = github_result["data"]
                response_parts.extend([
                    f"✅ **GitHub Push:** Successfully pushed to {repo_info['repo']}",
                    f"📁 **Location:** {repo_info['pushed_files'][0].split('/')[0]}/",
                    f""
                ])
                response_parts.append("Your confab is now ready! You can start using it and the specifications are version-controlled in GitHub.")
            else:
                response_parts.append(f"⚠️ **GitHub Warning:** {github_result.get('error', 'Unknown GitHub error')}")
                response_parts.append("The files were saved locally and you can manually push them to GitHub later.")
            
            # Update progress to mark all steps complete
            self.context.setup_progress.completed_steps = [1, 2, 3, 4, 5, 6, 7]
            self.context.setup_progress.current_stage = "complete"
            await self._persist_progress()
            
            return {
                "response": "\n".join(response_parts),
                "confab_id": self.confab_id,
                "is_resume": False,
                "setup_progress": {
                    "completed_steps": self.context.setup_progress.completed_steps,
                    "current_stage": "complete",
                    "total_steps": self.context.setup_progress.total_steps,
                    "remaining_steps": 0
                },
                "tool_calls": ["generate_name", "create_spec", "save_spec_locally", "github_push"],
                "timestamp": datetime.now().isoformat(),
                "auto_generated": True,
            }
            
        except Exception as e:
            logger.error(f"Error in auto spec generation workflow: {e}")
            return {
                "response": f"I encountered an error while automatically generating your confab specifications: {str(e)}\n\nLet's continue manually - I can help you set up each step individually.",
                "confab_id": self.confab_id,
                "is_resume": False,
                "setup_progress": self.context.setup_progress.__dict__,
                "tool_calls": [],
                "timestamp": datetime.now().isoformat(),
            }

    async def _persist_progress(self) -> None:
        """Persist setup progress to confab.setup_progress JSON field in database."""
        try:
            self.confab.setup_progress = {
                "completed_steps": self.context.setup_progress.completed_steps,
                "current_stage": self.context.setup_progress.current_stage,
            }
            self.db.commit()
            logger.info(f"Persisted progress for confab {self.confab_id}: {self.context.setup_progress.completed_steps}")
        except Exception as e:
            logger.error(f"Failed to persist progress for confab {self.confab_id}: {e}")
