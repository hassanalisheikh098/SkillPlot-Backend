import logging
import uuid
from typing import List, Optional
from fastapi import APIRouter, status, HTTPException
from pydantic import BaseModel, Field
from groq import AsyncGroq

from app.config import settings
from app.services.supabase_client import supabase

router = APIRouter()
logger = logging.getLogger(__name__)


class ChatMessage(BaseModel):
    """
    A single turn in the conversation — either a user message or an assistant reply.
    """
    role: str = Field(..., description="Speaker role: 'user' or 'assistant'")
    content: str = Field(..., description="Text content of the message")


class ChatbotRequest(BaseModel):
    """
    Request payload representing the chatbot input from the client.
    """
    message: str = Field(..., description="The user's career or coding question")
    target_role: Optional[str] = Field(
        None, description="The job role the user is aiming for"
    )
    missing_skills: Optional[List[str]] = Field(
        None, description="List of skills the user needs to acquire"
    )
    user_skills: Optional[List[str]] = Field(
        default=[], description="List of skills the user already has"
    )
    history: Optional[List[ChatMessage]] = Field(
        default=[], description="Previous conversation turns for multi-turn context"
    )
    user_name: Optional[str] = Field(None, description="The user's name")
    experience_summary: Optional[str] = Field(None, description="The user's professional experience summary")
    education_summary: Optional[str] = Field(None, description="The user's education summary")


class ChatbotResponse(BaseModel):
    """
    Response payload returned to the Flutter application.
    """
    status: str = Field(..., description="Operation status (success/error)")
    reply: str = Field(..., description="The AI career coach's response")
    updated_history: List[ChatMessage] = Field(
        ..., description="Full conversation history including the latest exchange"
    )


def _get_fallback_reply(
    message: str,
    target_role: Optional[str],
    missing_skills: Optional[List[str]],
    user_skills: Optional[List[str]] = None,
) -> str:
    """
    Dynamic offline mock coaching reply to use as a fallback.
    """
    if target_role and missing_skills:
        skills_str = ", ".join(missing_skills)
        return (
            f"To transition into a {target_role}, focus on building project-based proofs of concept. "
            f"For your gap in {skills_str}, try setting up a small repository today. "
            "Breaking these technologies down into single-day milestones is the fastest way to master them!"
        )
    elif target_role:
        return (
            f"If you're targeting a {target_role} role, double-down on creating a strong public portfolio. "
            "Select 2 key projects that showcase your core architectures and version control habits. "
            "Publish them to GitHub and write clean README files to demonstrate your professional standards."
        )
    else:
        return (
            "The most effective way to accelerate your career growth is through active, hands-on building. "
            "Find a specific problem, build a tool to solve it, and deploy it to a free hosting tier. "
            "Continuous, daily progress is the key to mastering new technical fields!"
        )


@router.post("/chat", response_model=ChatbotResponse, status_code=status.HTTP_200_OK)
async def chat(request: ChatbotRequest) -> ChatbotResponse:
    """
    Career Chatbot endpoint that passes user messages, targeted role, and missing
    skills to the Groq Llama-3.1 model to generate concise, tactical coaching.
    """
    user_message = request.message
    target_role = request.target_role
    missing_skills = request.missing_skills

    # Validate that we have a configured key. If not, trigger fallback early.
    api_key = settings.GROQ_API_KEY.strip()
    if not api_key or api_key == "your-groq-api-key" or "gsk_" not in api_key:
        logger.warning(
            "Groq API Key is not configured or uses placeholder credentials. "
            "Routing request to local career coach fallback."
        )
        fallback_reply = _get_fallback_reply(
            user_message, target_role, missing_skills, request.user_skills
        )
        updated_history = list(request.history or []) + [
            ChatMessage(role="user", content=user_message),
            ChatMessage(role="assistant", content=fallback_reply),
        ]
        return ChatbotResponse(
            status="success",
            reply=fallback_reply,
            updated_history=updated_history,
        )

    # Construct the Career Coach system prompt
    coach_target = request.user_name if request.user_name else 'this candidate'
    system_prompt = f"You are a personal AI career coach for {coach_target}. "

    if request.experience_summary:
        system_prompt += f"They have this background: {request.experience_summary}. "
    if request.education_summary:
        system_prompt += f"Their education: {request.education_summary}. "
    if request.user_skills:
        system_prompt += f"Their current skills include: {', '.join(request.user_skills[:10])}. "
    if target_role:
        system_prompt += f"They are targeting a {target_role} role. "
    if missing_skills:
        system_prompt += f"Their skill gaps are: {', '.join(missing_skills)}. "

    system_prompt += (
        "Address them by first name when possible. Be warm, specific, and direct. "
        "Keep responses under 4 sentences for mobile readability."
    )

    try:
        # Build the messages list: system prompt + last 6 history turns + current message
        messages = [{"role": "system", "content": system_prompt}]

        if request.history:
            for msg in request.history[-6:]:
                messages.append({"role": msg.role, "content": msg.content})

        messages.append({"role": "user", "content": user_message})

        # Call Groq asynchronously using the AsyncGroq client
        client = AsyncGroq(api_key=api_key)
        completion = await client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=messages,
            max_tokens=180,
            temperature=0.7,
        )

        reply = completion.choices[0].message.content.strip()
        logger.info("Successfully fetched AI response from Groq client.")

        updated_history = list(request.history or []) + [
            ChatMessage(role="user", content=user_message),
            ChatMessage(role="assistant", content=reply),
        ]
        return ChatbotResponse(
            status="success",
            reply=reply,
            updated_history=updated_history,
        )

    except Exception as e:
        logger.error(
            f"Failed to fetch response from Groq SDK due to: {e}. "
            "Gracefully serving dynamic fallback coaching data."
        )
        fallback_reply = _get_fallback_reply(
            user_message, target_role, missing_skills, request.user_skills
        )
        updated_history = list(request.history or []) + [
            ChatMessage(role="user", content=user_message),
            ChatMessage(role="assistant", content=fallback_reply),
        ]
        return ChatbotResponse(
            status="success",
            reply=fallback_reply,
            updated_history=updated_history,
        )


