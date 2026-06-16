from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.api import router
from app.models import Base, engine
from app.config import settings
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Validate team members configuration on startup
try:
    team_members = settings.get_team_members()
    logger.info(f"Dashboard configured to track {len(team_members)} team members")
except FileNotFoundError as e:
    logger.error(f"Configuration error: {e}")
    logger.error("Create team_members.json from team_members.json.example before starting the dashboard")
    sys.exit(1)
except ValueError as e:
    logger.error(f"Configuration error: {e}")
    sys.exit(1)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="GitLab Dashboard", version="1.0.0")

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(router)


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
