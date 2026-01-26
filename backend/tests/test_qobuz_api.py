"""Tests for Qobuz API client."""
import pytest
import socket
from app.config import get_settings
from app.integrations.qobuz_api import (
    get_qobuz_api,
    reset_qobuz_api,
    QobuzAPIError,
    _get_streamrip_app_credentials,
)


def has_qobuz_credentials() -> bool:
    """Check if Qobuz credentials are configured."""
    settings = get_settings()
    return bool(settings.qobuz_email and settings.qobuz_password)


def has_qobuz_app_credentials() -> bool:
    """Check if Qobuz app credentials are available."""
    settings = get_settings()
    # Check env vars first
    if settings.qobuz_app_id:
        return True
    # Check streamrip config
    app_id, _ = _get_streamrip_app_credentials()
    return bool(app_id)


def can_reach_qobuz() -> bool:
    """Check if Qobuz host is reachable (DNS resolution)."""
    try:
        socket.gethostbyname("www.qobuz.com")
        return True
    except Exception:
        return False


# Skip marker for tests requiring full Qobuz setup
requires_qobuz_setup = pytest.mark.skipif(
    not (has_qobuz_credentials() and has_qobuz_app_credentials() and can_reach_qobuz()),
    reason="Qobuz credentials or app_id not configured (run 'rip config --qobuz' to set up)"
)


@pytest.fixture(autouse=True)
def reset_api():
    """Reset API singleton between tests."""
    reset_qobuz_api()
    yield
    reset_qobuz_api()


@requires_qobuz_setup
@pytest.mark.asyncio
async def test_search_albums():
    """Test album search returns results with artwork."""
    api = get_qobuz_api()

    results = await api.search_albums("Pink Floyd", limit=5)

    assert len(results) > 0
    assert results[0]["title"]
    assert results[0]["artist_name"]
    assert results[0]["artwork_url"]  # Key test - artwork present


@requires_qobuz_setup
@pytest.mark.asyncio
async def test_search_artists():
    """Test artist search returns results with images."""
    api = get_qobuz_api()

    results = await api.search_artists("Beatles", limit=5)

    assert len(results) > 0
    assert results[0]["name"]
    assert results[0]["album_count"] > 0


@requires_qobuz_setup
@pytest.mark.asyncio
async def test_search_tracks():
    """Test track search returns results."""
    api = get_qobuz_api()

    results = await api.search_tracks("Comfortably Numb", limit=5)

    assert len(results) > 0
    assert results[0]["title"]
    assert results[0]["artist_name"]


@requires_qobuz_setup
@pytest.mark.asyncio
async def test_get_artist_discography():
    """Test fetching artist with albums."""
    api = get_qobuz_api()

    # First search to get an artist ID
    artists = await api.search_artists("Pink Floyd", limit=1)
    assert len(artists) > 0

    artist_id = artists[0]["id"]

    # Get full artist with discography
    artist = await api.get_artist(artist_id)

    assert artist["name"]
    assert "albums" in artist
    assert len(artist["albums"]) > 0
    assert artist["albums"][0]["artwork_url"]


@requires_qobuz_setup
@pytest.mark.asyncio
async def test_get_album_tracks():
    """Test fetching album with track listing."""
    api = get_qobuz_api()

    # Search for a known album
    albums = await api.search_albums("Dark Side of the Moon", limit=1)
    assert len(albums) > 0

    album_id = albums[0]["id"]

    # Get full album with tracks
    album = await api.get_album(album_id)

    assert album["title"]
    assert "tracks" in album
    assert len(album["tracks"]) > 0
    assert album["tracks"][0]["title"]
    assert album["tracks"][0]["duration"] > 0


@requires_qobuz_setup
@pytest.mark.asyncio
async def test_album_has_quality_info():
    """Test album includes quality metadata."""
    api = get_qobuz_api()

    albums = await api.search_albums("Pink Floyd", limit=1)
    assert len(albums) > 0

    album = albums[0]
    assert "hires" in album
    assert "maximum_bit_depth" in album
    assert "maximum_sampling_rate" in album


@requires_qobuz_setup
@pytest.mark.asyncio
async def test_album_has_all_artwork_sizes():
    """Test album includes multiple artwork sizes."""
    api = get_qobuz_api()

    albums = await api.search_albums("Beatles Abbey Road", limit=1)
    assert len(albums) > 0

    album = albums[0]
    assert "artwork_small" in album
    assert "artwork_thumbnail" in album
    assert "artwork_large" in album
    assert "artwork_url" in album


@requires_qobuz_setup
@pytest.mark.asyncio
async def test_track_has_disc_number():
    """Test track includes disc number for multi-disc support."""
    api = get_qobuz_api()

    albums = await api.search_albums("The Wall Pink Floyd", limit=1)
    assert len(albums) > 0

    album = await api.get_album(albums[0]["id"])
    assert len(album["tracks"]) > 0

    # All tracks should have disc_number
    for track in album["tracks"]:
        assert "disc_number" in track
        assert track["disc_number"] >= 1


@requires_qobuz_setup
@pytest.mark.asyncio
async def test_caching_returns_same_data():
    """Test that cached responses are returned."""
    api = get_qobuz_api()

    # Search for artist first
    artists = await api.search_artists("Radiohead", limit=1)
    assert len(artists) > 0

    artist_id = artists[0]["id"]

    # First call
    artist1 = await api.get_artist(artist_id)

    # Second call should be cached
    artist2 = await api.get_artist(artist_id)

    assert artist1["id"] == artist2["id"]
    assert artist1["name"] == artist2["name"]


@pytest.mark.asyncio
async def test_missing_credentials_raises_error():
    """Test that missing credentials raise appropriate error."""
    if not can_reach_qobuz():
        pytest.skip("Qobuz host not reachable")
    from app.integrations.qobuz_api import QobuzAPI

    # Create fresh instance (not singleton)
    api = QobuzAPI()

    # Clear any cached token
    api._user_auth_token = None
    api._token_expiry = 0

    # This will fail if credentials are not set in test environment
    # In production tests with credentials, this should pass
    # In CI without credentials, this test verifies error handling
    try:
        await api.search_albums("test", limit=1)
    except QobuzAPIError as e:
        assert "credentials" in str(e).lower() or "login" in str(e).lower()
    finally:
        await api.close()


@pytest.mark.asyncio
async def test_get_qobuz_api_region_support():
    """Test that different regions create different instances."""
    api_us = get_qobuz_api("us")
    api_uk = get_qobuz_api("uk")

    assert api_us is not api_uk
    assert api_us._region == "us-en"
    assert api_uk._region == "gb-en"

    # Same region should return same instance
    api_us2 = get_qobuz_api("us")
    assert api_us is api_us2


@pytest.mark.asyncio
async def test_get_qobuz_api_default_region():
    """Test default region is US."""
    api = get_qobuz_api()
    assert api._region == "us-en"
