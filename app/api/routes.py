from fastapi import APIRouter, Depends, Request, BackgroundTasks
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Optional
from app.models import get_db
from app.services.metrics_service import MetricsService
from app.config import settings
import logging

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
logger = logging.getLogger(__name__)


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Render the main dashboard page."""
    return templates.TemplateResponse("dashboard.html", {"request": request})


@router.get("/api/groups")
async def get_groups():
    """Get list of configured groups."""
    groups = settings.get_groups()
    return {
        "groups": groups,
        "mode": "multi" if len(groups) > 1 else "single"
    }


@router.get("/api/metrics/merge-requests")
async def get_merge_request_metrics(
    days: int = 30,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    group_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get merge request metrics, optionally filtered by group or custom date range."""
    service = MetricsService(db, group_id=group_id)
    return service.get_merge_request_metrics(
        days=days,
        start_date=start_date,
        end_date=end_date,
        group_id=group_id
    )


@router.get("/api/metrics/commits")
async def get_commit_metrics(
    days: int = 30,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    group_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get commit activity metrics, optionally filtered by group or custom date range."""
    service = MetricsService(db, group_id=group_id)
    return service.get_commit_metrics(days=days, start_date=start_date, end_date=end_date)


@router.get("/api/metrics/contributors")
async def get_contributor_metrics(
    days: int = 30,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    group_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get contributor statistics, optionally filtered by group or custom date range."""
    service = MetricsService(db, group_id=group_id)
    return service.get_contributor_metrics(
        days=days,
        start_date=start_date,
        end_date=end_date,
        group_id=group_id
    )


@router.get("/api/metrics/comments")
async def get_comment_metrics(
    days: int = 30,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    group_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get MR comment/review metrics, optionally filtered by group or custom date range."""
    service = MetricsService(db, group_id=group_id)
    return service.get_comment_metrics(
        days=days,
        start_date=start_date,
        end_date=end_date,
        group_id=group_id
    )


@router.post("/api/refresh")
async def refresh_all_metrics(days: int = 30, background_tasks: BackgroundTasks = None, db: Session = Depends(get_db)):
    """Force refresh all metrics from GitLab (Phase 1 - fast, MRs only)."""
    service = MetricsService(db)

    # Phase 1: Fast refresh (MRs only, no detailed commit/comment counts)
    logger.info(f"Phase 1 refresh: MRs only (fast)")
    service.refresh_merge_requests(days=days)
    service.refresh_commits(days=days)
    service.refresh_comments(days=days)
    service.refresh_contributors(days=days, fetch_details=False)  # Fast: MR counts only

    # Phase 2 will be triggered separately by the client
    return {"status": "success", "message": "Fast refresh complete (MRs only). Use /api/refresh-detailed for commit/comment counts."}


def background_refresh_detailed(days: int):
    """Background task to fetch detailed commit/comment counts."""
    from app.models import get_db
    logger.info(f"Phase 2 background refresh started: fetching detailed commit/comment counts for {days} days")

    db = next(get_db())
    try:
        service = MetricsService(db)
        service.refresh_contributors_detailed(days=days)
        logger.info("Phase 2 complete: detailed commit/comment counts refreshed")
    except Exception as e:
        logger.error(f"Phase 2 failed: {e}")
    finally:
        db.close()


@router.post("/api/refresh-detailed")
async def refresh_detailed_metrics(days: int = 30, background_tasks: BackgroundTasks = None):
    """Phase 2: Fetch detailed commit/comment counts in background (slow, 3-5 minutes)."""
    if background_tasks:
        background_tasks.add_task(background_refresh_detailed, days)
        return {"status": "success", "message": f"Phase 2 started in background. This will take 3-5 minutes for {days} days."}
    else:
        return {"status": "error", "message": "Background tasks not available"}
