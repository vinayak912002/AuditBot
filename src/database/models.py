from sqlalchemy import Column, Integer, String, DateTime, Enum, JSON
from sqlalchemy.ext.declarative import declarative_base
import enum
import datetime

Base = declarative_base()

class JobStatus(enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class InvoiceJob(Base):
    __tablename__ = "invoice_jobs"

    id = Column(Integer, primary_key=True)
    file_id = Column(String, unique=True, nullable=False)
    file_name = Column(String)
    status = Column(Enum(JobStatus), default=JobStatus.PENDING)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    extracted_data = Column(JSON, nullable=True)
    error_message = Column(String, nullable=True)

    def __repr__(self):
        return f"<InvoiceJob(id={self.id}, file_id='{self.file_id}', status='{self.status}')>"
