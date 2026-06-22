import logging
import re
import urllib.parse
from typing import List, Dict
import httpx
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

router = APIRouter()
logger = logging.getLogger(__name__)

# Static Job Seed Data
JOB_ROLES_DATABASE: Dict[str, List[str]] = {
    "Frontend Developer": [
        "JavaScript", "TypeScript", "React", "HTML", "CSS", "Git", "Figma"
    ],
    "Backend Developer": [
        "Python", "FastAPI", "SQL", "PostgreSQL", "Docker", "Git", "Node.js"
    ],
    "Full-Stack Developer": [
        "JavaScript", "TypeScript", "React", "Python", "Node.js", "SQL", "Git", "HTML", "CSS"
    ],
    "DevOps Engineer": [
        "AWS", "Docker", "Kubernetes", "CI/CD", "Git", "Python", "Linux", "Terraform"
    ],
    "Mobile Developer": [
        "Flutter", "Dart", "Git", "JavaScript", "SQL", "Firebase"
    ],
    "Data Scientist": [
        "Python", "Machine Learning", "Pandas", "NumPy", "scikit-learn", "SQL", "Matplotlib", "Tableau"
    ],
    "AI/ML Engineer": [
        "Python", "TensorFlow", "PyTorch", "Machine Learning", "Deep Learning", "NLP", "NumPy", "Pandas"
    ],
    "Cloud Engineer": [
        "AWS", "Azure", "GCP", "Docker", "Kubernetes", "Terraform", "CI/CD", "Linux"
    ],
    "QA Engineer": [
        "Python", "Agile", "Scrum", "SQL", "Git", "Postman", "CI/CD"
    ],
    "UI/UX Designer": [
        "Figma", "HTML", "CSS", "Communication", "Problem Solving", "Agile"
    ],
    "Data Analyst": [
        "Python", "SQL", "Excel", "Power BI", "Tableau", "Pandas", "NumPy"
    ],
    "Cybersecurity Engineer": [
        "Python", "Linux", "Shell Scripting", "AWS", "Git", "SQL", "Agile"
    ],
    "Product Manager": [
        "Agile", "Scrum", "Jira", "Communication", "Leadership", "Project Management", "Figma"
    ],
    "Game Developer": [
        "C++", "Python", "Git", "JavaScript", "C#"
    ],
    "Embedded Systems Engineer": [
        "C++", "Python", "Git", "Linux", "Shell Scripting"
    ],
    "Blockchain Developer": [
        "JavaScript", "TypeScript", "Python", "SQL", "Git", "Node.js"
    ],
    "SEO Specialist": [
        "SEO", "SEM", "Google Analytics", "Keyword Research", "Link Building",
        "Content Marketing", "Google Ads", "A/B Testing", "Copywriting"
    ],
    "Digital Marketing Manager": [
        "Social Media Marketing", "Google Analytics", "Email Marketing", "Content Marketing",
        "Facebook Ads", "Google Ads", "SEO", "Brand Strategy", "HubSpot", "Mailchimp"
    ],
    "HR Manager": [
        "Recruitment", "Talent Acquisition", "Employee Relations", "Performance Management",
        "HR Policies", "Onboarding", "Payroll", "Labor Law", "HRIS", "Training & Development"
    ],
    "Financial Analyst": [
        "Financial Analysis", "Financial Modeling", "Excel", "Financial Reporting",
        "Budgeting", "Forecasting", "GAAP", "Investment Analysis", "Bloomberg Terminal", "SAP"
    ],
    "Accountant": [
        "Accounting", "QuickBooks", "SAP", "Tax Planning", "Auditing", "GAAP",
        "Cost Accounting", "Financial Reporting", "Excel", "Cash Flow Management"
    ],
    "Business Analyst": [
        "Business Analysis", "Process Improvement", "Stakeholder Management", "Agile",
        "Jira", "Scrum", "SQL", "Excel", "Power BI", "Communication", "Tableau"
    ],
    "Sales Manager": [
        "Sales", "B2B Sales", "CRM", "Salesforce", "Lead Generation", "Negotiation",
        "Pipeline Management", "Account Management", "Communication", "Leadership"
    ],
    "Customer Success Manager": [
        "Customer Success", "Client Retention", "CRM", "Communication", "Salesforce",
        "Upselling", "Account Management", "Customer Support", "Problem Solving"
    ],
    "Graphic Designer": [
        "Adobe Photoshop", "Adobe Illustrator", "Adobe InDesign", "Figma", "Canva",
        "Typography", "Color Theory", "Brand Identity", "Logo Design", "Creativity"
    ],
    "Video Editor": [
        "Adobe Premiere Pro", "After Effects", "Video Editing", "Motion Graphics",
        "Color Theory", "Storytelling", "Adobe Photoshop", "Canva"
    ],
    "Content Writer": [
        "Copywriting", "Content Marketing", "SEO", "Research", "Microsoft Word",
        "Email Marketing", "Social Media Marketing", "Communication", "Attention to Detail"
    ],
    "Operations Manager": [
        "Operations Management", "Supply Chain Management", "Process Improvement",
        "Lean", "Six Sigma", "ERP", "Vendor Management", "Procurement", "Leadership", "Excel"
    ],
    "Healthcare Administrator": [
        "Healthcare Administration", "HIPAA", "Electronic Health Records", "EHR",
        "Medical Coding", "ICD-10", "Public Health", "Communication", "Microsoft Office"
    ],
    "Legal Counsel": [
        "Legal Research", "Contract Drafting", "Compliance", "Corporate Law",
        "Due Diligence", "Legal Writing", "Contract Law", "Regulatory Affairs", "Communication"
    ],
    "Training Specialist": [
        "Training Facilitation", "Instructional Design", "Curriculum Development",
        "E-Learning", "LMS", "Coaching", "Presentation Skills", "Communication", "Adult Learning"
    ],
}

