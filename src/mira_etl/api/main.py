from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from mira_etl.api.routes.health import router as health_router
from mira_etl.api.routes.procurements import router as procurements_router


app = FastAPI(
    title="MIRA API",
    version="0.1.0",
    description="Read-only API for normalized public procurement data.",
)
app.include_router(health_router, prefix="/api/v1")
app.include_router(procurements_router, prefix="/api/v1")

WEB_INDEX = Path(__file__).resolve().parents[3] / "web" / "index.html"


@app.get("/", include_in_schema=False)
def web_index() -> FileResponse:
    return FileResponse(WEB_INDEX)
