"""Tests for library endpoints."""
import pytest
from app.models.artist import Artist
from app.models.album import Album
from app.models.track import Track


@pytest.fixture
def sample_library(db):
    """Create sample library data."""
    # Artist
    artist = Artist(
        name="The Beatles",
        normalized_name="beatles",
        sort_name="Beatles, The",
        path="/music/artists/The Beatles",
    )
    db.add(artist)
    db.commit()
    db.refresh(artist)

    # Album
    album = Album(
        artist_id=artist.id,
        title="Abbey Road",
        normalized_title="abbey road",
        year=1969,
        path="/music/artists/The Beatles/Abbey Road (1969)",
        total_tracks=17,
        available_tracks=17,
        source="qobuz",
    )
    db.add(album)
    db.commit()
    db.refresh(album)

    # Tracks
    tracks = []
    for i in range(1, 4):
        track = Track(
            album_id=album.id,
            title=f"Track {i}",
            normalized_title=f"track {i}",
            track_number=i,
            path=f"/music/artists/The Beatles/Abbey Road (1969)/0{i} - Track {i}.flac",
            sample_rate=96000,
            bit_depth=24,
            format="FLAC",
            source="qobuz",
        )
        db.add(track)
        tracks.append(track)
    db.commit()

    return {"artist": artist, "album": album, "tracks": tracks}


def test_list_artists(client, sample_library, auth_headers):
    """Test listing artists."""
    response = client.get("/api/artists", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["name"] == "The Beatles"


def test_list_artists_filter_letter(client, sample_library, auth_headers):
    """Test filtering artists by letter."""
    response = client.get("/api/artists?letter=B", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1  # "Beatles, The" starts with B


def test_get_artist(client, sample_library, auth_headers):
    """Test getting single artist."""
    artist_id = sample_library["artist"].id
    response = client.get(f"/api/artists/{artist_id}", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "The Beatles"


def test_get_artist_not_found(client, auth_headers):
    """Test getting non-existent artist."""
    response = client.get("/api/artists/999", headers=auth_headers)
    assert response.status_code == 404


def test_get_artist_albums(client, sample_library, auth_headers):
    """Test getting artist's albums."""
    artist_id = sample_library["artist"].id
    response = client.get(f"/api/artists/{artist_id}/albums", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["title"] == "Abbey Road"


def test_get_album(client, sample_library, auth_headers):
    """Test getting album details."""
    album_id = sample_library["album"].id
    response = client.get(f"/api/albums/{album_id}", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Abbey Road"
    assert data["artist"]["name"] == "The Beatles"
    assert data["is_hearted"] is False


def test_get_album_tracks(client, sample_library, auth_headers):
    """Test getting album tracks."""
    album_id = sample_library["album"].id
    response = client.get(f"/api/albums/{album_id}/tracks", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    assert data[0]["track_number"] == 1


def test_search(client, sample_library, auth_headers):
    """Test library search."""
    response = client.get("/api/search?q=beatles", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert len(data["artists"]) == 1
    assert data["artists"][0]["name"] == "The Beatles"


def test_heart_album(client, sample_library, auth_headers):
    """Test hearting an album."""
    album_id = sample_library["album"].id
    response = client.post(f"/api/me/library/albums/{album_id}", headers=auth_headers)

    assert response.status_code == 200
    assert "added" in response.json()["message"].lower()


def test_unheart_album(client, db, sample_library, auth_headers, test_user):
    """Test unhearting an album."""
    album_id = sample_library["album"].id

    # Heart first
    client.post(f"/api/me/library/albums/{album_id}", headers=auth_headers)

    # Unheart
    response = client.delete(f"/api/me/library/albums/{album_id}", headers=auth_headers)

    assert response.status_code == 200
    assert "removed" in response.json()["message"].lower()


def test_get_user_library(client, db, sample_library, auth_headers, test_user):
    """Test getting user's library."""
    album_id = sample_library["album"].id

    # Heart album
    client.post(f"/api/me/library/albums/{album_id}", headers=auth_headers)

    # Get library
    response = client.get("/api/me/library", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["is_hearted"] is True
