import logging
import re
from typing import List
import fitz  # PyMuPDF
import numpy as np

logger = logging.getLogger(__name__)

# Monkey-patch numpy.load to allow pickle loading before spaCy is imported or loaded.
# This prevents the 'This file contains pickled (object) data' error under newer environments.
try:
    _orig_load = np.load

    def _patched_load(*args, **kwargs):
        kwargs["allow_pickle"] = True
        return _orig_load(*args, **kwargs)

    np.load = _patched_load
    logger.info("Successfully monkey-patched numpy.load for spaCy compatibility.")
except Exception as e:
    logger.warning(f"Could not monkey-patch numpy.load: {e}")

# Import spaCy dynamically and set flag
try:
    import spacy

    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False
    logger.warning(
        "spaCy is not installed. Fallback regex matcher will be used for skill extraction."
    )

# Baseline dictionary of technical and soft skills
SKILLS_DICTIONARY = [
    # Core languages
    "Python",
    "JavaScript",
    "TypeScript",
    "Java",
    "C++",
    "C#",
    "Go",
    "Rust",
    "Swift",
    "Kotlin",
    "Dart",
    # Web & frontend
    "React",
    "HTML",
    "CSS",
    "Node.js",
    "Express",
    # Mobile
    "Flutter",
    "React Native",
    "Android",
    "iOS",
    "Xcode",
    # Backend & APIs
    "FastAPI",
    "Django",
    "Flask",
    "Spring Boot",
    "GraphQL",
    "REST API",
    "gRPC",
    "Microservices",
    # Databases
    "SQL",
    "PostgreSQL",
    "MongoDB",
    "Redis",
    # Cloud & DevOps
    "AWS",
    "Azure",
    "GCP",
    "Docker",
    "Kubernetes",
    "Terraform",
    "Firebase",
    "CI/CD",
    # Data & analytics
    "Pandas",
    "NumPy",
    "Matplotlib",
    "Power BI",
    "Tableau",
    "Excel",
    # AI / ML
    "Machine Learning",
    "Deep Learning",
    "TensorFlow",
    "PyTorch",
    "scikit-learn",
    "NLP",
    "OpenAI",
    "Hugging Face",
    "LangChain",
    # Version control & workflow
    "Git",
    "Linux",
    "Shell Scripting",
    "Agile",
    "Scrum",
    "Jira",
    "Postman",
    "Figma",
    # Project & soft skills
    "Project Management",
    "Communication",
    "Leadership",
    "Problem Solving",
    "Teamwork",
    "Critical Thinking",
    "Time Management",
    # Marketing & SEO
    "SEO",
    "SEM",
    "Google Analytics",
    "Google Ads",
    "Facebook Ads",
    "Content Marketing",
    "Email Marketing",
    "Copywriting",
    "Brand Strategy",
    "Market Research",
    "Social Media Marketing",
    "Influencer Marketing",
    "HubSpot",
    "Mailchimp",
    "A/B Testing",
    "Conversion Rate Optimization",
    "Keyword Research",
    "Link Building",
    # HR & People
    "Recruitment",
    "Talent Acquisition",
    "Onboarding",
    "Employee Relations",
    "Performance Management",
    "HR Policies",
    "Payroll",
    "HRIS",
    "Compensation & Benefits",
    "Training & Development",
    "Labor Law",
    "Conflict Resolution",
    "Organizational Development",
    "Workforce Planning",
    "Succession Planning",
    # Finance & Accounting
    "Financial Analysis",
    "Accounting",
    "Budgeting",
    "Forecasting",
    "Financial Reporting",
    "GAAP",
    "IFRS",
    "QuickBooks",
    "SAP",
    "Auditing",
    "Tax Planning",
    "Cost Accounting",
    "Variance Analysis",
    "Cash Flow Management",
    "Investment Analysis",
    "Risk Management",
    "Bloomberg Terminal",
    "Financial Modeling",
    # Business & Operations
    "Business Analysis",
    "Process Improvement",
    "Operations Management",
    "Supply Chain Management",
    "Logistics",
    "Procurement",
    "Vendor Management",
    "Lean",
    "Six Sigma",
    "ERP",
    "CRM",
    "Salesforce",
    "Business Development",
    "Stakeholder Management",
    "Change Management",
    "Strategic Planning",
    # Design (non-tech)
    "Adobe Photoshop",
    "Adobe Illustrator",
    "Adobe InDesign",
    "Adobe Premiere Pro",
    "After Effects",
    "Canva",
    "Video Editing",
    "Motion Graphics",
    "Photography",
    "Typography",
    "Color Theory",
    "Print Design",
    "Logo Design",
    "Brand Identity",
    "3D Modeling",
    "Blender",
    "AutoCAD",
    "Creativity",
    # Healthcare & Medical
    "Patient Care",
    "Clinical Research",
    "Medical Terminology",
    "Electronic Health Records",
    "EHR",
    "HIPAA",
    "Pharmacology",
    "Nursing",
    "First Aid",
    "Anatomy",
    "Physiology",
    "Medical Coding",
    "ICD-10",
    "Healthcare Administration",
    "Public Health",
    "Epidemiology",
    # Education & Training
    "Curriculum Development",
    "Instructional Design",
    "E-Learning",
    "LMS",
    "Classroom Management",
    "Lesson Planning",
    "Student Assessment",
    "Special Education",
    "Adult Learning",
    "Training Facilitation",
    "Coaching",
    "Mentoring",
    # Legal
    "Legal Research",
    "Contract Drafting",
    "Compliance",
    "Litigation",
    "Corporate Law",
    "Intellectual Property",
    "Contract Law",
    "Due Diligence",
    "Legal Writing",
    "Arbitration",
    "Regulatory Affairs",
    # Sales & Customer Success
    "Sales",
    "B2B Sales",
    "B2C Sales",
    "Cold Calling",
    "Lead Generation",
    "Pipeline Management",
    "Account Management",
    "Negotiation",
    "Customer Success",
    "Client Retention",
    "Upselling",
    "Zoho",
    "Customer Support",
    "Technical Support",
    # Soft skills (expand existing)
    "Public Speaking",
    "Presentation Skills",
    "Report Writing",
    "Data Entry",
    "Microsoft Office",
    "Microsoft Word",
    "Microsoft Excel",
    "Microsoft PowerPoint",
    "Research",
    "Analytical Thinking",
    "Adaptability",
    "Multitasking",
    "Attention to Detail",
    "Decision Making",
    "Storytelling",
    # --- Optometry & Clinical Eye Care ---
    "Optometry",
    "Refraction",
    "Slit-Lamp Examination",
    "Fundoscopy",
    "Contact Lens Fitting",
    "Visual Field Analysis",
    "Patient Counseling",
    "Ocular Examinations",
    "Glaucoma Assessment",
    "Cataract Assessment",
    "Binocular Vision Testing",
    "Orthoptic Evaluation",
    "Auto Refractor",
    "A-Scan",
    "Clinical Decision Making",
    # --- Retail & Store Management ---
    "Store Management",
    "Inventory Management",
    "POS Systems",
    "Visual Merchandising",
    "Revenue Generation",
    "Loss Prevention",
    "Staff Scheduling",
    "Retail Operations",
    # --- Administration & Office ---
    "Documentation",
    "Record Keeping",
    "Office Management",
    "Google Suites",
    "Google Suite",
    "Filing",
    "Office Coordination",
    # --- Sales & Client Relations (expanded) ---
    "Client Relations",
    "Client Handling",
    "Customer Dealing",
    "Corporate Sales",
    "Sales Coordination",
    "Admission Counseling",
    "Business Communication",
    "Public Relations",
    "Brand Management",
    "ROI Optimization",
    "Campaign Management",
    "KPI Analysis",
    # --- Healthcare & Life Sciences (expanded) ---
    "Healthcare Business Development",
    "Medical Documentation",
    "Biological Sciences",
    "Health Education",
    "Patient Education",
    # --- Graphic & Creative (expanded) ---
    "Adobe Creative Suite",
    "Graphic Design",
    "Banner Design",
    "Promotional Design",
    "Creative Design",
    "Illustration",
    "Video Blogging",
    "Social Media Content",
    # --- General Professional Skills ---
    "Organizational Skills",
    "Interpersonal Skills",
    "Quick Learner",
    "Results Oriented",
    "Department Coordination",
    "Stakeholder Communication",
    "Professional Outreach",
]