# Static dummy fallback remote jobs to return if the live API is down or times out
DUMMY_FALLBACK_JOBS: Dict[str, List[Dict[str, str]]] = {
    "Python": [
        {
            "title": "Senior Backend Engineer (Python)",
            "company_name": "TechGen Solutions",
            "category": "Software Development",
            "candidate_required_location": "Remote (US/Canada)",
            "salary": "$120,000 - $140,000 USD",
            "url": "https://remotive.com/fallback-python-1",
        },
        {
            "title": "Python Data Developer",
            "company_name": "DataOps Systems",
            "category": "Data Science",
            "candidate_required_location": "Worldwide",
            "salary": "$90,000 - $110,000 USD",
            "url": "https://remotive.com/fallback-python-2",
        },
        {
            "title": "Junior Python Developer",
            "company_name": "StartUp Labs",
            "category": "Software Development",
            "candidate_required_location": "Remote (Europe)",
            "salary": "€50,000 - €60,000 EUR",
            "url": "https://remotive.com/fallback-python-3",
        },
    ],
    "Flutter": [
        {
            "title": "Senior Flutter Developer",
            "company_name": "MobileFirst Inc",
            "category": "Software Development / Mobile",
            "candidate_required_location": "Worldwide",
            "salary": "$100,000 - $130,000 USD",
            "url": "https://remotive.com/fallback-flutter-1",
        },
        {
            "title": "Flutter / Dart Engineer",
            "company_name": "Appify Solutions",
            "category": "Software Development",
            "candidate_required_location": "Remote (US/Canada)",
            "salary": "$110,000 - $125,000 USD",
            "url": "https://remotive.com/fallback-flutter-2",
        },
    ],
    "SEO": [
        {
            "title": "Remote SEO Specialist",
            "company_name": "GrowthLab Agency",
            "category": "Marketing",
            "candidate_required_location": "Worldwide",
            "salary": "$50,000 - $70,000 USD",
            "url": "https://remotive.com/fallback-seo-1",
        }
    ],
    "HR": [
        {
            "title": "Remote HR Manager",
            "company_name": "PeopleFirst Corp",
            "category": "Human Resources",
            "candidate_required_location": "Worldwide",
            "salary": "$60,000 - $80,000 USD",
            "url": "https://remotive.com/fallback-hr-1",
        }
    ],
    "Sales": [
        {
            "title": "Remote Sales Manager",
            "company_name": "Nexus Ventures",
            "category": "Sales",
            "candidate_required_location": "Worldwide",
            "salary": "$70,000 - $95,000 USD",
            "url": "https://remotive.com/fallback-sales-1",
        }
    ],
}

