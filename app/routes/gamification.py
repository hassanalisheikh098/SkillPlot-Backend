import logging
from typing import List, Optional
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.services.supabase_client import supabase

# =============================================================================
# DB Table Creation SQL for xp_history (run in Supabase SQL editor):
#
# CREATE TABLE IF NOT EXISTS public.xp_history (
#   id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
#   user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
#   action TEXT NOT NULL,
#   xp_awarded INTEGER NOT NULL,
#   total_xp_after INTEGER NOT NULL,
#   created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
# );
# CREATE INDEX IF NOT EXISTS idx_xp_history_user ON public.xp_history (user_id, created_at DESC);
# =============================================================================

router = APIRouter()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

XP_REWARDS: dict[str, int] = {
    "resume_uploaded": 50,
    "skill_gap_analyzed": 30,
    "course_completed": 100,
    "roadmap_generated": 40,
    "chat_message_sent": 5,
    "profile_completed": 75,
}

# Ordered from lowest to highest threshold
BADGE_THRESHOLDS: dict[str, int] = {
    "Beginner": 0,
    "Explorer": 100,
    "Learner": 300,
    "Achiever": 600,
    "Pro": 1000,
    "Expert": 2000,
}

_TABLE = "user_progress"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _earned_badges(total_xp: int) -> List[str]:
    """Return every badge whose XP threshold has been reached."""
    return [badge for badge, threshold in BADGE_THRESHOLDS.items() if total_xp >= threshold]


def _mock_progress_response(user_id: str) -> "UserProgressResponse":
    """Return a safe offline mock when Supabase is unavailable."""
    return UserProgressResponse(
        status="success",
        user_id=user_id,
        total_xp=0,
        badges=["Beginner"],
        completed_courses=0,
        level=0,
        next_level_xp=100,
        current_badge="Beginner",
        xp_to_next_badge=100,
    )


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class AwardXpRequest(BaseModel):
    """Request body for awarding XP to a user after a tracked action."""
    user_id: str = Field(..., description="The Supabase Auth UUID of the user")
    action: str = Field(
        ..., description=f"Action key. Supported: {list(XP_REWARDS.keys())}"
    )


class AwardXpResponse(BaseModel):
    """Response returned after an XP award operation."""
    status: str = Field(..., description="Operation status (success/error)")
    user_id: str = Field(..., description="The user whose XP was updated")
    action: str = Field(..., description="The action that was awarded")
    action_xp: int = Field(..., description="XP awarded for this specific action")
    total_xp: int = Field(..., description="Updated cumulative XP total")
    new_badges: List[str] = Field(
        ..., description="Badges newly unlocked in this operation"
    )
    all_badges: List[str] = Field(
        ..., description="Complete list of badges the user now holds"
    )


class UserProgressResponse(BaseModel):
    """Full gamification progress snapshot for a user."""
    status: str = Field(..., description="Operation status (success/error)")
    user_id: str = Field(..., description="The user whose progress is shown")
    total_xp: int = Field(..., description="Cumulative XP earned")
    badges: List[str] = Field(..., description="All badges currently unlocked")
    completed_courses: int = Field(..., description="Total courses marked complete")
    level: int = Field(..., description="User level based on total XP")
    next_level_xp: int = Field(..., description="XP needed to reach the next level")
    current_badge: str = Field(..., description="Highest unlocked badge")
    xp_to_next_badge: int = Field(..., description="XP needed to unlock the next badge threshold")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/award-xp", response_model=AwardXpResponse, status_code=status.HTTP_200_OK)