# Global cache for the spaCy NLP model
_nlp = None


def get_nlp():
    """
    Helper function to lazily load and cache the spaCy model.
    """
    global _nlp, SPACY_AVAILABLE
    if not SPACY_AVAILABLE:
        return None
    if _nlp is None:
        try:
            _nlp = spacy.load("en_core_web_sm")
            logger.info(
                f"spaCy model loaded successfully with "
                f"{len(list(_nlp.vocab))} vocab entries."
            )
        except Exception as e:
            logger.error(
                f"Error loading spaCy model 'en_core_web_sm': {e}. "
                "Will fall back to regex matching."
            )
    return _nlp


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """
    Opens a PDF file stream using PyMuPDF (fitz), loops through all pages,
    and concatenates their text content.

    Args:
        file_bytes (bytes): Raw bytes of the uploaded PDF file.

    Returns:
        str: Concatenated text content extracted from the PDF.
    """
    extracted_text = ""
    try:
        with fitz.open(stream=file_bytes, filetype="pdf") as doc:
            text_list = []
            for page in doc:
                text_list.append(page.get_text())
            extracted_text = "\n".join(text_list)
        logger.info(f"Successfully extracted {len(extracted_text)} characters from PDF.")
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {e}")
        raise ValueError(f"Unable to parse the PDF document: {str(e)}")

    return extracted_text


