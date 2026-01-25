"""Activity log model."""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func
from app.database import Base


class ActivityLog(Base):
    """Audit log of all user actions."""

    __tablename__ = "activity_log"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    action = Column(String(50), nullable=False, index=True)  # download, import, heart, unheart, delete, export
    entity_type = Column(String(50))  # artist, album, track
    entity_id = Column(Integer)
    details = Column(JSON)  # Additional context (use JSON for SQLite compat)
    ip_address = Column(String(45))  # Use String for SQLite compat (supports IPv6)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    def __repr__(self):
        return f"<Activity {self.action} by user {self.user_id}>"
