from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    PROJECT_NAME: str = "MediaFlow"
    API_V1_STR: str = "/api/v1"
    CORS_ORIGINS: list[str] = ["*"]
    
    # Storage settings
    DOWNLOAD_PATH: str = "downloads"
    
    # Extraction settings
    ANALYSIS_TIMEOUT: int = 15
    
    class Config:
        case_sensitive = True

settings = Settings()

# Ensure directories exist
if os.environ.get("VERCEL"):
    settings.DOWNLOAD_PATH = "/tmp/downloads"

os.makedirs(settings.DOWNLOAD_PATH, exist_ok=True)
