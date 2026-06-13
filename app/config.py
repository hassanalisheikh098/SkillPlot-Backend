import logging
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

# Set up basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load local environment variables from .env file
load_dotenv()

class Settings(BaseSettings):
    """
    Application settings managed via Pydantic Settings.
    Loads settings from environment variables or a local .env file.
    """
    # Supabase connection parameters (defaults allow app initialization)
    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""
    GROQ_API_KEY: str = ""

    # API server configurations
    PORT: int = 8000
    ENVIRONMENT: str = "development"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    def validate_supabase_config(self) -> None:
        """
        Log warnings if Supabase configuration values are missing or default placeholders.
        """
        if not self.SUPABASE_URL or "your-supabase-project" in self.SUPABASE_URL:
            logger.warning("SUPABASE_URL is not configured or is using placeholder credentials.")
        if (
            not self.SUPABASE_KEY 
            or "your-supabase-anon" in self.SUPABASE_KEY 
            or "your-supabase-service-role" in self.SUPABASE_KEY
        ):
            logger.warning(
                "SUPABASE_KEY is not configured or is using placeholder credentials. "
                "Ensure you use the 'service_role' key (NOT anon key) to allow the backend to bypass RLS for writes."
            )

settings = Settings()
settings.validate_supabase_config()
