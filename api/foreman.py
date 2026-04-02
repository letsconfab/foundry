"""
Foreman Agent - Top-level orchestrator for confabs in 'building' status
Handles context loading, resume prompts, and proactive conversation guidance.

V2 Architecture (when FOREMAN_V2_ENABLED=true):
- Deterministic stage machine with explicit transitions
- Structured LLM extraction at low temperature
- Direct tool invocation per stage
- Save-gated stage progression
"""

import logging
import json
import re
import os
from dataclasses import dataclass
from typing import Optional, Dict, Any, List, Literal, Tuple
from datetime import datetime
from sqlalchemy.orm import Session

# Feature flag for V2 deterministic interview flow
FOREMAN_V2_ENABLED = os.getenv("FOREMAN_V2_ENABLED", "false").lower() == "true"

from models import Confab, GitHubAccount
from context_loader import ContextLoader, ForemanContext
from resume_generator import ResumePromptGenerator, STAGE_PROMPTS, STEP_DESCRIPTIONS
from llm_service import (
    ask_llm,
    ask_llm_json,
    extract_purpose,
    extract_participants,
    extract_memory_preference,
    extract_tools,
    extract_guardrails,
    extract_sample_io,
    extract_review_intent,
)
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


# =========================================================================
# V2 Stage Machine Types and Configuration
# =========================================================================

@dataclass
class StageResult:
    """Result from a V2 stage handler."""
    status: Literal["complete", "clarify", "skip", "error"]
    data: Optional[Dict[str, Any]] = None       # Extracted/saved data
    summary: Optional[str] = None               # What was saved (for response)
    next_question: Optional[str] = None         # What to ask next
    error_message: Optional[str] = None         # If status == "error"


# Stage questions - the primary question for each stage
STAGE_QUESTIONS = {
    "purpose": "What should this agent do? Describe its main job in a sentence or two.",
    "participants": "Who should have access to this agent? You can add email addresses or skip for now.",
    "memory": "Should this agent remember previous conversations? (yes, no, or limited)",
    "tools": "What external tools or APIs does this agent need? (e.g., web search, database, none)",
    "guardrails": "What safety boundaries should this agent follow? List any rules or restrictions.",
    "sample_io": "Can you provide an example interaction? (e.g., 'User asks X, agent responds Y')",
    "review": "Here's your agent configuration. Ready to save and deploy?",
}

# Clarification prompts when we need more info
STAGE_CLARIFICATIONS = {
    "purpose": "I need a bit more detail. What specific task should this agent help with?",
    "participants": "Could you provide an email address, or say 'skip' to continue?",
    "memory": "Please specify: should it remember conversations? (yes/no/limited)",
    "tools": "Which tools specifically? For example: web search, calendar, database, or 'none'.",
    "guardrails": "What's one important rule this agent should follow?",
    "sample_io": "Can you give a quick example of what a user might ask and how the agent should respond?",
    "review": "Would you like to make any changes, or shall I save this configuration?",
}

# Acknowledgment templates (short, no praise)
STAGE_ACKNOWLEDGMENTS = {
    "purpose": "Recorded the purpose.",
    "participants": "Added participant.",
    "memory": "Memory settings configured.",
    "tools": "Tools configured.",
    "guardrails": "Guardrails saved.",
    "sample_io": "Example recorded.",
    "review": "Configuration saved.",
}