# Static Course Catalog Map mapping common skills to specific, high-quality course pages
STATIC_COURSE_CATALOG: Dict[str, Dict[str, str]] = {
    "FastAPI": {
        "title": "FastAPI - The Complete Course (Beginner + Advanced)",
        "provider": "Udemy",
        "url": "https://www.udemy.com/course/fastapi-the-complete-course-beginner-advanced/",
    },
    "Docker": {
        "title": "Docker & Kubernetes: The Practical Guide",
        "provider": "Udemy",
        "url": "https://www.udemy.com/course/docker-kubernetes-the-practical-guide/",
    },
    "PostgreSQL": {
        "title": "SQL and PostgreSQL Complete Bootcamp",
        "provider": "Udemy",
        "url": "https://www.udemy.com/course/the-complete-sql-bootcamp/",
    },
    "Node.js": {
        "title": "The Complete Node.js Developer Course",
        "provider": "Udemy",
        "url": "https://www.udemy.com/course/the-complete-node-js-developer-course-2/",
    },
    "React": {
        "title": "React - The Complete Guide (incl. Next.js, Redux)",
        "provider": "Udemy",
        "url": "https://www.udemy.com/course/react-the-complete-guide-incl-redux/",
    },
    "Flutter": {
        "title": "Flutter & Dart - The Complete Guide",
        "provider": "Udemy",
        "url": "https://www.udemy.com/course/learn-flutter-dart-to-build-ios-android-apps/",
    },
    "SEO": {
        "title": "The Complete SEO Course",
        "provider": "Udemy",
        "url": "https://www.udemy.com/course/seo-2019-complete-seo-training-traffic-with-windows-mac/",
    },
    "Google Analytics": {
        "title": "Google Analytics for Beginners – Google",
        "provider": "Google",
        "url": "https://skillshop.google.com/",
    },
    "Financial Modeling": {
        "title": "Financial Modeling & Valuation Analyst (FMVA)",
        "provider": "CFI",
        "url": "https://corporatefinanceinstitute.com/certifications/financial-modeling-valuation-analyst-fmva-program/",
    },
    "Excel": {
        "title": "Microsoft Excel - Excel from Beginner to Advanced",
        "provider": "Udemy",
        "url": "https://www.udemy.com/course/microsoft-excel-2013-from-beginner-to-advanced-and-beyond/",
    },
    "Adobe Photoshop": {
        "title": "Adobe Photoshop CC – Advanced Training Course",
        "provider": "Udemy",
        "url": "https://www.udemy.com/course/adobe-photoshop-cc-essentials-training-course/",
    },
    "Recruitment": {
        "title": "Recruiting Foundations",
        "provider": "LinkedIn Learning",
        "url": "https://www.linkedin.com/learning/recruiting-foundations",
    },
    "Salesforce": {
        "title": "Salesforce for Beginners",
        "provider": "Udemy",
        "url": "https://www.udemy.com/course/salesforce-lex/",
    },
    "Content Marketing": {
        "title": "Content Marketing Certification",
        "provider": "HubSpot Academy",
        "url": "https://academy.hubspot.com/courses/content-marketing",
    },
    "Accounting": {
        "title": "Accounting Fundamentals",
        "provider": "Coursera",
        "url": "https://www.coursera.org/learn/accounting-fundamentals",
    },
}


class SkillGapAnalysisRequest(BaseModel):
    """
    Request model for the skill gap analysis endpoint.
    """
    target_role: str = Field(..., description="The role name the user is targeting")
    user_skills: List[str] = Field(
        ..., description="List of skills the user currently possesses"
    )


