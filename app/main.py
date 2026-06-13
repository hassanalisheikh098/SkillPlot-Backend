import os
import uvicorn
from app.routes import auth, resume, jobs, chatbot, roadmap, gamification, users
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add this — ensures CORS headers appear even on 500s
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    import logging
    logging.getLogger(__name__).error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {str(exc)}"},
        headers={"Access-Control-Allow-Origin": "*"},
    )

# Include service routers under v1 API prefix
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(resume.router, prefix="/api/v1/resume", tags=["Resume Analysis"])
app.include_router(jobs.router, prefix="/api/v1/jobs", tags=["Job Roles & Skill Gap"])
app.include_router(chatbot.router, prefix="/api/v1/chat", tags=["Career Chatbot"])
app.include_router(roadmap.router, prefix="/api/v1/roadmap", tags=["Roadmap"])
app.include_router(gamification.router, prefix="/api/v1/gamification", tags=["Gamification"])
app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])

@app.get("/health", tags=["Health"])
async def health_check():
    """
    Simple health verification endpoint.
    """
    return {
        "status": "healthy",
        "service": "Career Readiness & Resume Analyzer API"
    }

@app.get("/", tags=["Health"])
async def root():
    """
    Service root entrypoint providing system status.
    """
    return {
        "message": "Welcome to the Career Readiness & Resume Analyzer API",
        "version": "1.0.0",
        "status": "healthy"
    }

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
