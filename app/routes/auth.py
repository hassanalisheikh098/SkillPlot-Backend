import logging
from fastapi import APIRouter, HTTPException, status
from app.models import UserSignUpRequest, UserLoginRequest, AuthResponse
from app.services.supabase_client import supabase

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def signup(credentials: UserSignUpRequest):
    """
    Register a new user using Supabase Authentication.
    """
    if not supabase:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase client is not initialized. Please verify configuration."
        )

    try:
        # Register user with Supabase auth
        response = supabase.auth.sign_up({
            "email": credentials.email,
            "password": credentials.password
        })

        # Extract session if automatically logged in/verified
        session_data = None
        if response.session:
            session_data = {
                "access_token": response.session.access_token,
                "refresh_token": response.session.refresh_token,
                "expires_at": response.session.expires_at,
                "user": {
                    "id": response.user.id,
                    "email": response.user.email
                }
            }

        return AuthResponse(
            status="success",
            message="User registration successful.",
            session=session_data
        )
    except Exception as e:
        logger.error(f"Sign up process failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Registration failed: {str(e)}"
        )

@router.post("/login", response_model=AuthResponse)
async def login(credentials: UserLoginRequest):
    """
    Log in an existing user using email and password via Supabase.
    """
    if not supabase:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase client is not initialized. Please verify configuration."
        )

    try:
        # Sign in using password
        response = supabase.auth.sign_in_with_password({
            "email": credentials.email,
            "password": credentials.password
        })

        session_data = None
        if response.session:
            session_data = {
                "access_token": response.session.access_token,
                "refresh_token": response.session.refresh_token,
                "expires_at": response.session.expires_at,
                "user": {
                    "id": response.user.id,
                    "email": response.user.email
                }
            }

        return AuthResponse(
            status="success",
            message="Login successful.",
            session=session_data
        )
    except Exception as e:
        logger.error(f"Login process failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}"
        )
