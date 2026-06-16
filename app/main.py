from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.api import router
from app.models import Base, engine
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="GitLab Dashboard", version="1.0.0")

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(router)


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
