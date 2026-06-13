import logging
from supabase import create_client, Client
from app.config import settings

logger = logging.getLogger(__name__)

# Initialize the Supabase client safely
supabase: Client = None

if settings.SUPABASE_URL and settings.SUPABASE_KEY:
    try:
        supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
        logger.info("Supabase client initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize Supabase client: {e}")
else:
    logger.warning(
        "Supabase credentials (SUPABASE_URL/SUPABASE_KEY) are missing. "
        "Supabase client initialization skipped."
    )
