"""Backup history model."""
from sqlalchemy import Column, Integer, String, BigInteger, DateTime, Text
from sqlalchemy.sql import func
from app.database import Base


class BackupHistory(Base):
    """Backup operation history."""

    __tablename__ = "backup_history"

    id = Column(Integer, primary_key=True, index=True)
    destination = Column(String(500), nullable=False)
    destination_type = Column(String(50))  # local, nas, s3, b2
    status = Column(String(20), nullable=False)  # running, complete, failed
    files_backed_up = Column(Integer, default=0)
    total_size = Column(BigInteger, default=0)
    error_message = Column(Text)
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<BackupHistory {self.id}: {self.status}>"