# System prompt for the Foreman agent
FOREMAN_SYSTEM_PROMPT = """You are the Foreman, the lead orchestrator in the Agent Foundry. You guide users through building AI agents (called "confabs").

IMPORTANT: You must actively lead this conversation. Do not wait passively for the user to drive the process. After each user response, acknowledge what they said, save the relevant information using the appropriate tool, then proactively move to the next step.

## The 7-Step Process
1. **Define purpose** - What should the agent do? (CURRENT FOCUS if just starting)
2. **Add participants** - Who can access it?
3. **Configure memory** - Should it remember conversations?
4. **Set up tools** - What external capabilities does it need?
5. **Establish guardrails** - What are its safety boundaries?
6. **Sample I/O** - Provide example interactions
7. **Review** - Finalize the configuration

## Available Tools
CRITICAL: You MUST use these tools to save information. Without calling these tools, nothing is persisted!

### Step 1: Purpose and Naming
When the user describes what their agent should do:
1. First, save the purpose using define_purpose:
   {{"tool": "define_purpose", "args": {{"purpose_text": "A clear, detailed description of what the agent does..."}}}}

2. Then, generate and save a short name (1-2 words, descriptive):
   {{"tool": "set_confab_name", "args": {{"name": "YourChosenName"}}}}
   - Examples: "SupportBot", "DataAnalyzer", "CodeReviewer", "TrueDetectiveHub"
   - A timestamp will be added automatically (e.g., "SupportBot-20260326-1430")

### Step 2: Participants
{{"tool": "add_participant", "args": {{"email": "user@example.com"}}}}

### Step 3: Memory
{{"tool": "configure_memory", "args": {{"memory_notes": "Notes about what to remember", "enable": true}}}}

### Step 4: Tools/APIs
{{"tool": "add_tools_and_apis", "args": {{"tool_name": "ToolName", "api_key": "key_if_needed"}}}}

### Step 5: Guardrails
{{"tool": "guardrails", "args": {{"guardrails_text": "1. Safety rule 1\\n2. Safety rule 2\\n3. Safety rule 3"}}}}

### Step 6: Sample I/O
{{"tool": "sample_io", "args": {{"sample_text": "User: Example user input\\nAgent: Expected agent response"}}}}

### Step 7: Review and Save
{{"tool": "review_and_save", "args": {{}}}}

## Your Behavior
- LEAD the conversation - always end your response with a clear question for the next step
- Focus on ONE step at a time - don't overwhelm the user
- ALWAYS use the appropriate tool to save information - just acknowledging is NOT enough
- After receiving information, call the tool to save it, briefly confirm what you saved, then ask about the next step
- Keep responses concise and action-oriented
- If the user's response is vague, ask ONE specific clarifying question
- If the user wants to skip a step, acknowledge it and move to the next step
- When all steps are complete, summarize the configuration and confirm they're ready to save

## Response Format
1. Brief acknowledgment of what the user said (1-2 sentences)
2. Tool call(s) to save the information (REQUIRED - do not skip this!)
3. Confirmation of what you saved
4. Clear transition to the next step with a specific question

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
        logger.info(
            f"Foreman initialized for confab {self.confab_id} "
            f"[v2_enabled={FOREMAN_V2_ENABLED}, "
            f"stage={self.context.setup_progress.current_stage}, "
            f"completed_steps={self.context.setup_progress.completed_steps}]"
        )
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

        current_stage = self.context.setup_progress.current_stage
        logger.info(
            f"[Foreman] Processing message for confab {self.confab_id} "
            f"[stage={current_stage}, v2={FOREMAN_V2_ENABLED}]"
        )
        logger.debug(f"[Foreman] User message: {user_message[:100]}...")

        # V2 path: deterministic stage-based dispatch
        if FOREMAN_V2_ENABLED:
            return await self._process_message_v2(user_message)

        # V1 path: LLM-driven flow with tool parsing from prose
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
        """Parse tool calls from LLM response (JSON embedded in text).

        V1 ONLY: This method parses JSON tool calls embedded in prose.
        In V2, tools are called directly from stage handlers.
        """
        tool_calls = []
        seen_json_strings = set()  # Avoid duplicate tool calls
        parse_attempts = 0
        parse_failures = 0

        logger.debug(f"[Foreman] Scanning response for tool calls ({len(response)} chars)")

        # Find all potential starting positions for tool JSON objects
        search_start = 0
        while True:
            # Look for {"tool" or {'tool
            start = response.find('{"tool"', search_start)
            if start == -1:
                start = response.find("{'tool", search_start)
            if start == -1:
                break

            parse_attempts += 1
            try:
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

                # Skip if we've already seen this exact JSON string
                if json_str in seen_json_strings:
                    search_start = end
                    continue
                seen_json_strings.add(json_str)

                # Normalize quotes and parse
                normalized = json_str.replace("'", '"')
                tool_call = json.loads(normalized)

                # Validate it has the expected structure
                if "tool" in tool_call:
                    tool_calls.append(tool_call)
                    logger.info(
                        f"[Foreman] Parsed tool call: {tool_call.get('tool')} "
                        f"[confab={self.confab_id}]"
                    )

                search_start = end
            except (json.JSONDecodeError, ValueError) as e:
                parse_failures += 1
                logger.warning(
                    f"[Foreman] Tool parse failure at position {start}: {e} "
                    f"[confab={self.confab_id}, snippet={response[start:start+50]}...]"
                )
                search_start = start + 1  # Move past this position and try again

        logger.info(
            f"[Foreman] Tool parsing complete: {len(tool_calls)} found, "
            f"{parse_attempts} attempts, {parse_failures} failures "
            f"[confab={self.confab_id}]"
        )
        return tool_calls

    async def _execute_tools_and_respond(
        self,
        tool_calls: List[Dict[str, Any]],
        original_response: str,
        user_message: str
    ) -> str:
        """Execute tool calls and generate enriched response.

        V1 ONLY: Executes tools discovered via prose parsing.
        In V2, tools are called directly from stage handlers.
        """
        results = []
        success_count = 0
        failure_count = 0

        logger.info(
            f"[Foreman] Executing {len(tool_calls)} tool(s) [confab={self.confab_id}]"
        )

        for call in tool_calls:
            tool_name = call.get("tool")
            args = call.get("args", {})

            logger.debug(
                f"[Foreman] Tool execution attempt: {tool_name} "
                f"[args={list(args.keys())}, confab={self.confab_id}]"
            )

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
                    success_count += 1
                    logger.info(
                        f"[Foreman] Tool success: {tool_name} "
                        f"[confab={self.confab_id}, result_preview={str(result)[:100]}]"
                    )
                except Exception as e:
                    results.append(f"Tool '{tool_name}' failed: {str(e)}")
                    failure_count += 1
                    logger.error(
                        f"[Foreman] Tool failure: {tool_name} "
                        f"[confab={self.confab_id}, error={e}]"
                    )
            else:
                failure_count += 1
                logger.warning(
                    f"[Foreman] Unknown tool: {tool_name} [confab={self.confab_id}]"
                )
                results.append(f"Tool '{tool_name}' not found")

        logger.info(
            f"[Foreman] Tool execution complete: {success_count} succeeded, "
            f"{failure_count} failed [confab={self.confab_id}]"
        )

        # If tools were executed, append results to response
        if results:
            return original_response + "\n\n[Tool execution results: " + "; ".join(results) + "]"

        return original_response

    async def _update_progress_from_response(
        self,
        user_message: str,
        assistant_response: str
    ) -> None:
        """Update setup progress based on conversation content.

        V1 ONLY: Uses phrase-based heuristics to detect stage completion.
        In V2, stage progression is controlled by explicit save success.
        """
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
        matched_signals = [s for s in completion_signals if s in response_lower]

        if matched_signals:
            logger.debug(
                f"[Foreman] Progress signals detected: {matched_signals} "
                f"[stage={current_stage}, confab={self.confab_id}]"
            )
            step_num = stage_to_step.get(current_stage)

            if step_num and step_num not in self.context.setup_progress.completed_steps:
                old_stage = current_stage
                # Update progress
                self.context.setup_progress.completed_steps.append(step_num)

                # Determine next stage
                for next_step in range(step_num + 1, 8):
                    if next_step not in self.context.setup_progress.completed_steps:
                        next_stage = {v: k for k, v in stage_to_step.items()}.get(next_step)
                        if next_stage:
                            self.context.setup_progress.current_stage = next_stage
                        break

                logger.info(
                    f"[Foreman] Stage transition: {old_stage} -> "
                    f"{self.context.setup_progress.current_stage} "
                    f"[completed={self.context.setup_progress.completed_steps}, "
                    f"confab={self.confab_id}]"
                )

                # Persist to confab config
                await self._persist_progress()
        else:
            logger.debug(
                f"[Foreman] No progress signals in response "
                f"[stage={current_stage}, confab={self.confab_id}]"
            )

    async def _persist_progress(self) -> None:
        """Persist setup progress to confab.setup_progress JSON field in database."""
        try:
            self.confab.setup_progress = {
                "completed_steps": self.context.setup_progress.completed_steps,
                "current_stage": self.context.setup_progress.current_stage,
            }
            self.db.commit()
            logger.info(
                f"[Foreman] Progress persisted [confab={self.confab_id}, "
                f"stage={self.context.setup_progress.current_stage}, "
                f"completed={self.context.setup_progress.completed_steps}]"
            )
        except Exception as e:
            logger.error(
                f"[Foreman] Failed to persist progress "
                f"[confab={self.confab_id}, error={e}]"
            )

    # =========================================================================
    # V2 METHODS - Deterministic Interview Flow
    # =========================================================================

    # Stage order for V2 deterministic flow
    STAGE_ORDER = ["purpose", "participants", "memory", "tools", "guardrails", "sample_io", "review"]

    async def _process_message_v2(self, user_message: str) -> Dict[str, Any]:
        """
        V2: Deterministic stage-based message processing.

        Instead of letting the LLM drive the entire flow, we dispatch to
        stage-specific handlers that:
        1. Extract structured data from user input (low-temp LLM)
        2. Call tools directly
        3. Advance stage only on successful save
        4. Return templated responses
        """
        current_stage = self.context.setup_progress.current_stage

        logger.info(
            f"[Foreman V2] Processing message [stage={current_stage}, "
            f"confab={self.confab_id}]"
        )

        # Dispatch to stage-specific handler
        stage_handlers = {
            "purpose": self._handle_purpose,
            "participants": self._handle_participants,
            "memory": self._handle_memory,
            "tools": self._handle_tools,
            "guardrails": self._handle_guardrails,
            "sample_io": self._handle_sample_io,
            "review": self._handle_review,
        }

        # Check if user wants to update a previous stage
        target_stage, extracted_content = self._detect_update_intent(user_message)
        is_update = target_stage is not None and target_stage != current_stage

        if is_update:
            logger.info(f"[Foreman V2] Update intent detected: {target_stage}")
            handler = stage_handlers.get(target_stage)
            # Use extracted content if available, otherwise full message
            message_to_process = extracted_content or user_message
        else:
            handler = stage_handlers.get(current_stage)
            message_to_process = user_message

        if not handler:
            stage_name = target_stage if is_update else current_stage
            logger.error(f"[Foreman V2] No handler for stage: {stage_name}")
            return self._build_error_response(
                f"Unknown stage: {stage_name}",
                current_stage
            )

        # Execute stage handler
        try:
            result = await handler(message_to_process)
        except Exception as e:
            logger.error(f"[Foreman V2] Handler error for {current_stage}: {e}")
            result = StageResult(
                status="error",
                error_message=f"An error occurred: {str(e)}"
            )

        # Process result and potentially advance stage
        if is_update:
            # For updates to previous stages, confirm the update and re-ask current stage question
            if result.status == "complete":
                # Reload confab to get updated data for summary
                self.db.refresh(self.confab)
                if current_stage == "review":
                    response_text = f"Updated {target_stage}.{self._build_config_summary()}\n\n{STAGE_QUESTIONS.get(current_stage, '')}"
                else:
                    response_text = f"Updated {target_stage}. {STAGE_QUESTIONS.get(current_stage, '')}"
            else:
                response_text = self._render_foreman_reply(result, target_stage)
        else:
            response_text = self._render_foreman_reply(result, current_stage)
            # Only advance stage for normal flow (not updates)
            if result.status in ("complete", "skip"):
                await self._complete_stage(current_stage)

        # Build response
        return {
            "response": response_text,
            "confab_id": self.confab_id,
            "is_resume": False,
            "setup_progress": {
                "completed_steps": self.context.setup_progress.completed_steps,
                "current_stage": self.context.setup_progress.current_stage,
                "total_steps": self.context.setup_progress.total_steps,
                "remaining_steps": self.context.setup_progress.remaining_steps
            },
            "tool_calls": [],  # V2 doesn't expose tool calls
            "timestamp": datetime.now().isoformat(),
            "v2_metadata": {
                "stage": current_stage,
                "stage_status": result.status,
                "is_update": is_update,
                "updated_stage": target_stage if is_update else None,
                "saved_fields": result.data,
                "next_question": result.next_question,
            }
        }

    def _next_stage_after(self, stage: str) -> Optional[str]:
        """Return the next stage after the given stage, or None if at end."""
        try:
            idx = self.STAGE_ORDER.index(stage)
            if idx + 1 < len(self.STAGE_ORDER):
                return self.STAGE_ORDER[idx + 1]
        except ValueError:
            logger.warning(f"[Foreman V2] Unknown stage: {stage}")
        return None

    def _stage_to_step_num(self, stage: str) -> Optional[int]:
        """Convert stage name to step number (1-indexed)."""
        try:
            return self.STAGE_ORDER.index(stage) + 1
        except ValueError:
            return None

    async def _complete_stage(self, stage: str) -> None:
        """Mark a stage as complete and advance to the next stage."""
        step_num = self._stage_to_step_num(stage)
        if step_num and step_num not in self.context.setup_progress.completed_steps:
            self.context.setup_progress.completed_steps.append(step_num)

        next_stage = self._next_stage_after(stage)
        if next_stage:
            self.context.setup_progress.current_stage = next_stage

        logger.info(
            f"[Foreman V2] Stage complete: {stage} -> {next_stage} "
            f"[completed={self.context.setup_progress.completed_steps}, "
            f"confab={self.confab_id}]"
        )

        await self._persist_progress()

    def _build_config_summary(self) -> str:
        """Build a summary of the current confab configuration."""
        confab = self.confab
        setup_progress = confab.setup_progress or {}
        lines = ["\n\n---\n**Agent Configuration**\n---\n\n"]

        # Name
        if confab.name:
            lines.append(f"**Name:** {confab.name}\n\n")

        # Purpose
        if confab.purpose:
            purpose_preview = confab.purpose[:300] + "..." if len(confab.purpose) > 300 else confab.purpose
            lines.append(f"**Purpose:**\n{purpose_preview}\n\n")

        # Participants (stored in setup_progress)
        participants = setup_progress.get("participants", [])
        if participants:
            if isinstance(participants, list):
                lines.append(f"**Participants:** {', '.join(str(p) for p in participants)}\n\n")
            else:
                lines.append(f"**Participants:** {participants}\n\n")

        # Memory
        memory_notes = setup_progress.get("memory_notes")
        if memory_notes:
            lines.append(f"**Memory:** {memory_notes}\n\n")

        # Tools
        tools = setup_progress.get("tools", [])
        if tools:
            if isinstance(tools, list):
                lines.append(f"**Tools:** {', '.join(str(t) for t in tools)}\n\n")
            else:
                lines.append(f"**Tools:** {tools}\n\n")

        # Guardrails
        if confab.guardrails:
            rules = [g.get("rule", "") for g in confab.guardrails if isinstance(g, dict)]
            if rules:
                lines.append("**Guardrails:**\n")
                for i, rule in enumerate(rules[:5], 1):  # Show first 5
                    lines.append(f"  {i}. {rule}\n")
                if len(rules) > 5:
                    lines.append(f"  ... and {len(rules) - 5} more\n")
                lines.append("\n")

        # Sample I/O
        sample_io = setup_progress.get("sample_io")
        if sample_io:
            lines.append(f"**Sample Q&A:**\n{sample_io}\n\n")

        lines.append("---\n")
        return "".join(lines)

    def _render_foreman_reply(self, result: StageResult, current_stage: str) -> str:
        """Render a consistent Foreman response from a StageResult."""
        parts = []

        if result.status == "error":
            parts.append(result.error_message or "An error occurred.")
            parts.append(STAGE_QUESTIONS.get(current_stage, "How would you like to proceed?"))

        elif result.status == "clarify":
            if result.summary:
                parts.append(result.summary)
            parts.append(result.next_question or STAGE_CLARIFICATIONS.get(current_stage, "Could you provide more detail?"))

        elif result.status == "skip":
            parts.append("Skipping this step.")
            next_stage = self._next_stage_after(current_stage)
            if next_stage:
                if next_stage == "review":
                    parts.append(self._build_config_summary())
                parts.append(STAGE_QUESTIONS.get(next_stage, ""))

        elif result.status == "complete":
            # Acknowledgment + next question
            ack = result.summary or STAGE_ACKNOWLEDGMENTS.get(current_stage, "Saved.")
            parts.append(ack)
            next_stage = self._next_stage_after(current_stage)
            if next_stage:
                if next_stage == "review":
                    parts.append(self._build_config_summary())
                parts.append(STAGE_QUESTIONS.get(next_stage, ""))
            else:
                parts.append("All steps complete. Your agent is ready.")

        return " ".join(parts)

    def _build_error_response(self, error_msg: str, stage: str) -> Dict[str, Any]:
        """Build an error response dict."""
        return {
            "response": f"Error: {error_msg}",
            "confab_id": self.confab_id,
            "is_resume": False,
            "setup_progress": {
                "completed_steps": self.context.setup_progress.completed_steps,
                "current_stage": self.context.setup_progress.current_stage,
                "total_steps": self.context.setup_progress.total_steps,
                "remaining_steps": self.context.setup_progress.remaining_steps
            },
            "tool_calls": [],
            "timestamp": datetime.now().isoformat(),
            "v2_metadata": {
                "stage": stage,
                "stage_status": "error",
                "saved_fields": None,
                "next_question": None,
            }
        }

    def _detect_update_intent(self, user_message: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Detect if user wants to update a previous stage.

        Returns:
            (target_stage, extracted_content) if update intent detected
            (None, None) if no update intent
        """
        msg_lower = user_message.lower()

        # Patterns that indicate update intent
        update_triggers = ["update", "change", "modify", "edit", "revise", "fix", "add to", "also add"]

        # Map keywords to stages
        stage_keywords = {
            "purpose": ["purpose", "what it does", "description", "objective"],
            "participants": ["participant", "email", "access", "who can"],
            "memory": ["memory", "remember", "conversation history"],
            "tools": ["tool", "api", "capability", "integration"],
            "guardrails": ["guardrail", "rule", "restriction", "safety", "boundary", "constraint"],
            "sample_io": ["sample", "example", "interaction", "input", "output"],
        }

        # Check if message starts with or contains update trigger
        has_update_trigger = any(trigger in msg_lower for trigger in update_triggers)
        if not has_update_trigger:
            return None, None

        # Find which stage is being referenced
        for stage, keywords in stage_keywords.items():
            for keyword in keywords:
                if keyword in msg_lower:
                    # Extract the content after the stage reference
                    # e.g., "Update the guardrails: X Y Z" -> "X Y Z"
                    content = user_message
                    for trigger in update_triggers:
                        for kw in keywords:
                            # Try to find pattern like "update the guardrails:"
                            pattern = rf"(?i){trigger}\s+(?:the\s+)?{kw}[s]?\s*[:\-]?\s*"
                            match = re.search(pattern, user_message)
                            if match:
                                content = user_message[match.end():].strip()
                                break
                    return stage, content if content else user_message

        return None, None

    def _detect_skip_intent(self, user_message: str) -> bool:
        """Detect if user wants to skip the current step."""
        skip_patterns = ["skip", "next", "pass", "later", "not now", "move on", "none"]
        msg_lower = user_message.lower().strip()
        return any(pattern in msg_lower for pattern in skip_patterns)

    def _build_stage_conversation_context(self, include_current: str = "") -> str:
        """
        Build conversation context from thread history for the current stage.

        Returns a formatted string of all user messages and assistant questions
        that belong to the current stage (i.e., messages after the last stage
        transition, or all messages if we're on the first stage).
        """
        if not self.context.thread_history:
            return include_current

        # Get recent conversation (last 10 messages should cover current stage)
        recent = self.context.thread_history[-10:]

        lines = []
        for msg in recent:
            role = "User" if msg.role == "user" else "Foreman"
            lines.append(f"{role}: {msg.content}")

        if include_current:
            lines.append(f"User: {include_current}")

        return "\n".join(lines)

    # =========================================================================
    # Stage Handlers
    # =========================================================================

    async def _handle_purpose(self, user_message: str) -> StageResult:
        """
        Handle the purpose definition stage using structured extraction.

        This handler accumulates context from multiple conversation turns,
        allowing users to refine the purpose through clarifying questions.
        """
        if self._detect_skip_intent(user_message):
            return StageResult(status="skip")

        # Check if message has enough content for a purpose
        if len(user_message.strip()) < 10:
            return StageResult(
                status="clarify",
                next_question=STAGE_CLARIFICATIONS["purpose"]
            )

        # Build conversation context including all prior purpose discussion
        context = self._build_stage_conversation_context(user_message)

        # Use structured LLM extraction with full conversation context
        extraction = await extract_purpose(user_message, context=context)

        if not extraction.success:
            logger.warning(f"[Foreman V2] Purpose extraction failed: {extraction.error}")
            # Fallback to using message directly
            purpose_text = user_message.strip()
            suggested_name = None
        else:
            data = extraction.data
            # Check if LLM needs clarification
            if not data.get("is_clear", True) and data.get("clarification_needed"):
                return StageResult(
                    status="clarify",
                    next_question=data["clarification_needed"]
                )
            purpose_text = data.get("purpose_text", user_message.strip())
            suggested_name = data.get("suggested_name")

        # Save purpose
        try:
            define_purpose(
                db=self.db,
                confab_id=self.confab_id,
                purpose_text=purpose_text
            )
            logger.info(f"[Foreman V2] Purpose saved [confab={self.confab_id}]")

            # Save suggested name if available
            name_result = None
            if suggested_name:
                try:
                    set_confab_name(db=self.db, confab_id=self.confab_id, name=suggested_name)
                    name_result = suggested_name
                except Exception as e:
                    logger.warning(f"[Foreman V2] Name save failed: {e}")

            return StageResult(
                status="complete",
                data={"purpose": purpose_text, "name": name_result},
                summary=f"Recorded the purpose: \"{purpose_text[:50]}{'...' if len(purpose_text) > 50 else ''}\""
            )
        except Exception as e:
            logger.error(f"[Foreman V2] Purpose save failed: {e}")
            return StageResult(
                status="error",
                error_message=f"Failed to save purpose: {str(e)}"
            )

    async def _handle_participants(self, user_message: str) -> StageResult:
        """Handle the participants stage using structured extraction."""
        if self._detect_skip_intent(user_message):
            return StageResult(status="skip")

        # Use structured LLM extraction
        extraction = await extract_participants(user_message)

        if extraction.success:
            data = extraction.data
            if data.get("wants_to_skip"):
                return StageResult(status="skip")
            if data.get("clarification_needed") and not data.get("emails"):
                return StageResult(
                    status="clarify",
                    next_question=data["clarification_needed"]
                )
            emails = data.get("emails", [])
        else:
            # Fallback to regex extraction
            email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
            emails = re.findall(email_pattern, user_message)

        if not emails:
            return StageResult(
                status="clarify",
                next_question=STAGE_CLARIFICATIONS["participants"]
            )

        # Add each participant
        added = []
        for email in emails:
            try:
                add_participant(db=self.db, confab_id=self.confab_id, email=email)
                added.append(email)
            except Exception as e:
                logger.warning(f"[Foreman V2] Failed to add participant {email}: {e}")

        if added:
            return StageResult(
                status="complete",
                data={"participants": added},
                summary=f"Added {len(added)} participant(s): {', '.join(added)}"
            )
        else:
            return StageResult(
                status="error",
                error_message="Could not add participants. Please try again."
            )

    async def _handle_memory(self, user_message: str) -> StageResult:
        """Handle the memory configuration stage using structured extraction."""
        if self._detect_skip_intent(user_message):
            return StageResult(status="skip")

        # Use structured LLM extraction
        extraction = await extract_memory_preference(user_message)

        if extraction.success:
            data = extraction.data
            if data.get("wants_to_skip"):
                return StageResult(status="skip")
            if data.get("clarification_needed") and data.get("enable_memory") is None:
                return StageResult(
                    status="clarify",
                    next_question=data["clarification_needed"]
                )

            memory_type = data.get("memory_type", "full")
            enable = data.get("enable_memory", True) if memory_type != "none" else False
            notes = data.get("notes", f"Memory: {memory_type}")
        else:
            # Fallback to keyword matching
            msg_lower = user_message.lower()
            if any(w in msg_lower for w in ["yes", "enable", "remember", "retain"]):
                enable = True
                notes = "Full conversation memory enabled"
            elif any(w in msg_lower for w in ["no", "disable", "forget", "don't remember"]):
                enable = False
                notes = "Memory disabled"
            elif any(w in msg_lower for w in ["limited", "some", "partial", "recent"]):
                enable = True
                notes = "Limited memory - recent conversations only"
            else:
                return StageResult(
                    status="clarify",
                    next_question=STAGE_CLARIFICATIONS["memory"]
                )

        try:
            configure_memory(
                db=self.db,
                confab_id=self.confab_id,
                memory_notes=notes,
                enable=enable
            )
            return StageResult(
                status="complete",
                data={"enable": enable, "notes": notes},
                summary=f"Memory configured: {notes}"
            )
        except Exception as e:
            logger.error(f"[Foreman V2] Memory config failed: {e}")
            return StageResult(
                status="error",
                error_message=f"Failed to configure memory: {str(e)}"
            )

    async def _handle_tools(self, user_message: str) -> StageResult:
        """Handle the tools/APIs stage using structured extraction."""
        if self._detect_skip_intent(user_message):
            return StageResult(status="skip")

        # Use structured LLM extraction
        extraction = await extract_tools(user_message)

        if extraction.success:
            data = extraction.data
            if data.get("wants_to_skip"):
                return StageResult(status="skip")
            if data.get("no_tools_needed"):
                return StageResult(
                    status="complete",
                    data={"tools": []},
                    summary="No additional tools configured."
                )
            if data.get("clarification_needed") and not data.get("tools"):
                return StageResult(
                    status="clarify",
                    next_question=data["clarification_needed"]
                )
            detected_tools = data.get("tools", [])
        else:
            # Fallback to keyword matching
            msg_lower = user_message.lower()
            if any(w in msg_lower for w in ["none", "no tools", "nothing", "no apis"]):
                return StageResult(
                    status="complete",
                    data={"tools": []},
                    summary="No additional tools configured."
                )

            tool_keywords = {
                "web search": "web_search",
                "search": "web_search",
                "database": "database",
                "db": "database",
                "calendar": "calendar",
                "email": "email",
                "slack": "slack",
                "api": "custom_api",
            }
            detected_tools = []
            for keyword, tool_name in tool_keywords.items():
                if keyword in msg_lower:
                    detected_tools.append(tool_name)
            if not detected_tools:
                detected_tools = [user_message.strip()[:50]]

        try:
            for tool in detected_tools:
                add_tools_and_apis(
                    db=self.db,
                    confab_id=self.confab_id,
                    tool_name=tool,
                    api_key=""
                )
            return StageResult(
                status="complete",
                data={"tools": detected_tools},
                summary=f"Tools configured: {', '.join(detected_tools)}"
            )
        except Exception as e:
            logger.error(f"[Foreman V2] Tools config failed: {e}")
            return StageResult(
                status="error",
                error_message=f"Failed to configure tools: {str(e)}"
            )

    async def _handle_guardrails(self, user_message: str) -> StageResult:
        """Handle the guardrails stage using structured extraction."""
        if self._detect_skip_intent(user_message):
            return StageResult(status="skip")

        # Use structured LLM extraction
        extraction = await extract_guardrails(user_message)

        if extraction.success:
            data = extraction.data
            if data.get("wants_to_skip"):
                return StageResult(status="skip")
            if data.get("clarification_needed") and data.get("rules_count", 0) == 0:
                return StageResult(
                    status="clarify",
                    next_question=data["clarification_needed"]
                )
            guardrails_text = data.get("guardrails_text", user_message.strip())
            # Handle case where LLM returns a list instead of string
            if isinstance(guardrails_text, list):
                guardrails_text = "\n".join(f"{i+1}. {rule}" for i, rule in enumerate(guardrails_text))
        else:
            if len(user_message.strip()) < 5:
                return StageResult(
                    status="clarify",
                    next_question=STAGE_CLARIFICATIONS["guardrails"]
                )
            guardrails_text = user_message.strip()

        try:
            guardrails(
                db=self.db,
                confab_id=self.confab_id,
                guardrails_text=guardrails_text
            )
            return StageResult(
                status="complete",
                data={"guardrails": guardrails_text},
                summary="Guardrails saved."
            )
        except Exception as e:
            logger.error(f"[Foreman V2] Guardrails save failed: {e}")
            return StageResult(
                status="error",
                error_message=f"Failed to save guardrails: {str(e)}"
            )

    async def _handle_sample_io(self, user_message: str) -> StageResult:
        """Handle the sample I/O stage using structured extraction."""
        if self._detect_skip_intent(user_message):
            return StageResult(status="skip")

        # Use structured LLM extraction
        extraction = await extract_sample_io(user_message)

        if extraction.success:
            data = extraction.data
            if data.get("wants_to_skip"):
                return StageResult(status="skip")
            if data.get("clarification_needed") and not (data.get("has_input") or data.get("has_output")):
                return StageResult(
                    status="clarify",
                    next_question=data["clarification_needed"]
                )
            sample_text = data.get("sample_text", user_message.strip())
        else:
            if len(user_message.strip()) < 10:
                return StageResult(
                    status="clarify",
                    next_question=STAGE_CLARIFICATIONS["sample_io"]
                )
            sample_text = user_message.strip()

        try:
            sample_io(
                db=self.db,
                confab_id=self.confab_id,
                sample_text=sample_text
            )
            return StageResult(
                status="complete",
                data={"sample": sample_text},
                summary="Example interaction recorded."
            )
        except Exception as e:
            logger.error(f"[Foreman V2] Sample I/O save failed: {e}")
            return StageResult(
                status="error",
                error_message=f"Failed to save example: {str(e)}"
            )

    async def _handle_review(self, user_message: str) -> StageResult:
        """Handle the review and save stage using structured extraction."""
        msg_lower = user_message.lower()

        # Check if user wants to see the configuration (before LLM extraction)
        if any(w in msg_lower for w in ["show", "display", "view", "see", "what is", "what's"]) and \
           any(w in msg_lower for w in ["config", "configuration", "summary", "settings", "setup"]):
            self.db.refresh(self.confab)
            config_summary = self._build_config_summary()
            return StageResult(
                status="clarify",
                summary=f"Here's your current configuration:{config_summary}",
                next_question="Ready to save and deploy, or would you like to make changes?"
            )

        # Use structured LLM extraction
        extraction = await extract_review_intent(user_message)

        if extraction.success:
            data = extraction.data
            intent = data.get("intent", "unclear")

            if intent == "confirm":
                try:
                    review_and_save(db=self.db, confab_id=self.confab_id)
                    return StageResult(
                        status="complete",
                        data={"saved": True},
                        summary="Configuration saved. Your agent is ready to deploy."
                    )
                except Exception as e:
                    logger.error(f"[Foreman V2] Review save failed: {e}")
                    return StageResult(
                        status="error",
                        error_message=f"Failed to save configuration: {str(e)}"
                    )

            elif intent == "edit":
                edit_target = data.get("edit_target", "any section")
                return StageResult(
                    status="clarify",
                    summary=f"What would you like to change about the {edit_target}?",
                    next_question="You can update the purpose, participants, memory, tools, guardrails, or examples."
                )

            else:  # unclear
                if data.get("clarification_needed"):
                    return StageResult(
                        status="clarify",
                        next_question=data["clarification_needed"]
                    )

        # Fallback to keyword matching (msg_lower already defined at start)
        if any(w in msg_lower for w in ["yes", "save", "confirm", "deploy", "done", "ready", "looks good"]):
            try:
                review_and_save(db=self.db, confab_id=self.confab_id)
                return StageResult(
                    status="complete",
                    data={"saved": True},
                    summary="Configuration saved. Your agent is ready to deploy."
                )
            except Exception as e:
                logger.error(f"[Foreman V2] Review save failed: {e}")
                return StageResult(
                    status="error",
                    error_message=f"Failed to save configuration: {str(e)}"
                )

        if any(w in msg_lower for w in ["change", "edit", "modify", "update", "go back"]):
            return StageResult(
                status="clarify",
                summary="What would you like to change?",
                next_question="You can update the purpose, participants, memory, tools, guardrails, or examples."
            )

        # Default: ask for confirmation
        return StageResult(
            status="clarify",
            next_question=STAGE_CLARIFICATIONS["review"]
        )
