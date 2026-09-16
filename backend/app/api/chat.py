"""
DevLens AI — Chat & LLM Router
Provides AI-powered chat about repositories using Groq LLM.
Conversation history is persisted in chat_conversations / chat_messages tables.
"""
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.auth.dependencies import CurrentUserId
from app.config import get_settings
from app.database import get_db_context
from app.models import (
    ChatConversation, ChatMessage, Repository,
    GraphNode,
)

router = APIRouter(tags=["chat"])
settings = get_settings()


# ── Schemas ──────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    conversation_id: Optional[str] = None
    message: str


class CitationOut(BaseModel):
    node_id: str
    file_path: str
    start_line: int
    end_line: int


class ChatMessageOut(BaseModel):
    id: Optional[str] = None
    role: str
    content: str
    citations: Optional[list[CitationOut]] = None
    created_at: Optional[str] = None


class ChatResponseOut(BaseModel):
    conversation_id: str
    message: ChatMessageOut


class ConversationOut(BaseModel):
    id: str
    title: Optional[str] = None
    created_at: str


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_groq_client():
    from groq import Groq
    return Groq(api_key=settings.groq_api_key)


async def _fetch_context_nodes(db, repo_id: uuid.UUID, query: str, limit: int = 8) -> list:
    """
    Simple keyword-based context retrieval.
    Returns top-N graph nodes matching the query.
    """
    result = await db.execute(
        select(GraphNode)
        .where(
            GraphNode.repository_id == repo_id,
            GraphNode.node_type.in_(["function", "class", "method"]),
        )
        .limit(300)
    )
    nodes = result.scalars().all()

    keywords = set(q.lower() for q in query.split() if len(q) > 2)
    scored = []
    for node in nodes:
        text = f"{node.name} {node.docstring or ''} {node.qualified_name}".lower()
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            scored.append((score, node))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [n for _, n in scored[:limit]]


