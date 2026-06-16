from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.models import get_db
from app.services.metrics_service import MetricsService

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Render the main dashboard page."""
    return templates.TemplateResponse("dashboard.html", {"request": request})


@router.get("/api/metrics/merge-requests")
async def get_merge_request_metrics(days: int = 30, db: Session = Depends(get_db)):
    """Get merge request metrics."""
    service = MetricsService(db)
    return service.get_merge_request_metrics(days=days)


@router.get("/api/metrics/commits")
async def get_commit_metrics(days: int = 30, db: Session = Depends(get_db)):
    """Get commit activity metrics."""
    service = MetricsService(db)
    return service.get_commit_metrics(days=days)


@router.get("/api/metrics/contributors")
async def get_contributor_metrics(days: int = 30, db: Session = Depends(get_db)):
    """Get contributor statistics."""
    service = MetricsService(db)
    return service.get_contributor_metrics(days=days)


@router.get("/api/metrics/comments")
async def get_comment_metrics(days: int = 30, db: Session = Depends(get_db)):
    """Get MR comment/review metrics."""
    service = MetricsService(db)
    return service.get_comment_metrics(days=days)


@router.post("/api/refresh")
async def refresh_all_metrics(days: int = 30, db: Session = Depends(get_db)):
    """Force refresh all metrics from GitLab."""
    service = MetricsService(db)
    service.refresh_merge_requests(days=days)
    service.refresh_commits(days=days)
    service.refresh_comments(days=days)
    service.refresh_contributors(days=days)
    return {"status": "success", "message": "All metrics refreshed"}
