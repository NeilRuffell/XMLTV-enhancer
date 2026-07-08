from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse

from .config import load_settings
from .service import EnrichmentService

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

settings = load_settings()
service = EnrichmentService(settings)
app = FastAPI(title="XMLTV Enhancer", version="0.1.0")


@app.get("/health")
async def health() -> dict:
    return service.health()


@app.get("/refresh")
async def refresh(clear: int = Query(default=0)) -> dict:
    return await service.refresh(clear_cache=bool(clear))


@app.get("/stats")
async def stats() -> dict:
    return service.last_stats


@app.get("/epg.xml")
async def epg() -> FileResponse:
    path = settings.output_epg_path
    if not path.exists():
        raise HTTPException(status_code=404, detail="epg_not_built")
    return FileResponse(path, media_type="application/xml", filename="epg.xml")


@app.get("/genres.xml")
async def genres() -> FileResponse:
    path = settings.output_genres_path
    if not path.exists():
        raise HTTPException(status_code=404, detail="genres_not_built")
    return FileResponse(path, media_type="application/xml", filename="genres.xml")


@app.get("/inspect")
async def inspect(title: str = Query(..., min_length=1)) -> dict:
    return await service.inspect(title)


@app.get("/audit")
async def audit() -> dict:
    return await service.audit()