class SkillGapAnalysisResponse(BaseModel):
    """
    Response model matching the expected structure of the Flutter skill gap screen.
    """
    status: str = Field(..., description="The status of the operation (success/error)")
    target_role: str = Field(..., description="The role name that was analyzed")
    readiness_score: int = Field(
        ..., description="Readiness percentage score between 0 and 100"
    )
    matched_skills: List[str] = Field(
        ..., description="List of required skills the user has"
    )
    missing_skills: List[str] = Field(
        ..., description="List of required skills the user is missing"
    )
    total_required: int = Field(
        ..., description="Total number of required skills for the role"
    )


class RemoteJobResponse(BaseModel):
    """
    Response model representing a lightweight, clean remote job structure.
    """
    title: str = Field(..., description="Job title")
    company_name: str = Field(..., description="Company hiring")
    category: str = Field(..., description="Job category")
    candidate_required_location: str = Field(
        ..., description="Allowed locations for candidate"
    )
    salary: str = Field(..., description="Salary details if available, else 'Not Specified'")
    url: str = Field(..., description="Application or listing URL")


class RecommendCoursesRequest(BaseModel):
    """
    Request model for the course recommendations endpoint.
    """
    missing_skills: List[str] = Field(
        ..., description="List of missing skills for course recommendations"
    )


class CourseRecommendation(BaseModel):
    """
    Model representing a recommended course or fallback search link.
    """
    skill: str = Field(..., description="The name of the skill")
    course_title: str = Field(..., description="The recommended course title")
    provider: str = Field(..., description="The provider of the course (e.g., Udemy, Coursera, YouTube)")
    url: str = Field(..., description="The course URL or fallback search URL")


class CourseRecommendationsResponse(BaseModel):
    """
    Response model matching the expected structure of course recommendations.
    """
    status: str = Field(..., description="The status of the recommendation operation (success/error)")
    recommendations: List[CourseRecommendation] = Field(
        ..., description="List of recommended courses or fallbacks"
    )


def _get_dynamic_fallback(role: str) -> List[RemoteJobResponse]:
    """
    Generate clean, realistic dummy remote jobs if live API search fails.
    """
    role_lower = role.lower()
    for key, jobs in DUMMY_FALLBACK_JOBS.items():
        if key.lower() in role_lower or role_lower in key.lower():
            return [RemoteJobResponse(**job) for job in jobs]

    # Generate a dynamic fallback list for arbitrary roles
    return [
        RemoteJobResponse(
            title=f"Remote {role} Developer",
            company_name="Innovate Ltd",
            category="Software Development",
            candidate_required_location="Worldwide",
            salary="Not Specified",
            url=f"https://remotive.com/fallback-{role_lower}-1",
        ),
        RemoteJobResponse(
            title=f"Senior {role} Engineer",
            company_name="CloudVentures Labs",
            category="Software Development",
            candidate_required_location="Remote (US/Canada)",
            salary="$110,000 - $140,000 USD",
            url=f"https://remotive.com/fallback-{role_lower}-2",
        ),
    ]


@router.get("/job-roles", status_code=status.HTTP_200_OK)
async def get_job_roles():
    """
    Retrieve list of all available job titles to populate dropdown menu.
    """
    logger.info("Fetching all available job roles.")
    return {
        "roles": list(JOB_ROLES_DATABASE.keys()),
        "skill_counts": {role: len(skills) for role, skills in JOB_ROLES_DATABASE.items()}
    }


@router.post(
    "/analyze-gap",
    response_model=SkillGapAnalysisResponse,
    status_code=status.HTTP_200_OK,
)
async def analyze_gap(request: SkillGapAnalysisRequest) -> SkillGapAnalysisResponse:
    """
    Compare user skills against target job required skills, and calculate
    the match percentage and missing skills.
    """
    target_role = request.target_role
    user_skills = request.user_skills

    # Validate target role existence
    if target_role not in JOB_ROLES_DATABASE:
        logger.warning(f"Skill gap request rejected. Invalid job role: '{target_role}'")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Target role '{target_role}' not found in the database. "
            f"Available roles: {list(JOB_ROLES_DATABASE.keys())}",
        )

    required_skills = JOB_ROLES_DATABASE[target_role]

    # Convert user skills to lowercase for O(1) case-insensitive lookup
    user_skills_lower = {skill.lower() for skill in user_skills}

    matched_skills = []
    missing_skills = []

    # Filter skills preserving the original database casing
    for skill in required_skills:
        if skill.lower() in user_skills_lower:
            matched_skills.append(skill)
        else:
            missing_skills.append(skill)

    # Calculate readiness score as an integer percentage
    total_required = len(required_skills)
    if total_required > 0:
        readiness_score = int(round((len(matched_skills) / total_required) * 100))
    else:
        readiness_score = 100

    logger.info(
        f"Analyzed gap for '{target_role}': "
        f"readiness={readiness_score}%, "
        f"matched={len(matched_skills)}, "
        f"missing={len(missing_skills)}"
    )

    return SkillGapAnalysisResponse(
        status="success",
        target_role=target_role,
        readiness_score=readiness_score,
        matched_skills=matched_skills,
        missing_skills=missing_skills,
        total_required=total_required,
    )


