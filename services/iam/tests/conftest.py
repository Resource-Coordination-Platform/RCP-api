import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import MagicMock
# Add the app directory to the path so we can import modules
import os
import sys
iam_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
root_dir = os.path.dirname(os.path.dirname(iam_dir))

sys.path.append(iam_dir)
sys.path.append(os.path.join(root_dir, "packages", "common"))
sys.path.append(os.path.join(root_dir, "packages", "clients"))
sys.path.append(os.path.join(root_dir, "packages", "contracts"))

# Import the FastAPI app and dependencies
from app.main import app
from app.db.database import get_db
from app.models import Base

# Setup SQLite in-memory database for testing
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB

@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Remove schema for SQLite compatibility
for table in Base.metadata.tables.values():
    table.schema = None

# Create tables
Base.metadata.create_all(bind=engine)

from unittest.mock import MagicMock, patch

@pytest.fixture(scope="session", autouse=True)
def mock_outbox_emit():
    with patch("app.services.auth.emit") as mock_emit:
        yield mock_emit

@pytest.fixture(scope="session", autouse=True)
def mock_relay():
    with patch("app.main.start_relay") as mock_start:
        # start_relay returns a threading.Event that gets .set() called on it
        mock_event = MagicMock()
        mock_start.return_value = mock_event
        yield mock_start

@pytest.fixture(scope="session")
def db_engine():
    yield engine

@pytest.fixture(scope="function")
def db_session(db_engine):
    """Provides a fresh database session for each test."""
    connection = db_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()

@pytest.fixture(scope="function")
def client(db_session):
    """Provides a TestClient for testing API endpoints."""
    # We need to override get_db to return the specific session for the test
    def override_get_db_for_test():
        yield db_session
        
    app.dependency_overrides[get_db] = override_get_db_for_test
    
    with TestClient(app) as c:
        yield c
