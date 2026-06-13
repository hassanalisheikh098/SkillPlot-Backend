from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


# ---------------------------------------------------------------------------
# Auth models
# ---------------------------------------------------------------------------

class UserSignUpRequest(BaseModel):
    """Schema for user registration requests."""
    email: str = Field(..., description="User's email address")
    password: str = Field(..., min_length=6, description="User's password (min 6 characters)")


class UserLoginRequest(BaseModel):
    """Schema for user authentication/login requests."""
    email: str = Field(..., description="User's email address")
    password: str = Field(..., description="User's password")


class AuthResponse(BaseModel):
    """Schema for standard authentication responses."""
    status: str = Field(..., description="Status of the operation (success/error)")
    message: str = Field(..., description="Descriptive message")
    session: Optional[Dict[str, Any]] = Field(None, description="Supabase session object if authenticated")


# ---------------------------------------------------------------------------
# Roadmap models
# ---------------------------------------------------------------------------

class RoadmapRequest(BaseModel):
    """Request payload for AI career roadmap generation."""
    target_role: str = Field(..., description="The job role the user is targeting")
    missing_skills: List[str] = Field(..., description="Skills the user still needs to acquire")
    user_name: Optional[str] = Field(None, description="Optional first name to personalise the roadmap")


class RoadmapStep(BaseModel):
    """A single, concrete learning milestone within the roadmap."""
    step_number: int = Field(..., description="Ordered position of this step (1-based)")
    title: str = Field(..., description="Short milestone title")
    description: str = Field(..., description="What the learner should do and why")
    resources: List[str] = Field(..., description="Recommended resources, tools, or links")
    estimated_weeks: int = Field(..., description="Rough time budget in weeks")


class RoadmapResponse(BaseModel):
    """Full roadmap response returned to the Flutter client."""
    status: str = Field(..., description="Operation status (success/error)")
    target_role: str = Field(..., description="The target role used to generate this roadmap")
    steps: List[RoadmapStep] = Field(..., description="Ordered list of learning milestones")


# ---------------------------------------------------------------------------
# Gamification / XP models
# ---------------------------------------------------------------------------

class XPUpdateRequest(BaseModel):
    """Request payload for awarding XP to a user after a tracked action."""
    user_id: str = Field(..., description="The Supabase Auth UUID of the user")
    action: str = Field(..., description="The action key that triggered the XP award")
    points: int = Field(..., description="Number of XP points to award")


class UserProgressResponse(BaseModel):
    """Full gamification progress snapshot for a user."""
    status: str = Field(..., description="Operation status (success/error)")
    user_id: str = Field(..., description="The user whose progress is shown")
    total_xp: int = Field(..., description="Cumulative XP earned")
    badges: List[str] = Field(..., description="All badges currently unlocked")
    completed_courses: int = Field(..., description="Total courses marked complete")
