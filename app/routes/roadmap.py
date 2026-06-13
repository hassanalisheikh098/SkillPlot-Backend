import json
import logging
import math
from typing import List, Optional

from fastapi import APIRouter, status
from groq import AsyncGroq
from pydantic import BaseModel, Field

from app.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class RoadmapRequest(BaseModel):
    """
    Request payload for generating an AI career roadmap.
    """
    target_role: str = Field(..., description="The job role the user is targeting")
    missing_skills: List[str] = Field(
        ..., description="Skills the user still needs to acquire"
    )
    user_name: Optional[str] = Field(
        None, description="Optional first name to personalise the roadmap"
    )


class RoadmapStep(BaseModel):
    """
    A single, concrete learning milestone within the roadmap.
    """
    step_number: int = Field(..., description="Ordered position of this step (1-based)")
    title: str = Field(..., description="Short milestone title")
    description: str = Field(..., description="What the learner should do and why")
    resources: List[str] = Field(..., description="Recommended resources, tools, or links")
    estimated_weeks: int = Field(..., description="Rough time budget in weeks")


class RoadmapResponse(BaseModel):
    """
    Full roadmap response returned to the Flutter client.
    """
    status: str = Field(..., description="Operation status (success/error)")
    target_role: str = Field(..., description="The target role used to generate this roadmap")
    steps: List[RoadmapStep] = Field(..., description="Ordered list of learning milestones")


# ---------------------------------------------------------------------------
# Static fallback generator
# ---------------------------------------------------------------------------

def _build_static_fallback(target_role: str, missing_skills: List[str]) -> List[RoadmapStep]:
    """
    Produce a sensible 5-step roadmap without calling any external API.

    Strategy
    --------
    Step 1  : Foundation Setup — always first
    Steps 2-4 : Skill-group steps, distributing missing_skills evenly across them
    Step 5  : Build Portfolio Project — always last
    """
    steps: List[RoadmapStep] = []

    # -- Step 1: Foundation Setup --------------------------------------------
    steps.append(
        RoadmapStep(
            step_number=1,
            title="Foundation Setup",
            description=(
                f"Prepare your development environment for the {target_role} journey. "
                "Install the required runtimes, editors (VS Code recommended), version control "
                "(Git + GitHub), and any language-specific tooling listed in your skill gap. "
                "A clean, reproducible local setup prevents friction in every step that follows."
            ),
            resources=[
                "https://code.visualstudio.com/",
                "https://git-scm.com/downloads",
                "https://github.com/",
            ],
            estimated_weeks=1,
        )
    )

    # -- Steps 2-4: Skill groups --------------------------------------------
    # Split missing_skills into up to 3 roughly equal groups
    skills = missing_skills if missing_skills else [target_role]
    num_groups = min(3, max(1, len(skills)))
    group_size = math.ceil(len(skills) / num_groups)
    skill_groups = [skills[i: i + group_size] for i in range(0, len(skills), group_size)]

    skill_step_titles = ["Core Skills Acquisition", "Advanced Skill Building", "Integration & Practice"]
    skill_step_descs = [
        "Master the foundational concepts of your primary skill gaps through structured courses and daily coding exercises. Focus on understanding, not just copying — build small test projects for each technology.",
        "Deepen your understanding of the more advanced skills in your gap list. Study real-world codebases on GitHub, contribute to open-source, and replicate features you admire.",
        "Combine your newly acquired skills in a single integrated mini-project. This demonstrates you can apply technologies together — exactly what employers evaluate during technical interviews.",
    ]

    for idx, group in enumerate(skill_groups[:3]):
        step_num = idx + 2
        skills_str = ", ".join(group)
        udemy_search = f"https://www.udemy.com/courses/search/?q={'+'.join(group[0].split())}"
        steps.append(
            RoadmapStep(
                step_number=step_num,
                title=f"{skill_step_titles[idx]}: {skills_str}",
                description=skill_step_descs[idx],
                resources=[
                    udemy_search,
                    "https://developer.mozilla.org/",
                    "https://roadmap.sh/",
                ],
                estimated_weeks=2 + idx,
            )
        )

    # -- Final step: Portfolio Project ---------------------------------------
    steps.append(
        RoadmapStep(
            step_number=len(steps) + 1,
            title="Build a Portfolio Project",
            description=(
                f"Consolidate everything by building a complete, deployable {target_role} portfolio project. "
                "Choose a real-world problem, apply each skill from your roadmap, deploy to a free tier "
                "(Render, Railway, or Vercel), and write a professional README. "
                "This single artefact will anchor every technical interview conversation."
            ),
            resources=[
                "https://render.com/",
                "https://railway.app/",
                "https://github.com/",
                "https://www.makeareadme.com/",
            ],
            estimated_weeks=3,
        )
    )

    return steps


