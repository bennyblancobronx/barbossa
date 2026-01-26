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


@pytest.fixture
def real_audio_sample():
    """Generate a minimal valid WAV audio file for testing.

    Creates a proper WAV file with PCM audio data that passes
    format validation by beets/exiftool.
    """
    import struct
    import io

    # WAV file parameters
    sample_rate = 44100
    num_channels = 2
    bits_per_sample = 16
    duration_seconds = 1  # 1 second of audio

    num_samples = sample_rate * duration_seconds
    bytes_per_sample = bits_per_sample // 8
    data_size = num_samples * num_channels * bytes_per_sample

    # Generate silence (zeros) as audio data
    audio_data = b'\x00' * data_size

    # Build WAV file
    wav_buffer = io.BytesIO()

    # RIFF header
    wav_buffer.write(b'RIFF')
    wav_buffer.write(struct.pack('<I', 36 + data_size))  # File size - 8
    wav_buffer.write(b'WAVE')

    # fmt chunk
    wav_buffer.write(b'fmt ')
    wav_buffer.write(struct.pack('<I', 16))  # Chunk size
    wav_buffer.write(struct.pack('<H', 1))   # Audio format (PCM)
    wav_buffer.write(struct.pack('<H', num_channels))
    wav_buffer.write(struct.pack('<I', sample_rate))
    wav_buffer.write(struct.pack('<I', sample_rate * num_channels * bytes_per_sample))  # Byte rate
    wav_buffer.write(struct.pack('<H', num_channels * bytes_per_sample))  # Block align
    wav_buffer.write(struct.pack('<H', bits_per_sample))

    # data chunk
    wav_buffer.write(b'data')
    wav_buffer.write(struct.pack('<I', data_size))
    wav_buffer.write(audio_data)

    return wav_buffer.getvalue()


@pytest.fixture
def audio_album_folder(tmp_path, real_audio_sample):
    """Create a test album folder with real audio files.

    Returns a folder containing valid WAV audio files suitable for
    end-to-end import testing with real audio processing.
    """
    album_dir = tmp_path / "Test Artist" / "Test Album (2024)"
    album_dir.mkdir(parents=True)

    # Create multiple audio tracks
    (album_dir / "01 - Track One.wav").write_bytes(real_audio_sample)
    (album_dir / "02 - Track Two.wav").write_bytes(real_audio_sample)

    # Create cover art (minimal valid JPEG)
    # JPEG magic bytes + minimal structure
    jpeg_header = bytes([
        0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00, 0x01,
        0x01, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00, 0xFF, 0xDB, 0x00, 0x43,
    ])
    jpeg_data = jpeg_header + b'\x00' * 64 + bytes([0xFF, 0xD9])  # Minimal JPEG
    (album_dir / "cover.jpg").write_bytes(jpeg_data)

    return album_dir


@pytest.fixture
def mock_beets_client():
    """Factory fixture to create mocked BeetsClient with configurable behavior.

    Use this for tests that need realistic beets behavior without
    calling the actual beets subprocess.
    """
    from unittest.mock import MagicMock, AsyncMock

    def _create_mock(
        identify_result=None,
        import_returns_same_path=True,
        import_raises=None
    ):
        mock = MagicMock()

        # Default identify result
        if identify_result is None:
            identify_result = {
                "artist": "Test Artist",
                "album": "Test Album",
                "year": 2024,
                "confidence": 0.95
            }
        mock.identify = AsyncMock(return_value=identify_result)

        # Configure import behavior
        if import_raises:
            mock.import_album = AsyncMock(side_effect=import_raises)
            mock.import_with_metadata = AsyncMock(side_effect=import_raises)
        elif import_returns_same_path:
            # Returns the input path (simulates no-move or same-location import)
            async def return_input(path, **kwargs):
                return path
            mock.import_album = AsyncMock(side_effect=return_input)
            mock.import_with_metadata = AsyncMock(side_effect=return_input)

        mock.fetch_artwork = AsyncMock(return_value=None)

        return mock

    return _create_mock


@pytest.fixture
def mock_exiftool_client():
    """Factory fixture to create mocked ExifToolClient.

    Returns track metadata based on files found in the given path.
    """
    from unittest.mock import MagicMock, AsyncMock
    from pathlib import Path

    def _create_mock(tracks_metadata=None):
        mock = MagicMock()

        if tracks_metadata is None:
            # Default: generate metadata based on audio files in path
            async def extract_metadata(path):
                path = Path(path)
                audio_extensions = {".flac", ".mp3", ".m4a", ".ogg", ".wav", ".aiff"}
                tracks = []

                for i, f in enumerate(sorted(path.iterdir())):
                    if f.is_file() and f.suffix.lower() in audio_extensions:
                        tracks.append({
                            "title": f.stem.split(" - ", 1)[-1] if " - " in f.stem else f.stem,
                            "track_number": i + 1,
                            "disc_number": 1,
                            "duration": 180,
                            "sample_rate": 44100,
                            "bit_depth": 16,
                            "format": f.suffix[1:].upper(),
                            "path": str(f),
                            "file_size": f.stat().st_size if f.exists() else 1000
                        })

                return tracks

            mock.get_album_metadata = AsyncMock(side_effect=extract_metadata)
        else:
            mock.get_album_metadata = AsyncMock(return_value=tracks_metadata)

        return mock

    return _create_mock


@pytest.fixture
def pending_review_with_files(db, tmp_path, real_audio_sample):
    """Create a pending review with actual audio files on disk.

    Provides both the database record and real files for E2E testing.
    """
    from app.models.pending_review import PendingReview, PendingReviewStatus

    # Create review folder with audio
    review_folder = tmp_path / "review" / "pending-album-test"
    review_folder.mkdir(parents=True)
    (review_folder / "01 - Track One.wav").write_bytes(real_audio_sample)
    (review_folder / "02 - Track Two.wav").write_bytes(real_audio_sample)

    # Create database record
    review = PendingReview(
        path=str(review_folder),
        suggested_artist="Suggested Artist",
        suggested_album="Suggested Album",
        beets_confidence=0.85,
        track_count=2,
        quality_info={"sample_rate": 44100, "bit_depth": 16, "format": "wav"},
        source="import",
        source_url="",
        status=PendingReviewStatus.PENDING
    )
    db.add(review)
    db.commit()
    db.refresh(review)

    return review, review_folder