@router.get("", response_model=List[RemoteJobResponse], status_code=status.HTTP_200_OK)
@router.get("/jobs", response_model=List[RemoteJobResponse], status_code=status.HTTP_200_OK)
async def get_remote_jobs() -> List[RemoteJobResponse]:
    """
    Search and retrieve live remote jobs using the Remotive.io API.
    If the API fails or times out, gracefully falls back to static dummy jobs.
    """
    logger.info("Received request to fetch remote jobs.")
    url = "https://remotive.com/api/remote-jobs"

    try:
        # Request external Remotive API asynchronously with a 10s timeout
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            raw_jobs = data.get("jobs", [])

            parsed_jobs = []
            for job in raw_jobs:
                parsed_jobs.append(
                    RemoteJobResponse(
                        title=job.get("title", "Remote Developer"),
                        company_name=job.get("company_name", "Confidential"),
                        category=job.get("category", "Software Development"),
                        candidate_required_location=job.get(
                            "candidate_required_location", "Worldwide"
                        ),
                        salary=job.get("salary") or "Not Specified",
                        url=job.get("url", "https://remotive.com"),
                    )
                )

            logger.info(
                f"Successfully fetched {len(parsed_jobs)} live remote jobs from Remotive API."
            )
            return parsed_jobs

    except Exception as e:
        logger.warning(
            f"Remotive API request failed due to: {e}. "
            "Gracefully serving dynamic fallback data to client."
        )
        return _get_dynamic_fallback()


@router.post(
    "/recommend-courses",
    response_model=CourseRecommendationsResponse,
    status_code=status.HTTP_200_OK,
)
async def recommend_courses(
    request: RecommendCoursesRequest,
) -> CourseRecommendationsResponse:
    """
    Generate course recommendations for a list of missing skills.
    Matches against a static catalog of high-quality courses. If a skill is
    not present in the catalog, generates a high-quality fallback search link
    on YouTube or Coursera.
    """
    logger.info(f"Recommending courses for missing skills: {request.missing_skills}")
    recommendations = []

    # Map lowercase skill keys to their canonical catalog entries for case-insensitive matching
    catalog_lower = {k.lower(): v for k, v in STATIC_COURSE_CATALOG.items()}

    # Deduplicate incoming missing skills while maintaining order
    seen_skills = set()
    for skill in request.missing_skills:
        skill_clean = skill.strip()
        if not skill_clean:
            continue
        
        skill_lower = skill_clean.lower()
        if skill_lower in seen_skills:
            continue
        seen_skills.add(skill_lower)

        if skill_lower in catalog_lower:
            course = catalog_lower[skill_lower]
            recommendations.append(
                CourseRecommendation(
                    skill=skill_clean,
                    course_title=course["title"],
                    provider=course["provider"],
                    url=course["url"],
                )
            )
        else:
            # Fallback: generate a clean Udemy search URL targeting the skill directly
            encoded_skill = urllib.parse.quote_plus(skill_clean)
            recommendations.append(
                CourseRecommendation(
                    skill=skill_clean,
                    course_title=f"{skill_clean} - Find Courses on Udemy",
                    provider="Udemy",
                    url=f"https://www.udemy.com/courses/search/?q={encoded_skill}",
                )
            )

    return CourseRecommendationsResponse(
        status="success",
        recommendations=recommendations,
    )