# ---------------------------------------------------------------------------
# Groq AI roadmap generator
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are a career roadmap generator. Return ONLY valid JSON, no markdown, no backticks. "
    "The JSON must have this exact structure: "
    '{ "steps": [ { "step_number": 1, "title": "...", "description": "...", '
    '"resources": ["..."], "estimated_weeks": 2 } ] } '
    "Generate 4-6 steps. Each step should be a concrete learning milestone."
)


async def _call_groq(target_role: str, missing_skills: List[str], user_name: Optional[str]) -> List[RoadmapStep]:
    """
    Call the Groq Llama-3.1 model and parse its JSON response into RoadmapStep objects.
    Raises an exception on any failure so the caller can fall back gracefully.
    """
    api_key = settings.GROQ_API_KEY.strip()
    if not api_key or api_key == "your-groq-api-key" or "gsk_" not in api_key:
        raise ValueError("Groq API key is missing or uses placeholder credentials.")

    skills_str = ", ".join(missing_skills) if missing_skills else "general software development skills"
    greeting = f"for {user_name}" if user_name else "for someone"

    user_message = (
        f"Create a career roadmap {greeting} targeting {target_role}. "
        f"Their skill gaps are: {skills_str}. Make it practical and achievable."
    )

    client = AsyncGroq(api_key=api_key)
    completion = await client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        max_tokens=1024,
        temperature=0.65,
    )

    raw_content = completion.choices[0].message.content.strip()
    logger.debug(f"Raw Groq roadmap response: {raw_content}")

    # Strip any accidental markdown fences the model may still emit
    if raw_content.startswith("```"):
        raw_content = raw_content.split("```")[1]
        if raw_content.startswith("json"):
            raw_content = raw_content[4:]
        raw_content = raw_content.strip()

    parsed = json.loads(raw_content)
    raw_steps: List[dict] = parsed.get("steps", [])

    if not raw_steps:
        raise ValueError("Groq returned an empty steps list.")

    roadmap_steps = []
    for raw in raw_steps:
        roadmap_steps.append(
            RoadmapStep(
                step_number=int(raw.get("step_number", len(roadmap_steps) + 1)),
                title=str(raw.get("title", "Learning Milestone")),
                description=str(raw.get("description", "")),
                resources=[str(r) for r in raw.get("resources", [])],
                estimated_weeks=int(raw.get("estimated_weeks", 2)),
            )
        )

    return roadmap_steps


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post("/generate", response_model=RoadmapResponse, status_code=status.HTTP_200_OK)
async def generate_roadmap(request: RoadmapRequest) -> RoadmapResponse:
    """
    FR-04: AI Career Roadmap Generation.

    Calls the Groq Llama-3.1-8b-instant model to produce a structured,
    JSON-formatted career roadmap personalised to the user's target role and
    missing skills. Falls back to a static but sensible roadmap if the AI call
    fails for any reason (missing key, network error, malformed JSON, etc.).
    """
    logger.info(
        f"Roadmap generation requested — role='{request.target_role}', "
        f"missing_skills={request.missing_skills}"
    )

    steps: List[RoadmapStep]

    try:
        steps = await _call_groq(
            target_role=request.target_role,
            missing_skills=request.missing_skills,
            user_name=request.user_name,
        )
        logger.info(
            f"Successfully generated AI roadmap with {len(steps)} steps "
            f"for role '{request.target_role}'."
        )

    except Exception as exc:
        logger.warning(
            f"Groq roadmap generation failed ({exc}). "
            "Falling back to static roadmap generator."
        )
        steps = _build_static_fallback(
            target_role=request.target_role,
            missing_skills=request.missing_skills,
        )

    return RoadmapResponse(
        status="success",
        target_role=request.target_role,
        steps=steps,
    )
