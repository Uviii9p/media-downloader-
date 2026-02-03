from fastapi import APIRouter, HTTPException, Header, Query
from backend.app.models.schemas import AnalysisRequest, AnalysisResponse
from backend.app.services.extractor import extractor
from backend.app.services.streamer import stream_proxy
from backend.app.services.jobs import job_controller
import asyncio
import uuid
from typing import Optional

router = APIRouter()

# Temporary store for metadata
metadata_store = {}
url_cache = {}

@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_url(request: AnalysisRequest):
    # Cache hit
    cached_id = url_cache.get(request.url)
    if cached_id and cached_id in metadata_store:
        return AnalysisResponse(success=True, data=metadata_store[cached_id])

    job_id = str(uuid.uuid4())
    task = asyncio.create_task(extractor.extract_info(request.url))
    job_controller.register_job(job_id, task)
    
    try:
        metadata = await task
        if metadata:
            metadata_store[metadata.id] = metadata
            url_cache[request.url] = metadata.id
            return AnalysisResponse(success=True, data=metadata)
        
        # If metadata is None, it means all strategies failed
        return AnalysisResponse(
            success=False, 
            error="Analysis failed. The link might be private, restricted, or unsupported. Try a different link."
        )
    except Exception as e:
        print(f"[!] Endpoint Error: {str(e)}")
        return AnalysisResponse(success=False, error=f"Analysis error: {str(e)}")

@router.get("/stream")
async def stream_media(
    url: str = Query(...), 
    filename: Optional[str] = Query(None),
    range: Optional[str] = Header(None)
):
    try:
        return await stream_proxy.proxy_stream(url, range, filename)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