def extract_skills(text: str) -> List[str]:
    """
    Extracts matched skills from the text against a baseline dictionary.
    Performs case-insensitive matching. Tries using spaCy tokenization,
    but gracefully falls back to custom regex matching if spaCy fails.

    Args:
        text (str): The plain text extracted from a resume.

    Returns:
        List[str]: A unique, sorted list of matched skills.
    """
    if not text:
        return []

    nlp = get_nlp()
    if nlp is None:
        logger.warning("spaCy model is not available. Using regex fallback matcher.")
        return _extract_skills_fallback(text)

    try:
        # Process text using spaCy pipeline to tokenize
        doc = nlp(text)
        # Tokenize and lowercase all tokens
        tokens = [token.text.lower() for token in doc]

        matched_skills = []

        for skill in SKILLS_DICTIONARY:
            # Tokenize the skill using the same tokenizer to keep matching consistent
            skill_doc = nlp(skill)
            skill_tokens = [token.text.lower() for token in skill_doc]

            if not skill_tokens:
                continue

            # Check if the sequence of skill tokens exists as a contiguous block in the text tokens
            n = len(skill_tokens)
            matched = False
            for i in range(len(tokens) - n + 1):
                if tokens[i : i + n] == skill_tokens:
                    matched = True
                    break

            if matched:
                matched_skills.append(skill)

        # Return unique, sorted list of matched skills
        return sorted(list(set(matched_skills)))

    except Exception as e:
        logger.error(f"Error during spaCy skill matching: {e}. Falling back to regex.")
        return _extract_skills_fallback(text)


def _extract_skills_fallback(text: str) -> List[str]:
    """
    Fallback method using regex and basic tokenization when spaCy is unavailable or fails.
    """
    # Lowercase text for matching
    text_lower = text.lower()

    # Simple regex tokenization: split by whitespace and strip non-alphanumeric except special symbols
    raw_words = text_lower.split()
    tokens = []
    for word in raw_words:
        # Strip outer punctuation but preserve inner special characters (e.g. ++, #, .js)
        cleaned = re.sub(r"^[^\w+#]+|[^\w+#+.]+$", "", word)
        if cleaned.endswith("."):
            cleaned = cleaned[:-1]
        if cleaned:
            tokens.append(cleaned)

    matched_skills = []

    for skill in SKILLS_DICTIONARY:
        skill_lower = skill.lower()

        # Check if the skill has spaces (multi-word)
        if " " in skill_lower:
            # Match multi-word skill with word boundaries
            pattern = rf"\b{re.escape(skill_lower)}\b"
            if re.search(pattern, text_lower):
                matched_skills.append(skill)
        else:
            # Match single-word skill exactly against token list
            if skill_lower in tokens:
                matched_skills.append(skill)
            else:
                # Regex boundary fallback for special symbols (e.g. C++)
                if not skill_lower[-1].isalnum():
                    pattern = rf"\b{re.escape(skill_lower)}(?!\w)"
                else:
                    pattern = rf"\b{re.escape(skill_lower)}\b"

                if re.search(pattern, text_lower):
                    matched_skills.append(skill)

    return sorted(list(set(matched_skills)))


