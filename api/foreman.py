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

from models import Confab, Message, Thread, ThreadMapping, GitHubAccount
from context_loader import ContextLoader, ForemanContext
from resume_generator import ResumePromptGenerator, STAGE_PROMPTS, STEP_DESCRIPTIONS
from llm_service import ask_llm

logger = logging.getLogger(__name__)


# System prompt for the Foreman agent
FOREMAN_SYSTEM_PROMPT = """You are the Foreman, an AI assistant helping users build and configure AI agents (called "confabs").

Your role is to guide users through a 7-step process to create their agent:
1. Define purpose - What should the agent do?
2. Add participants - Who can access it?
3. Configure memory - Should it remember conversations?
4. Set up tools - What external capabilities does it need?
5. Establish guardrails - What are its safety boundaries?
6. Sample I/O - Provide example interactions
7. Review - Finalize the configuration

Guidelines:
- Be helpful and conversational
- Ask clarifying questions when needed
- Guide users one step at a time
- Summarize what you understand before moving to the next step
- When a step is complete, suggest the next step
- If the user wants to skip a step or revisit a previous one, accommodate them

When the user provides information for a step, acknowledge it and either:
1. Ask a follow-up question if more details are needed
2. Confirm what you understood and suggest moving to the next step

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
                role="assistant"
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
        """
        if not self.initialized:
            raise RuntimeError("Foreman not initialized. Call initialize() first.")

        # Ensure we have a thread
        thread_id = await self._ensure_thread()

        # Store user message
        user_msg = Message(
            thread_id=thread_id,
            content=user_message,
            role="user"
        )
        self.db.add(user_msg)
        self.db.commit()
        self.db.refresh(user_msg)

        # Build contextual prompt
        prompt = self._build_contextual_prompt(user_message)

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

        # Store assistant response
        assistant_msg = Message(
            thread_id=thread_id,
            content=response,
            role="assistant"
        )
        self.db.add(assistant_msg)
        self.db.commit()
        self.db.refresh(assistant_msg)

        # Update progress if needed
        await self._update_progress_from_response(user_message, response)

        return {
            "response": response,
            "confab_id": self.confab_id,
            "thread_id": thread_id,
            "is_resume": False,
            "setup_progress": {
                "completed_steps": self.context.setup_progress.completed_steps,
                "current_stage": self.context.setup_progress.current_stage,
                "total_steps": self.context.setup_progress.total_steps,
                "remaining_steps": self.context.setup_progress.remaining_steps
            },
            "tool_calls": tool_calls,
            "timestamp": datetime.now().isoformat(),
            "messages": {
                "user_message_id": user_msg.id,
                "assistant_message_id": assistant_msg.id
            }
        }

    async def _ensure_thread(self) -> int:
        """Ensure a thread exists for this confab, create if needed."""
        if self.context.thread_id:
            return self.context.thread_id

        # Create new thread
        new_thread = Thread(
            thread_name=f"Foreman session for {self.confab.name or f'confab-{self.confab_id}'}",
            owner_user_id=self.confab.user_id
        )
        self.db.add(new_thread)
        self.db.commit()
        self.db.refresh(new_thread)

        # Create thread mapping
        mapping = ThreadMapping(
            confab_id=self.confab_id,
            thread_id=new_thread.id
        )
        self.db.add(mapping)
        self.db.commit()

        self.context.thread_id = new_thread.id
        logger.info(f"Created new thread {new_thread.id} for confab {self.confab_id}")
        return new_thread.id

    def _build_contextual_prompt(self, user_message: str) -> str:
        """Build a prompt with full context for the LLM."""
        # Get system context from GitHub files
        generator = ResumePromptGenerator(self.context)
        system_context = generator.get_system_context()

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
            completed_steps=self.context.setup_progress.completed_steps
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
        # Import tool execution from agent_tools
        try:
            from agent_tools import (
                define_purpose, add_participant, configure_memory,
                add_tools_and_apis, guardrails, sample_io, review_and_save,
                update_purpose
            )

            tool_map = {
                "define_purpose": define_purpose,
                "add_participant": add_participant,
                "configure_memory": configure_memory,
                "add_tools_and_apis": add_tools_and_apis,
                "guardrails": guardrails,
                "sample_io": sample_io,
                "review_and_save": review_and_save,
                "update_purpose": update_purpose
            }

            results = []
            for call in tool_calls:
                tool_name = call.get("tool")
                args = call.get("args", {})

                if tool_name in tool_map:
                    try:
                        # Add confab_id to args if not present
                        if "confab_id" not in args:
                            args["confab_id"] = self.confab_id

                        result = tool_map[tool_name](**args)
                        results.append(f"Tool '{tool_name}' executed: {result}")
                        logger.info(f"Executed tool {tool_name} for confab {self.confab_id}")
                    except Exception as e:
                        results.append(f"Tool '{tool_name}' failed: {str(e)}")
                        logger.error(f"Tool {tool_name} error: {e}")

            # If tools were executed, append results to response
            if results:
                return original_response + "\n\n[Tool execution results: " + "; ".join(results) + "]"

        except ImportError as e:
            logger.warning(f"Could not import agent_tools: {e}")

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

    async def _persist_progress(self) -> None:
        """Persist setup progress to confab config in database."""
        try:
            config = self.context.db_config.copy() if self.context.db_config else {}
            config["setup_steps_completed"] = self.context.setup_progress.completed_steps

            self.confab.config = config
            self.db.commit()
            logger.info(f"Persisted progress for confab {self.confab_id}: {self.context.setup_progress.completed_steps}")
        except Exception as e:
            logger.error(f"Failed to persist progress: {e}")
