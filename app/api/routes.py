from fastapi import APIRouter, Depends, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Optional
import csv
from io import StringIO
from datetime import datetime
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


@router.get("/api/metrics/comparison")
async def get_comparison_metrics(
    days: int = 30,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    group_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get comparison metrics vs previous period."""
    service = MetricsService(db, group_id=group_id)
    return service.get_comparison_metrics(
        days=days,
        start_date=start_date,
        end_date=end_date,
        group_id=group_id
    )


@router.get("/api/metrics/trends")
async def get_trend_metrics(
    days: int = 90,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    group_id: Optional[str] = None,
    period: str = 'week',
    db: Session = Depends(get_db)
):
    """Get trend analysis data (MR velocity over time)."""
    service = MetricsService(db, group_id=group_id)
    return service.get_trend_metrics(
        days=days,
        start_date=start_date,
        end_date=end_date,
        group_id=group_id,
        period=period
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


@router.get("/api/export/contributors")
async def export_contributors_csv(
    days: int = 30,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    group_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Export contributor stats to CSV."""
    try:
        service = MetricsService(db, group_id=group_id)
        data = service.get_contributor_metrics(days=days, start_date=start_date, end_date=end_date, group_id=group_id)

        # Create CSV
        output = StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=['name', 'username', 'mr_count', 'comment_count', 'last_activity'],
            extrasaction='ignore'
        )
        writer.writeheader()
        writer.writerows(data['all_contributors'])

        # Generate filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        date_suffix = f"_{start_date}_to_{end_date}" if start_date and end_date else f"_{days}days"
        group_suffix = f"_{group_id}" if group_id else "_all_groups"
        filename = f"contributors{date_suffix}{group_suffix}_{timestamp}.csv"

        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        logger.error(f"Error exporting contributors CSV: {e}", exc_info=True)
        return {"error": str(e)}


@router.get("/api/export/merge-requests")
async def export_merge_requests_csv(
    days: int = 30,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    group_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Export merge requests to CSV."""
    try:
        service = MetricsService(db, group_id=group_id)
        data = service.get_merge_request_metrics(days=days, start_date=start_date, end_date=end_date, group_id=group_id)

        # Create CSV
        output = StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=['title', 'author', 'state', 'created_at', 'merged_at', 'time_to_merge_hours', 'web_url'],
            extrasaction='ignore'
        )
        writer.writeheader()
        writer.writerows(data['merge_requests'])

        # Generate filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        date_suffix = f"_{start_date}_to_{end_date}" if start_date and end_date else f"_{days}days"
        group_suffix = f"_{group_id}" if group_id else "_all_groups"
        filename = f"merge_requests{date_suffix}{group_suffix}_{timestamp}.csv"

        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        logger.error(f"Error exporting MRs CSV: {e}", exc_info=True)
        return {"error": str(e)}


@router.get("/api/export/stale-mrs")
async def export_stale_mrs_csv(
    days: int = 30,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    group_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Export stale MRs to CSV."""
    try:
        service = MetricsService(db, group_id=group_id)
        data = service.get_merge_request_metrics(days=days, start_date=start_date, end_date=end_date, group_id=group_id)

        # Filter to only stale MRs (open and older than threshold)
        from datetime import datetime, timedelta
        stale_threshold = datetime.utcnow() - timedelta(days=settings.stale_mr_days)

        stale_mrs = []
        for mr in data.get('merge_requests', []):
            if mr.get('state') == 'opened':
                created_at = datetime.fromisoformat(mr.get('created_at'))
                if created_at < stale_threshold:
                    days_open = (datetime.utcnow() - created_at).days
                    stale_mrs.append({
                        'title': mr.get('title'),
                        'author': mr.get('author'),
                        'project_name': mr.get('project_name'),
                        'days_open': days_open,
                        'created_at': mr.get('created_at'),
                        'web_url': mr.get('web_url')
                    })

        # Create CSV
        output = StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=['title', 'author', 'project_name', 'days_open', 'created_at', 'web_url'],
            extrasaction='ignore'
        )
        writer.writeheader()
        writer.writerows(stale_mrs)

        # Generate filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        group_suffix = f"_{group_id}" if group_id else "_all_groups"
        filename = f"stale_mrs{group_suffix}_{timestamp}.csv"

        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        logger.error(f"Error exporting stale MRs CSV: {e}", exc_info=True)
        return {"error": str(e)}


@router.get("/api/export/summary")
async def export_summary_csv(
    days: int = 30,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    group_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Export summary metrics to CSV."""
    try:
        service = MetricsService(db, group_id=group_id)

        # Fetch all metrics
        mr_data = service.get_merge_request_metrics(days=days, start_date=start_date, end_date=end_date, group_id=group_id)
        contributor_data = service.get_contributor_metrics(days=days, start_date=start_date, end_date=end_date, group_id=group_id)
        comment_data = service.get_comment_metrics(days=days, start_date=start_date, end_date=end_date, group_id=group_id)

        # Create summary rows
        summary_data = [
            {'metric': 'Total MRs', 'value': mr_data['total']},
            {'metric': 'Merged MRs', 'value': mr_data['merged']},
            {'metric': 'Open MRs', 'value': mr_data['open']},
            {'metric': 'Closed MRs', 'value': mr_data['closed']},
            {'metric': 'Avg Time to Merge (hours)', 'value': f"{mr_data['avg_time_to_merge_hours']:.1f}"},
            {'metric': 'Median Time to Merge (hours)', 'value': f"{mr_data['median_time_to_merge_hours']:.1f}"},
            {'metric': 'Avg Review Response (hours)', 'value': f"{mr_data.get('avg_review_response_hours', 0):.1f}"},
            {'metric': 'Median Review Response (hours)', 'value': f"{mr_data.get('median_review_response_hours', 0):.1f}"},
            {'metric': 'Stale MRs', 'value': mr_data.get('stale', 0)},
            {'metric': 'Total Contributors', 'value': contributor_data['total_contributors']},
            {'metric': 'Total Comments', 'value': comment_data['total']},
        ]

        # Create CSV
        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=['metric', 'value'])
        writer.writeheader()
        writer.writerows(summary_data)

        # Generate filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        date_suffix = f"_{start_date}_to_{end_date}" if start_date and end_date else f"_{days}days"
        group_suffix = f"_{group_id}" if group_id else "_all_groups"
        filename = f"summary{date_suffix}{group_suffix}_{timestamp}.csv"

        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        logger.error(f"Error exporting summary CSV: {e}", exc_info=True)
        return {"error": str(e)}
