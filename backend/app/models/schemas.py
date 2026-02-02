from pydantic import BaseModel
from typing import List, Optional

class MediaFormat(BaseModel):
    format_id: str
    extension: str
    resolution: Optional[str] = None
    filesize: Optional[int] = None
    quality_label: Optional[str] = None
    url: Optional[str] = None

class MediaMetadata(BaseModel):
    id: str
    title: str
    thumbnail: Optional[str] = None
    duration: Optional[float] = None
    uploader: Optional[str] = None
    platform: str
    formats: List[MediaFormat] = []
    original_url: str

class AnalysisRequest(BaseModel):
    url: str

class AnalysisResponse(BaseModel):
    success: bool
    data: Optional[MediaMetadata] = None
    error: Optional[str] = None
