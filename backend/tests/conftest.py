"""Pytest fixtures for Barbossa tests."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.main import app
from app.database import Base, get_db
from app.services.auth import AuthService

# In-memory SQLite for tests
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db():
    """Create a fresh database for each test."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db):
    """Create a test client with the test database."""
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def test_user(db):
    """Create a test user."""
    auth = AuthService(db)
    return auth.create_user("testuser", "testpass")


@pytest.fixture
def admin_user(db):
    """Create an admin user."""
    auth = AuthService(db)
    return auth.create_user("adminuser", "adminpass", is_admin=True)


@pytest.fixture
def auth_headers(db, test_user):
    """Get authorization headers for test user."""
    auth = AuthService(db)
    token = auth.create_token(test_user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_auth_headers(db, admin_user):
    """Get authorization headers for admin user."""
    auth = AuthService(db)
    token = auth.create_token(admin_user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_token(db, test_user):
    """Get raw JWT token for test user (used for WebSocket)."""
    auth = AuthService(db)
    return auth.create_token(test_user.id)


@pytest.fixture
def db_session(db):
    """Alias for db fixture (used by some tests)."""
    return db


@pytest.fixture
def test_artist(db):
    """Create a test artist."""
    from app.models.artist import Artist
    artist = Artist(
        name="Test Artist",
        normalized_name="test artist",
        sort_name="test artist"
    )
    db.add(artist)
    db.commit()
    db.refresh(artist)
    return artist


@pytest.fixture
def test_album(db, test_artist):
    """Create a test album."""
    from app.models.album import Album
    album = Album(
        artist_id=test_artist.id,
        title="Test Album",
        normalized_title="test album",
        year=2024,
        total_tracks=10,
        available_tracks=10,
        status="complete"
    )
    db.add(album)
    db.commit()
    db.refresh(album)
    return album


@pytest.fixture
def test_track(db, test_album):
    """Create a test track."""
    from app.models.track import Track
    track = Track(
        album_id=test_album.id,
        title="Test Track",
        normalized_title="test track",
        track_number=1,
        disc_number=1,
        duration=180,
        sample_rate=44100,
        bit_depth=16,
        format="flac",
        source="import",
        is_lossy=False
    )
    db.add(track)
    db.commit()
    db.refresh(track)
    return track
