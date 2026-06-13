import logging
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
from pydantic import BaseModel, Field

from app.services.nlp_service import (
    extract_text_from_pdf,
    extract_skills,
    extract_experience,
    extract_education,
    extract_full_name,
)
from app.services.supabase_client import supabase

router = APIRouter()
logger = logging.getLogger(__name__)


class ResumeUploadSuccessResponse(BaseModel):
    """
    Response model matching the expected structure of the Flutter application.
    """
    status: str = Field(..., description="The status of the operation (success/error)")
    filename: str = Field(..., description="The name of the uploaded PDF resume")
    extracted_skills: List[str] = Field(
        ..., description="List of unique, sorted skills matched from the resume"
    )


@router.post(
    "/upload-resume",
    response_model=ResumeUploadSuccessResponse,
    status_code=status.HTTP_200_OK,
)
async def upload_resume(
    file: UploadFile = File(...),
    user_id: Optional[str] = Form(None),
) -> ResumeUploadSuccessResponse:
    """
    Upload a resume in PDF format, extract the text, scan it for skills,
    and return the results.
    """
    # Enforce PDF files only for compatibility
    if not file.filename.lower().endswith(".pdf"):
        logger.warning(f"Rejected non-PDF upload attempt: {file.filename}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF documents are supported for upload.",
        )

    try:
        # Read the file bytes in memory
        file_bytes = await file.read()

        # Extract text from the PDF file
        extracted_text = extract_text_from_pdf(file_bytes)

        # Scan text for skills, experience, education, and full name
        extracted_skills = extract_skills(extracted_text)
        experience_summary = extract_experience(extracted_text)
        education_summary = extract_education(extracted_text)
        full_name = extract_full_name(extracted_text)

        logger.info(f"Processed {file.filename} successfully. Found {len(extracted_skills)} skills.")

        # Persist profile to Supabase if a user_id was provided.
        # This is best-effort — a failure here must never fail the upload response.
        if supabase and user_id:
            try:
                upsert_payload = {
                    "id": user_id,
                    "extracted_skills": extracted_skills,
                    "experience_summary": experience_summary,
                    "education_summary": education_summary,
                    "full_name": full_name if full_name else None,
                    "resume_filename": file.filename,
                    "resume_uploaded_at": datetime.now(timezone.utc).isoformat(),
                }
                supabase.table("user_profiles").upsert(
                    upsert_payload,
                    on_conflict="id",
                ).execute()
                logger.info(
                    f"Saved profile details to user_profiles for user '{user_id}'."
                )
            except Exception as e:
                logger.warning(
                    f"Could not save profile details to Supabase for user '{user_id}': {e}"
                )

        return ResumeUploadSuccessResponse(
            status="success",
            filename=file.filename,
            extracted_skills=extracted_skills,
        )

    except ValueError as ve:
        logger.error(f"Validation or parsing error in resume upload: {ve}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(ve),
        )
    except Exception as e:
        logger.error(f"Unexpected error during resume processing: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while parsing the resume: {str(e)}",
        )


class ResumeProfileResponse(BaseModel):
    status: str = Field(..., description="Operation status (success/not_found/error)")
    user_id: str = Field(..., description="The user UUID")
    full_name: Optional[str] = Field(None, description="The user's full name")
    extracted_skills: List[str] = Field(default=[], description="Extracted skills list")
    experience_summary: Optional[str] = Field(None, description="Professional experience summary")
    education_summary: Optional[str] = Field(None, description="Education summary")
    resume_filename: Optional[str] = Field(None, description="Uploaded resume filename")
    resume_uploaded_at: Optional[str] = Field(None, description="Resume upload timestamp")
    target_role: Optional[str] = Field(None, description="Target career role")


@router.get(
    "/profile/{user_id}",
    response_model=ResumeProfileResponse,
    status_code=status.HTTP_200_OK,
)
async def get_resume_profile(user_id: str) -> ResumeProfileResponse:
    """
    Retrieve user resume profile details from user_profiles.
    """
    logger.info(f"Received request to fetch resume profile for user '{user_id}'.")
    try:
        if not supabase:
            logger.warning("Supabase client is not connected.")
            return ResumeProfileResponse(
                status="not_found",
                user_id=user_id,
            )

        result = (
            supabase.table("user_profiles")
            .select("*")
            .eq("id", user_id)
            .maybe_single()
            .execute()
        )
        row = result.data

        if not row:
            logger.info(f"No resume profile found for user '{user_id}'.")
            return ResumeProfileResponse(
                status="not_found",
                user_id=user_id,
            )

        return ResumeProfileResponse(
            status="success",
            user_id=user_id,
            full_name=row.get("full_name"),
            extracted_skills=row.get("extracted_skills") or [],
            experience_summary=row.get("experience_summary"),
            education_summary=row.get("education_summary"),
            resume_filename=row.get("resume_filename"),
            resume_uploaded_at=row.get("resume_uploaded_at"),
            target_role=row.get("target_role"),
        )
    except Exception as e:
        logger.error(f"Error fetching resume profile for user '{user_id}': {e}")
        return ResumeProfileResponse(
            status="not_found",
            user_id=user_id,
        )
