import datetime
import logging
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models import User, Confab, Thread, ThreadParticipant, Message
from schemas import (
    ThreadCreate, ThreadResponse, ThreadWithParticipants,
    ParticipantAdd, ParticipantResponse,
    MessageCreate, MessageResponse, ChatRequest, ChatResponse,
    SetupProgressResponse, ForemanChatResponse, ForemanV2Metadata,
)
from deps import get_current_user
from llm_service import ask_llm
from foreman import Foreman
from foreman_v3 import FOREMAN_V3_ENABLED, ForemanV3

logger = logging.getLogger(__name__)
router = APIRouter(tags=["conversations"])


# =============================================================================
# Thread Routes
# =============================================================================

@router.get("/threads", response_model=List[ThreadResponse])
async def list_threads(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    threads = db.query(Thread).filter(Thread.owner_user_id == current_user.id).order_by(Thread.created_at.desc()).all()
    return [ThreadResponse.model_validate(t) for t in threads]


@router.post("/threads", response_model=ThreadResponse)
async def create_thread(body: ThreadCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db_thread = Thread(name=body.name, owner_user_id=current_user.id)
    db.add(db_thread)
    db.commit()
    db.refresh(db_thread)
    owner_participant = ThreadParticipant(thread_id=db_thread.id, participant_type="user", participant_id=current_user.id, role="owner")
    db.add(owner_participant)
    db.commit()
    return ThreadResponse.model_validate(db_thread)


@router.get("/threads/{thread_id}", response_model=ThreadWithParticipants)
async def get_thread(
    thread_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    thread = db.query(Thread).filter(Thread.id == thread_id, Thread.owner_user_id == current_user.id).first()
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")

    participants = db.query(ThreadParticipant).filter(ThreadParticipant.thread_id == thread_id).all()

    return ThreadWithParticipants(
        id=thread.id,
        name=thread.name,
        owner_user_id=thread.owner_user_id,
        created_at=thread.created_at,
        participants=[ParticipantResponse.model_validate(p) for p in participants]
    )


@router.delete("/threads/{thread_id}")
async def delete_thread(thread_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    thread = db.query(Thread).filter(Thread.id == thread_id, Thread.owner_user_id == current_user.id).first()
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")
    db.query(Message).filter(Message.thread_id == thread_id).delete(synchronize_session=False)
    db.query(ThreadParticipant).filter(ThreadParticipant.thread_id == thread_id).delete(synchronize_session=False)
    db.delete(thread)
    db.commit()
    return {"message": "Thread deleted"}


# =============================================================================
# Thread Participants Routes
# =============================================================================

@router.get("/threads/{thread_id}/participants", response_model=List[ParticipantResponse])
async def list_participants(
    thread_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    thread = db.query(Thread).filter(Thread.id == thread_id, Thread.owner_user_id == current_user.id).first()
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")

    participants = db.query(ThreadParticipant).filter(ThreadParticipant.thread_id == thread_id, ThreadParticipant.is_active == True).all()
    return [ParticipantResponse.model_validate(p) for p in participants]


@router.post("/threads/{thread_id}/participants", response_model=ParticipantResponse)
async def add_participant(
    thread_id: int,
    participant: ParticipantAdd,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    thread = db.query(Thread).filter(Thread.id == thread_id, Thread.owner_user_id == current_user.id).first()
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")

    # Validate participant exists (for user/confab types)
    if participant.participant_type == "user" and participant.participant_id:
        if not db.query(User).filter(User.id == participant.participant_id).first():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User not found")
    elif participant.participant_type == "confab" and participant.participant_id:
        if not db.query(Confab).filter(Confab.id == participant.participant_id).first():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Confab not found")
    elif participant.participant_type == "system" and not participant.system_agent_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="System agent name required")

    db_participant = ThreadParticipant(
        thread_id=thread_id,
        participant_type=participant.participant_type,
        participant_id=participant.participant_id,
        system_agent_name=participant.system_agent_name,
        role=participant.role,
    )
    db.add(db_participant)
    db.commit()
    db.refresh(db_participant)
    return ParticipantResponse.model_validate(db_participant)


@router.delete("/threads/{thread_id}/participants/{participant_id}")
async def remove_participant(
    thread_id: int,
    participant_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    thread = db.query(Thread).filter(Thread.id == thread_id, Thread.owner_user_id == current_user.id).first()
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")

    participant = db.query(ThreadParticipant).filter(
        ThreadParticipant.id == participant_id,
        ThreadParticipant.thread_id == thread_id
    ).first()
    if not participant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Participant not found")

    # Soft delete - mark as inactive
    participant.is_active = False
    participant.left_at = datetime.datetime.now(datetime.timezone.utc)
    db.commit()
    return {"message": "Participant removed"}


# =============================================================================
# Messages Routes
# =============================================================================

@router.get("/threads/{thread_id}/messages", response_model=List[MessageResponse])
async def list_messages(
    thread_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    thread = db.query(Thread).filter(Thread.id == thread_id, Thread.owner_user_id == current_user.id).first()
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")

    messages = db.query(Message).filter(Message.thread_id == thread_id).order_by(Message.created_at).all()
    return [MessageResponse.model_validate(m) for m in messages]


@router.post("/threads/{thread_id}/messages", response_model=MessageResponse)
async def add_message(
    thread_id: int,
    request: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Add a message to a thread without triggering agent responses.
    Used for saving initial greetings, persisting messages, etc.
    For full chat with agent responses, use POST /threads/{id}/chat instead.
    """
    thread = db.query(Thread).filter(Thread.id == thread_id, Thread.owner_user_id == current_user.id).first()
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")

    # Calculate depth for subthreading
    depth = 0
    if request.in_reply_to:
        parent = db.query(Message).filter(Message.id == request.in_reply_to).first()
        if parent:
            depth = parent.depth + 1

    message = Message(
        thread_id=thread_id,
        sender_type=request.sender_type,
        sender_id=request.sender_id or (current_user.id if request.sender_type == "user" else None),
        sender_name=request.sender_name or (current_user.name if request.sender_type == "user" else None),
        content=request.content,
        role=request.role,
        in_reply_to=request.in_reply_to,
        depth=depth,
        addressed_to=[a.model_dump() for a in request.addressed_to] if request.addressed_to else None,
    )
    db.add(message)
    db.commit()
    db.refresh(message)

    return MessageResponse.model_validate(message)


# =============================================================================
# Chat Route (unified endpoint with auto-response)
# =============================================================================

async def should_agent_respond(message_content: str, addressed_to: Optional[List], agent_participant: ThreadParticipant, thread_context: List[Message]) -> bool:
    """Determine if an agent should respond to a message."""
    # If explicitly addressed to this agent, respond
    if addressed_to:
        for addr in addressed_to:
            if addr.get("type") == agent_participant.participant_type:
                if agent_participant.participant_type == "system":
                    if addr.get("name") == agent_participant.system_agent_name:
                        return True
                elif addr.get("id") == agent_participant.participant_id:
                    return True
        return False  # Addressed to someone else

    # Broadcast message - infer from context
    # For now, agents always respond to broadcasts in threads where they participate
    return True


@router.post("/threads/{thread_id}/chat", response_model=ChatResponse)
async def chat(
    thread_id: int,
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Unified chat endpoint with automatic agent responses."""
    thread = db.query(Thread).filter(Thread.id == thread_id, Thread.owner_user_id == current_user.id).first()
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")

    depth = 0
    if request.in_reply_to:
        parent = db.query(Message).filter(Message.id == request.in_reply_to).first()
        if parent:
            depth = parent.depth + 1

    user_message = Message(
        thread_id=thread_id,
        sender_type="user",
        sender_id=current_user.id,
        sender_name=current_user.name,
        content=request.content,
        role="user",
        in_reply_to=request.in_reply_to,
        depth=depth,
        addressed_to=[a.model_dump() for a in request.addressed_to] if request.addressed_to else None,
    )
    db.add(user_message)
    db.commit()
    db.refresh(user_message)

    agent_participants = db.query(ThreadParticipant).filter(
        ThreadParticipant.thread_id == thread_id,
        ThreadParticipant.is_active == True,
        ThreadParticipant.participant_type.in_(["confab", "system"])
    ).all()

    thread_messages = db.query(Message).filter(Message.thread_id == thread_id).order_by(Message.created_at).limit(20).all()

    agent_responses = []
    foreman_result = None

    for agent in agent_participants:
        should_respond = await should_agent_respond(
            request.content,
            [a.model_dump() for a in request.addressed_to] if request.addressed_to else None,
            agent,
            thread_messages
        )
        if not should_respond:
            continue

        try:
            if agent.participant_type == "system" and agent.system_agent_name == "foreman":
                confab = db.query(Confab).filter(
                    Confab.user_id == current_user.id,
                    Confab.status == "building"
                ).order_by(Confab.created_at.desc()).first()

                if confab:
                    if FOREMAN_V3_ENABLED:
                        logger.info(f"[Chat] Using Foreman V3 (LangGraph) for confab {confab.id}")
                        foreman = ForemanV3(confab.id, db)
                        await foreman.initialize()
                        result = await foreman.process_message(
                            request.content,
                            thread_id=thread_id,
                            thread_history=thread_messages
                        )
                    else:
                        logger.warning(f"[Chat] Falling back to legacy Foreman for confab {confab.id}")
                        foreman = Foreman(confab.id, db)
                        await foreman.initialize()
                        result = await foreman.process_message(request.content)
                    response_content = result.get("response", "")
                    foreman_result = result
                else:
                    response_content = "No confab is currently being built. Please start a new confab to begin."

                sender_name = "Foreman"

            elif agent.participant_type == "confab":
                confab = db.query(Confab).filter(Confab.id == agent.participant_id).first()
                if not confab:
                    continue
                if confab.status == "building":
                    continue

                context = f"You are {confab.name}. "
                if confab.purpose:
                    context += f"Your purpose: {confab.purpose}\n"
                if confab.guardrails:
                    context += f"Guardrails: {confab.guardrails}\n"
                context += "\nConversation:\n"
                for msg in thread_messages[-10:]:
                    role = "User" if msg.role == "user" else "Assistant"
                    context += f"{role}: {msg.content}\n"
                context += f"User: {request.content}\n"

                response_content = await ask_llm(prompt=context, temperature=confab.temperature)
                sender_name = confab.name
            else:
                continue

            agent_message = Message(
                thread_id=thread_id,
                sender_type=agent.participant_type,
                sender_id=agent.participant_id,
                sender_name=sender_name,
                content=response_content,
                role="assistant",
                in_reply_to=user_message.id,
                depth=user_message.depth,
            )
            db.add(agent_message)
            db.commit()
            db.refresh(agent_message)
            agent_responses.append(MessageResponse.model_validate(agent_message))

        except Exception as e:
            logger.error(f"Error generating response from agent {agent.id}: {e}")
            continue

    foreman_metadata = None
    if foreman_result:
        setup_progress = foreman_result.get("setup_progress")
        v2_data = foreman_result.get("v2_metadata")
        is_v3 = foreman_result.get("is_v3", False)
        is_v2 = foreman_result.get("is_v2", v2_data is not None and not is_v3)

        foreman_metadata = ForemanChatResponse(
            response=foreman_result.get("response", ""),
            confab_id=foreman_result.get("confab_id", 0),
            thread_id=thread_id,
            setup_progress=SetupProgressResponse(**setup_progress) if setup_progress else None,
            tool_calls=foreman_result.get("tool_calls", []),
            timestamp=datetime.datetime.fromisoformat(foreman_result.get("timestamp", datetime.datetime.now().isoformat())),
            v2_metadata=ForemanV2Metadata(
                stage=v2_data.get("stage", ""),
                stage_status=v2_data.get("stage_status"),
                saved_fields=v2_data.get("saved_fields"),
                next_question=v2_data.get("next_question"),
                next_stage=setup_progress.get("current_stage") if setup_progress else None,
                clarification_needed=v2_data.get("stage_status") == "clarify" if v2_data else False,
                ui_hint=v2_data.get("ui_hint"),
            ) if v2_data else None,
            is_v2=is_v2,
            is_v3=is_v3,
        )

    return ChatResponse(
        thread_id=thread_id,
        user_message=MessageResponse.model_validate(user_message),
        agent_responses=agent_responses,
        timestamp=datetime.datetime.now(datetime.timezone.utc),
        foreman_metadata=foreman_metadata,
    )
