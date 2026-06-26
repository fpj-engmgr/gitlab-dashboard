from sqlalchemy import Column, Integer, String, DateTime, Float, Boolean, UniqueConstraint
from datetime import datetime
from .database import Base


class MergeRequest(Base):
    __tablename__ = "merge_requests"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(String, index=True, nullable=True)  # Multi-group support
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
    lines_added = Column(Integer, nullable=True)
    lines_deleted = Column(Integer, nullable=True)
    lines_changed = Column(Integer, nullable=True)  # Total: additions + deletions


class Commit(Base):
    __tablename__ = "commits"

    id = Column(String, primary_key=True)
    group_id = Column(String, index=True, nullable=True)  # Multi-group support
    project_id = Column(Integer, index=True)
    project_name = Column(String)
    author_name = Column(String)
    author_email = Column(String)
    committed_date = Column(DateTime)
    title = Column(String)
    message = Column(String)
    web_url = Column(String)


class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(String, index=True, nullable=True)  # Multi-group support
    note_id = Column(Integer, unique=True)
    mr_id = Column(Integer, index=True)
    project_id = Column(Integer, index=True)
    project_name = Column(String)
    author = Column(String)
    body = Column(String)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    mr_title = Column(String)
    web_url = Column(String)


class Contributor(Base):
    __tablename__ = "contributors"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(String, index=True, nullable=True)  # Multi-group support
    username = Column(String)
    name = Column(String)
    email = Column(String)
    commit_count = Column(Integer, default=0)
    mr_count = Column(Integer, default=0)
    comment_count = Column(Integer, default=0)
    last_activity = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint('group_id', 'username', name='_group_username_uc'),
    )


class CacheMetadata(Base):
    __tablename__ = "cache_metadata"

    id = Column(Integer, primary_key=True, index=True)
    data_type = Column(String, unique=True)
    last_updated = Column(DateTime, default=datetime.utcnow)
    is_updating = Column(Boolean, default=False)