def extract_experience(text: str) -> str:
    """
    Extracts professional experience section summary and tries to detect years of experience.
    """
    if not text:
        return ""

    logger.info("Extracting professional experience from resume text.")

    # Try to detect years of experience
    years_prefix = ""
    years_match = re.search(r"(?i)(\d+)\+?\s*years?\s+(?:of\s+)?experience", text)
    if years_match:
        years = years_match.group(1)
        years_prefix = f"{years} years experience. "

    # Look for experience section
    pattern = r"(?i)(?:^|\n)\s*(?:work\s+experience|experience|employment|professional\s+experience)\s*:?\s*(?:\n|\r)"
    match = re.search(pattern, text)
    if not match:
        match = re.search(r"(?i)\b(?:work\s+experience|experience|employment|professional\s+experience)\b", text)

    if not match:
        logger.info("No experience section header found in resume.")
        if years_prefix:
            return years_prefix.strip()
        return ""

    section_start = match.end()
    section_text = text[section_start:]

    # Extract the first 600 characters of that section
    section_extract = section_text[:600]

    # Clean whitespace: replace any whitespace/newline with a single space
    cleaned_text = re.sub(r"\s+", " ", section_extract).strip()

    result = f"{years_prefix}{cleaned_text}".strip()
    return result


def extract_education(text: str) -> str:
    """
    Extracts education section summary starting from the first detected degree keyword.
    """
    if not text:
        return ""

    logger.info("Extracting education background from resume text.")

    # Look for education section
    pattern = r"(?i)(?:^|\n)\s*(?:education|academic\s+background|qualifications)\s*:?\s*(?:\n|\r)"
    match = re.search(pattern, text)
    if not match:
        match = re.search(r"(?i)\b(?:education|academic\s+background|qualifications)\b", text)

    if not match:
        logger.info("No education section header found in resume.")
        return ""

    section_start = match.end()
    section_text = text[section_start:]

    # Detect degree keywords
    degrees = ["BS", "BE", "MS", "B.Sc", "M.Sc", "Bachelor", "Master", "PhD", "MBA", "BCS", "MCS"]
    degree_pattern = r"\b(?:" + "|".join(re.escape(d) for d in degrees) + r")\b"
    degree_match = re.search(degree_pattern, section_text, re.IGNORECASE)

    if degree_match:
        # Start extracting from where the degree keyword is located
        start_idx = degree_match.start()
        education_extract = section_text[start_idx:start_idx+400]
    else:
        # Fallback to the start of the section
        education_extract = section_text[:400]

    cleaned_text = re.sub(r"\s+", " ", education_extract).strip()
    return cleaned_text


def extract_full_name(text: str) -> str:
    """
    Extracts the candidate's full name from the first non-empty lines of the resume.
    """
    if not text:
        return ""

    logger.info("Extracting candidate name from resume text.")

    # Split the text into lines and clean them
    lines = [line.strip() for line in text.split("\n")]
    non_empty_lines = [line for line in lines if line]

    known_prefixes = {"Mr", "Ms", "Dr", "Mr.", "Ms.", "Dr."}

    for line in non_empty_lines:
        if len(line) > 50:
            continue

        # Split into words
        words = line.split()
        num_words = len(words)
        if not (2 <= num_words <= 5):
            continue

        # Check if each word starts with an uppercase letter or is a known prefix
        all_words_valid = True
        for word in words:
            clean_word = word.strip(",.()\"'")
            if not clean_word:
                continue
            if clean_word in known_prefixes:
                continue
            if not clean_word[0].isupper():
                all_words_valid = False
                break

        if all_words_valid:
            logger.info(f"Detected full name: {line}")
            return line

    logger.info("No confident full name detected.")
    return ""

