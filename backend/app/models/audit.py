from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func
from app.core.db import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(128), default="admin")
    prompt = Column(Text, nullable=False)
    selected_tool = Column(String(128), nullable=False)
    data_source = Column(String(64), nullable=False)
    result_count = Column(Integer, default=0)
    response_summary = Column(Text, nullable=False)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
