from sqlalchemy import Column, Integer, String, DateTime, Enum, JSON, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import enum
import datetime

Base = declarative_base()

class JobStatus(str, enum.Enum):
    NEW = "NEW"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"

class UserCredential(Base):
    """
    Stores OAuth2 tokens and identification for each user.
    The 'email' is used as the primary identifier across the system.
    """
    __tablename__ = "user_credentials"
    
    email = Column(String, primary_key=True)
    token_data = Column(JSON, nullable=False)
    drive_folder_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    # Relationship: One user can have many invoice jobs.
    jobs = relationship("InvoiceJob", back_populates="owner")

class InvoiceJob(Base):
    """
    Tracks the state and data of each invoice file found in Google Drive.
    Ensures idempotency using the unique 'file_id' from Google Drive.
    """
    __tablename__ = "invoice_jobs"

    file_id = Column(String, primary_key=True)
    file_name = Column(String)
    status = Column(Enum(JobStatus), default=JobStatus.NEW)
    
    # Isolation: Link job to a specific user.
    user_email = Column(String, ForeignKey("user_credentials.email"), nullable=False)
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    retry_count = Column(Integer, default=0)
    error_message = Column(String, nullable=True)
    extracted_data = Column(JSON, nullable=True)

    owner = relationship("UserCredential", back_populates="jobs")

    def __repr__(self):
        return f"<InvoiceJob(file_id='{self.file_id}', user='{self.user_email}', status='{self.status}')>"
