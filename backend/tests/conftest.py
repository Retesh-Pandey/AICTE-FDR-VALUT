import pytest
from fastapi.testclient import TestClient

from app.db.seed import seed_database
from app.db.session import SessionLocal
from app.main import app


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    seed_database(force=True)
    yield

@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client

@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def auth_headers(db):
    """Generates bearer authorization headers for each demo role."""
    from app.api.auth import create_access_token
    from app.db.models import User, UserRole

    inst_user = db.query(User).filter(User.role == UserRole.institution).first()
    officer_user = db.query(User).filter(User.role == UserRole.officer).first()
    admin_user = db.query(User).filter(User.role == UserRole.admin).first()

    return {
        "institution": {
            "Authorization": f"Bearer {create_access_token({'sub': str(inst_user.id), 'email': inst_user.email, 'role': 'institution'})}",
            "user": inst_user,
        },
        "officer": {
            "Authorization": f"Bearer {create_access_token({'sub': str(officer_user.id), 'email': officer_user.email, 'role': 'officer'})}",
            "user": officer_user,
        },
        "admin": {
            "Authorization": f"Bearer {create_access_token({'sub': str(admin_user.id), 'email': admin_user.email, 'role': 'admin'})}",
            "user": admin_user,
        },
    }