async def award_xp(request: AwardXpRequest) -> AwardXpResponse:
    """
    FR-07: Award XP for a completed user action.

    Reads the current progress row from Supabase, increments XP, evaluates
    badge thresholds, writes the update back, and returns the diff.
    Falls back to a mock zero-state if Supabase is unavailable.
    """
    action = request.action.strip()
    user_id = request.user_id.strip()

    # Validate action key
    if action not in XP_REWARDS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Unknown action '{action}'. "
                f"Supported actions: {list(XP_REWARDS.keys())}"
            ),
        )

    action_xp = XP_REWARDS[action]

    # ── Supabase unavailable: graceful offline fallback ──────────────────────
    if not supabase:
        logger.warning(
            "Supabase not connected. Returning mock XP award response "
            f"for user '{user_id}', action '{action}'."
        )
        mock_total = action_xp  # pretend the user starts at 0
        return AwardXpResponse(
            status="success",
            user_id=user_id,
            action=action,
            action_xp=action_xp,
            total_xp=mock_total,
            new_badges=_earned_badges(mock_total),
            all_badges=_earned_badges(mock_total),
        )

    # ── Fetch existing progress row ──────────────────────────────────────────
    try:
        result = (
            supabase.table(_TABLE)
            .select("total_xp, badges, completed_courses")
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
    except Exception as exc:
        logger.error(f"Supabase read failed for user '{user_id}': {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not read progress from database.",
        )

    # CRASH FIX: Ensure result is evaluated defensively
    row = result.data if (result is not None and hasattr(result, "data")) else None

    if row:
        current_xp: int = row.get("total_xp", 0)
        current_badges: List[str] = row.get("badges") or []
        completed_courses: int = row.get("completed_courses", 0)
    else:
        # First-time user — row does not exist yet; we will upsert below
        current_xp = 0
        current_badges = []
        completed_courses = 0

    # ── Increment course counter if relevant ─────────────────────────────────
    if action == "course_completed":
        completed_courses += 1

    # ── Calculate new totals and newly unlocked badges ───────────────────────
    new_total_xp = current_xp + action_xp
    all_badges = _earned_badges(new_total_xp)
    new_badges = [b for b in all_badges if b not in current_badges]

    # ── Upsert progress row ──────────────────────────────────────────────────
    upsert_payload = {
        "user_id": user_id,
        "total_xp": new_total_xp,
        "badges": all_badges,
        "completed_courses": completed_courses,
        "last_activity": datetime.now(timezone.utc).isoformat(),
    }

    try:
        # CRASH FIX: Explicitly assign payload returns away from global scope context
        upsert_result = supabase.table(_TABLE).upsert(
            upsert_payload, on_conflict="user_id"
        ).execute()
    except Exception as exc:
        logger.error(f"Supabase upsert failed for user '{user_id}': {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not save progress update to database.",
        )

    # Best effort insert into xp_history
    try:
        xp_history_payload = {
            "user_id": user_id,
            "action": action,
            "xp_awarded": action_xp,
            "total_xp_after": new_total_xp,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        # CRASH FIX: Isolate result tracking variable execution
        history_result = supabase.table("xp_history").insert(xp_history_payload).execute()
        logger.info(f"Successfully recorded XP history entry for user '{user_id}' and action '{action}'")
    except Exception as e:
        logger.warning(f"Could not record XP history entry: {e}")

    logger.info(
        f"Awarded {action_xp} XP to user '{user_id}' for '{action}'. "
        f"New total: {new_total_xp}. New badges: {new_badges}."
    )

    return AwardXpResponse(
        status="success",
        user_id=user_id,
        action=action,
        action_xp=action_xp,
        total_xp=new_total_xp,
        new_badges=new_badges,
        all_badges=all_badges,
    )

@router.get(
    "/progress/{user_id}",
    response_model=UserProgressResponse,
    status_code=status.HTTP_200_OK,
)
async def get_progress(user_id: str) -> UserProgressResponse:
    """
    FR-07: Retrieve full gamification progress for a user.

    Returns total XP, unlocked badges, and completed course count.
    Falls back to a safe mock if Supabase is unavailable.
    """
    logger.info(f"Fetching gamification progress for user '{user_id}'.")

    # ── Supabase unavailable: graceful offline fallback ──────────────────────
    if not supabase:
        logger.warning(
            f"Supabase not connected. Returning mock progress for user '{user_id}'."
        )
        return _mock_progress_response(user_id)

    try:
        result = (
            supabase.table(_TABLE)
            .select("total_xp, badges, completed_courses")
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
    except Exception as exc:
        logger.error(
            f"Supabase read failed for progress query on user '{user_id}': {exc}"
        )
        # Degrade gracefully rather than returning 503 — progress reads are non-critical
        return _mock_progress_response(user_id)

    row = result.data

    if not row:
        # User exists in Auth but has no progress row yet — return zero state
        return UserProgressResponse(
            status="success",
            user_id=user_id,
            total_xp=0,
            badges=["Beginner"],
            completed_courses=0,
            level=0,
            next_level_xp=100,
            current_badge="Beginner",
            xp_to_next_badge=100,
        )

    total_xp: int = row.get("total_xp", 0)
    badges: List[str] = row.get("badges") or _earned_badges(total_xp)
    completed_courses: int = row.get("completed_courses", 0)

    level = total_xp // 100
    next_level_xp = ((total_xp // 100) + 1) * 100
    current_badge = badges[-1] if badges else "Beginner"

    next_badge_xp = 0
    found_next = False
    for badge, threshold in BADGE_THRESHOLDS.items():
        if total_xp < threshold:
            next_badge_xp = threshold
            found_next = True
            break
    xp_to_next_badge = max(0, next_badge_xp - total_xp) if found_next else 0

    return UserProgressResponse(
        status="success",
        user_id=user_id,
        total_xp=total_xp,
        badges=badges,
        completed_courses=completed_courses,
        level=level,
        next_level_xp=next_level_xp,
        current_badge=current_badge,
        xp_to_next_badge=xp_to_next_badge,
    )


class XpHistoryItem(BaseModel):
    action: str = Field(..., description="The action that awarded XP")
    xp_awarded: int = Field(..., description="XP points awarded")
    total_xp_after: int = Field(..., description="Total XP after the award")
    created_at: str = Field(..., description="ISO timestamp of the action")


class XpHistoryResponse(BaseModel):
    status: str = Field(..., description="Operation status")
    user_id: str = Field(..., description="The user UUID")
    history: List[XpHistoryItem] = Field(default=[], description="XP history entries")


@router.get(
    "/xp-history/{user_id}",
    response_model=XpHistoryResponse,
    status_code=status.HTTP_200_OK,
)
async def get_xp_history(user_id: str) -> XpHistoryResponse:
    """
    Retrieve the last 10 XP history logs for a user.
    """
    logger.info(f"Received request to fetch XP history for user '{user_id}'.")
    try:
        user_id = user_id.strip()
        if not user_id:
            logger.error("Empty user_id provided.")
            return XpHistoryResponse(status="success", user_id="", history=[])

        if not supabase:
            logger.warning("Supabase client is not connected.")
            return XpHistoryResponse(status="success", user_id=user_id, history=[])

        result = (
            supabase.table("xp_history")
            .select("action, xp_awarded, total_xp_after, created_at")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(10)
            .execute()
        )

        history_items = []
        for row in result.data or []:
            history_items.append(
                XpHistoryItem(
                    action=row.get("action"),
                    xp_awarded=row.get("xp_awarded"),
                    total_xp_after=row.get("total_xp_after"),
                    created_at=row.get("created_at")
                )
            )

        logger.info(f"Retrieved {len(history_items)} XP history items for user '{user_id}'.")
        return XpHistoryResponse(
            status="success",
            user_id=user_id,
            history=history_items
        )
    except Exception as e:
        logger.error(f"Error retrieving XP history for user '{user_id}': {e}")
        return XpHistoryResponse(status="success", user_id=user_id, history=[])
