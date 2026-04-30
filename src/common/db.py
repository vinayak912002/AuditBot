import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from src.database.models import Base

load_dotenv()

# Database connection setup
# We use SQLAlchemy as our ORM to interact with PostgreSQL.
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgresroot@localhost:5432/auditbot")

engine = create_engine(DATABASE_URL)
# SessionLocal is the class used to create database sessions.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """
    Creates all tables in the database if they don't already exist.
    Run this via 'python main.py --init-db'.
    """
    Base.metadata.create_all(bind=engine)

def get_db():
    """
    Utility function to handle session opening/closing.
    Can be used as a context manager or in FastAPI dependency injection.
    """