def _build_system_prompt(repo_name: str, context_nodes: list) -> str:
    ctx_parts = []
    for node in context_nodes:
        part = f"[{node.node_type.upper()}] {node.qualified_name}"
        if node.signature:
            part += f"\nSignature: {node.signature}"
        if node.docstring:
            part += f"\nDocstring: {node.docstring}"
        if node.start_line:
            part += f"\nLocation: lines {node.start_line}–{node.end_line}"
        ctx_parts.append(part)

    context_str = "\n\n".join(ctx_parts) if ctx_parts else "No specific code context found for this query."

    return f"""You are DevLens AI, an expert code analyst for the repository "{repo_name}".
You help engineers understand codebases by answering questions about architecture, code flow, functions, and design decisions.

Relevant code context extracted from the repository:
---
{context_str}
---

Guidelines:
- Be precise and technical. Reference specific function names, file paths, and line numbers when relevant.
- If you are unsure, say so — do not hallucinate code that does not exist.
- When referencing code, use backticks for inline code and triple backticks for blocks.
- Keep responses focused and actionable.
"""


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/repositories/{repository_id}/chat", response_model=ChatResponseOut)
async def chat_with_repo(
    repository_id: uuid.UUID,
    body: ChatRequest,
    user_id: CurrentUserId,
):
    """Send a message and get an AI response with code citations (FR-7)."""
    async with get_db_context() as db:
        repo_result = await db.execute(
            select(Repository).where(
                Repository.id == repository_id,
                Repository.owner_user_id == user_id,
            )
        )
        repo = repo_result.scalar_one_or_none()
        if not repo:
            raise HTTPException(status_code=404, detail="Repository not found")

        # Get or create conversation
        conversation: Optional[ChatConversation] = None
        if body.conversation_id:
            try:
                conv_uuid = uuid.UUID(body.conversation_id)
                conv_result = await db.execute(
                    select(ChatConversation).where(
                        ChatConversation.id == conv_uuid,
                        ChatConversation.user_id == user_id,
                    )
                )
                conversation = conv_result.scalar_one_or_none()
            except (ValueError, Exception):
                pass

        if not conversation:
            conversation = ChatConversation(
                repository_id=repository_id,
                user_id=user_id,
                title=body.message[:80],
            )
            db.add(conversation)
            await db.flush()

        # Fetch previous messages (last 10)
        prev_msgs_result = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.conversation_id == conversation.id)
            .order_by(ChatMessage.created_at.desc())
            .limit(10)
        )
        prev_msgs = list(reversed(prev_msgs_result.scalars().all()))

        # Save user message
        user_msg = ChatMessage(
            conversation_id=conversation.id,
            role="user",
            content=body.message,
        )
        db.add(user_msg)
        await db.flush()

        # Fetch relevant code context
        context_nodes = await _fetch_context_nodes(db, repository_id, body.message)

        # Build LLM messages
        system_prompt = _build_system_prompt(repo.full_name, context_nodes)
        messages_for_llm = [{"role": "system", "content": system_prompt}]
        for msg in prev_msgs:
            messages_for_llm.append({"role": msg.role, "content": msg.content})
        messages_for_llm.append({"role": "user", "content": body.message})

        # Call LLM
        assistant_content = ""
        if settings.groq_api_key:
            try:
                client = _get_groq_client()
                completion = client.chat.completions.create(
                    model=settings.groq_model,
                    messages=messages_for_llm,
                    max_tokens=2048,
                    temperature=0.3,
                )
                assistant_content = completion.choices[0].message.content or ""
            except Exception as e:
                assistant_content = (
                    f"I encountered an error calling the LLM: {str(e)}. "
                    "Please check your GROQ_API_KEY in the .env file."
                )
        else:
            node_list = "\n".join(
                f"- **{n.name}** ({n.node_type}) at `{n.qualified_name}`"
                for n in context_nodes
            )
            assistant_content = (
                "⚠️ No LLM API key configured. Set `GROQ_API_KEY` in your `.env` file to enable AI chat.\n\n"
                f"Relevant code entities found for your query:\n\n{node_list or 'None found.'}"
            )

        # Build citations
        citations = [
            {
                "node_id": str(node.id),
                "file_path": node.qualified_name.split("::")[0] if "::" in node.qualified_name else node.name,
                "start_line": node.start_line or 0,
                "end_line": node.end_line or 0,
            }
            for node in context_nodes[:5]
            if node.start_line
        ]

        # Save assistant message
        assistant_msg = ChatMessage(
            conversation_id=conversation.id,
            role="assistant",
            content=assistant_content,
            citations_json=citations if citations else None,
        )
        db.add(assistant_msg)
        await db.flush()
        await db.commit()

        return ChatResponseOut(
            conversation_id=str(conversation.id),
            message=ChatMessageOut(
                id=str(assistant_msg.id),
                role="assistant",
                content=assistant_content,
                citations=[CitationOut(**c) for c in citations] if citations else None,
                created_at=assistant_msg.created_at.isoformat() if assistant_msg.created_at else None,
            ),
        )


@router.get("/repositories/{repository_id}/chat/conversations", response_model=dict)
async def list_conversations(
    repository_id: uuid.UUID,
    user_id: CurrentUserId,
):
    """List all chat conversations for a repository."""
    async with get_db_context() as db:
        result = await db.execute(
            select(ChatConversation)
            .where(
                ChatConversation.repository_id == repository_id,
                ChatConversation.user_id == user_id,
            )
            .order_by(ChatConversation.created_at.desc())
        )
        conversations = result.scalars().all()

    return {
        "conversations": [
            ConversationOut(
                id=str(c.id),
                title=c.title,
                created_at=c.created_at.isoformat(),
            )
            for c in conversations
        ]
    }


@router.get("/chat/conversations/{conversation_id}/messages", response_model=dict)
async def get_messages(
    conversation_id: uuid.UUID,
    user_id: CurrentUserId,
):
    """Get all messages in a conversation."""
    async with get_db_context() as db:
        conv_result = await db.execute(
            select(ChatConversation).where(
                ChatConversation.id == conversation_id,
                ChatConversation.user_id == user_id,
            )
        )
        conv = conv_result.scalar_one_or_none()
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")

        msgs_result = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.conversation_id == conversation_id)
            .order_by(ChatMessage.created_at.asc())
        )
        messages = msgs_result.scalars().all()

    return {
        "messages": [
            ChatMessageOut(
                id=str(m.id),
                role=m.role,
                content=m.content,
                citations=[CitationOut(**c) for c in (m.citations_json or [])],
                created_at=m.created_at.isoformat() if m.created_at else None,
            )
            for m in messages
        ]
    }
