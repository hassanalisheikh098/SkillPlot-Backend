import logging
from typing import List, Optional
from fastapi import APIRouter, status
from pydantic import BaseModel, Field
from app.services.supabase_client import supabase

router = APIRouter()
logger = logging.getLogger(__name__)


class UserProfileResponse(BaseModel):
    full_name: Optional[str] = Field(None, description="The user's full name")
    target_role: Optional[str] = Field(None, description="The target career role")
    extracted_skills: List[str] = Field(default=[], description="List of extracted skills")
    experience_summary: Optional[str] = Field(None, description="Extracted professional experience summary")
    education_summary: Optional[str] = Field(None, description="Extracted education summary")
    resume_filename: Optional[str] = Field(None, description="Uploaded resume filename")
    resume_uploaded_at: Optional[str] = Field(None, description="Timestamp of resume upload")


@router.get(
    "/profile/{user_id}",
    response_model=UserProfileResponse,
    status_code=status.HTTP_200_OK,
)
async def get_user_profile(user_id: str) -> UserProfileResponse:
    """
    Retrieve user profile details including resume parsing results.
    """
    logger.info(f"Received request to fetch user profile for user_id: '{user_id}'")
    if not supabase:
        logger.warning("Supabase client is not connected.")
        return UserProfileResponse()

    try:
        result = (
            supabase.table("user_profiles")
            .select(
                "full_name, target_role, extracted_skills, experience_summary, education_summary, resume_filename, resume_uploaded_at"
            )
            .eq("id", user_id)
            .maybe_single()
            .execute()
        )
        row = result.data

        if not row:
            logger.info(f"No user profile found in database for user_id: '{user_id}'")
            return UserProfileResponse()

        return UserProfileResponse(
            full_name=row.get("full_name"),
            target_role=row.get("target_role"),
            extracted_skills=row.get("extracted_skills") or [],
            experience_summary=row.get("experience_summary"),
            education_summary=row.get("education_summary"),
            resume_filename=row.get("resume_filename"),
            resume_uploaded_at=row.get("resume_uploaded_at"),
        )
    except Exception as e:
        logger.error(f"Error fetching user profile for user '{user_id}': {e}")
        return UserProfileResponse()
