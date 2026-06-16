from sqlalchemy import Column, Integer, String, DateTime, Float, Boolean
from datetime import datetime
from .database import Base


class MergeRequest(Base):
    __tablename__ = "merge_requests"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, index=True)
    project_name = Column(String)
    iid = Column(Integer)
    title = Column(String)
    state = Column(String)
    author = Column(String)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    merged_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)
    time_to_merge_hours = Column(Float, nullable=True)
    source_branch = Column(String)
    target_branch = Column(String)
    web_url = Column(String)


class Commit(Base):
    __tablename__ = "commits"

    id = Column(String, primary_key=True)
    project_id = Column(Integer, index=True)
    project_name = Column(String)
    author_name = Column(String)
    author_email = Column(String)
    committed_date = Column(DateTime)
    title = Column(String)
    message = Column(String)
    web_url = Column(String)


class Contributor(Base):
    __tablename__ = "contributors"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True)
    name = Column(String)
    email = Column(String)
    commit_count = Column(Integer, default=0)
    mr_count = Column(Integer, default=0)
    last_activity = Column(DateTime, nullable=True)


class CacheMetadata(Base):
    __tablename__ = "cache_metadata"

    id = Column(Integer, primary_key=True, index=True)
    data_type = Column(String, unique=True)
    last_updated = Column(DateTime, default=datetime.utcnow)
    is_updating = Column(Boolean, default=False)