class ChatHistorySaveRequest(BaseModel):
    user_id: str = Field(..., description="The user UUID")
    messages: List[ChatMessage] = Field(..., description="List of messages to save")


class ChatHistoryMessageResponse(BaseModel):
    role: str = Field(..., description="Author role")
    content: str = Field(..., description="Message text")
    created_at: Optional[str] = Field(None, description="Message creation timestamp")


class ChatHistoryResponse(BaseModel):
    status: str = Field(..., description="Operation status")
    messages: Optional[List[ChatHistoryMessageResponse]] = Field(None, description="List of retrieved messages")
    count: Optional[int] = Field(None, description="Number of saved messages")


@router.post("/save-history", status_code=status.HTTP_200_OK)
async def save_history(request: ChatHistorySaveRequest):
    """
    Save the chat history to Supabase for the user, retaining only the last 30 turns.
    """
    logger.info(f"Saving chat history for user: {request.user_id}")
    try:
        user_id = request.user_id.strip()
        if not user_id:
            logger.error("Empty user_id provided.")
            return {"status": "skipped"}

        # Validate UUID
        try:
            uuid.UUID(user_id)
        except ValueError:
            logger.error(f"Invalid UUID format: {user_id}")
            return {"status": "skipped"}

        if not supabase:
            logger.warning("Supabase client is not connected.")
            return {"status": "skipped"}

        # Delete existing history for user_id to refresh it
        try:
            supabase.table("chat_history").delete().eq("user_id", user_id).execute()
        except Exception as e:
            logger.warning(f"Error during deletion of old chat history: {e}")

        # Slice to last 30 messages to avoid bloat
        messages = request.messages[-30:]
        payload = [{"user_id": user_id, "role": m.role, "content": m.content} for m in messages]

        if payload:
            supabase.table("chat_history").insert(payload).execute()

        logger.info(f"Successfully saved {len(payload)} chat history messages for user '{user_id}'.")
        return {"status": "saved", "count": len(payload)}
    except Exception as e:
        logger.error(f"Unexpected error in save_history endpoint: {e}")
        return {"status": "skipped"}


@router.get("/history/{user_id}", response_model=ChatHistoryResponse, status_code=status.HTTP_200_OK)
async def get_history(user_id: str) -> ChatHistoryResponse:
    """
    Retrieve user chat history from Supabase (up to last 30 turns).
    """
    logger.info(f"Fetching chat history for user '{user_id}'.")
    try:
        user_id = user_id.strip()
        if not user_id:
            logger.error("Empty user_id provided for history retrieval.")
            return ChatHistoryResponse(status="success", messages=[])

        # Validate UUID
        try:
            uuid.UUID(user_id)
        except ValueError:
            logger.error(f"Invalid UUID format for history retrieval: {user_id}")
            return ChatHistoryResponse(status="success", messages=[])

        if not supabase:
            logger.warning("Supabase client is not connected.")
            return ChatHistoryResponse(status="success", messages=[])

        result = (
            supabase.table("chat_history")
            .select("role, content, created_at")
            .eq("user_id", user_id)
            .order("created_at", desc=False)
            .limit(30)
            .execute()
        )

        mapped_messages = []
        for row in result.data or []:
            mapped_messages.append(
                ChatHistoryMessageResponse(
                    role=row.get("role"),
                    content=row.get("content"),
                    created_at=row.get("created_at")
                )
            )

        logger.info(f"Retrieved {len(mapped_messages)} messages for user '{user_id}'.")
        return ChatHistoryResponse(status="success", messages=mapped_messages)
    except Exception as e:
        logger.error(f"Unexpected error retrieving chat history: {e}")
        return ChatHistoryResponse(status="success", messages=[])
