import { useState, useMemo } from 'react'
import { useQuery } from 'react-query'
import * as api from '../services/api'
import { useAuthStore } from '../stores/auth'
import { usePlayerStore } from '../stores/player'
import ArtistGrid from '../components/ArtistGrid'
import AlbumGrid from '../components/AlbumGrid'
import AlbumModal from '../components/AlbumModal'
import SearchBar from '../components/SearchBar'
import TrackRow from '../components/TrackRow'

const LETTERS = '#ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('')

export default function UserLibrary() {
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedLetter, setSelectedLetter] = useState(null)
  const [selectedArtist, setSelectedArtist] = useState(null)
  const [selectedAlbum, setSelectedAlbum] = useState(null)
  const [viewMode, setViewMode] = useState('albums') // 'albums' or 'tracks'
  const user = useAuthStore(state => state.user)
  const play = usePlayerStore(state => state.play)

  const { data, isLoading, refetch } = useQuery(
    ['user-library', user?.id],
    () => api.getUserLibrary().then(r => r.data),
    { enabled: !!user?.id }
  )

  const { data: tracksData, isLoading: tracksLoading, refetch: refetchTracks } = useQuery(
    ['user-library-tracks', user?.id],
    () => api.getUserLibraryTracks().then(r => r.data),
    { enabled: !!user?.id && viewMode === 'tracks' }
  )

  const albums = data?.items || data?.albums || []
  const tracks = tracksData || []

  // Group albums by artist to create artist list
  const artists = useMemo(() => {
    const artistMap = new Map()
    albums.forEach(album => {
      const artistId = album.artist?.id || album.artist_id
      const artistName = album.artist?.name || album.artist_name || 'Unknown Artist'
      if (!artistMap.has(artistId)) {
        artistMap.set(artistId, {
          id: artistId,
          name: artistName,
          artwork_path: album.artist?.artwork_path
        })
      }
    })
    return Array.from(artistMap.values()).sort((a, b) =>
      a.name.localeCompare(b.name)
    )
  }, [albums])

  // Filter artists by letter
  const filteredArtists = useMemo(() => {
    let result = artists
    if (selectedLetter) {
      if (selectedLetter === '#') {
        result = artists.filter(a => !/^[A-Za-z]/.test(a.name))
      } else {
        result = artists.filter(a =>
          a.name.toUpperCase().startsWith(selectedLetter)
        )
      }
    }
    if (searchQuery) {
      result = result.filter(a =>
        a.name.toLowerCase().includes(searchQuery.toLowerCase())
      )
    }
    return result
  }, [artists, selectedLetter, searchQuery])

  // Get albums for selected artist
  const artistAlbums = useMemo(() => {
    if (!selectedArtist) return []
    return albums.filter(album => {
      const artistId = album.artist?.id || album.artist_id
      return artistId === selectedArtist.id
    })
  }, [albums, selectedArtist])

  const handleArtistClick = (artist) => {
    setSelectedArtist(artist)
    setSelectedLetter(null)
    setSearchQuery('')
  }

  const handleBackToArtists = () => {
    setSelectedArtist(null)
  }

  const handleAlbumClick = (album) => {
    setSelectedAlbum(album)
  }

  const handleCloseModal = () => {
    setSelectedAlbum(null)
    refetch()
    refetchTracks()
  }

  const handlePlayTrack = (track, index) => {
    play(track, tracks)
  }

  const handleTrackHeart = () => {
    refetchTracks()
  }

  return (
    <div className="page-user-library">
      <header className="page-header">
        <div className="page-header-content">
          {selectedArtist ? (
            <>
              <button className="btn-back" onClick={handleBackToArtists}>
                <BackIcon />
              </button>
              <h1 className="text-2xl">{selectedArtist.name}</h1>
              <span className="text-muted">{artistAlbums.length} albums</span>
            </>
          ) : (
            <>
              <h1 className="text-2xl">My Library</h1>
              <div className="view-toggle">
                <button
                  className={`view-toggle-btn ${viewMode === 'albums' ? 'is-active' : ''}`}
                  onClick={() => { setViewMode('albums'); setSelectedArtist(null) }}
                >
                  Albums ({albums.length})
                </button>
                <button
                  className={`view-toggle-btn ${viewMode === 'tracks' ? 'is-active' : ''}`}
                  onClick={() => { setViewMode('tracks'); setSelectedArtist(null) }}
                >
                  Tracks ({tracks.length})
                </button>
              </div>
            </>
          )}
        </div>
      </header>

      {/* A-Z nav and search only when viewing albums/artists */}
      {!selectedArtist && viewMode === 'albums' && (
        <>
          <nav className="letter-nav">
            <button
              className={`letter-nav-item ${!selectedLetter ? 'is-active' : ''}`}
              onClick={() => setSelectedLetter(null)}
            >
              All
            </button>
            {LETTERS.map(letter => (
              <button
                key={letter}
                className={`letter-nav-item ${selectedLetter === letter ? 'is-active' : ''}`}
                onClick={() => setSelectedLetter(letter)}
              >
                {letter}
              </button>
            ))}
          </nav>

          <div className="library-toolbar">
            <SearchBar
              value={searchQuery}
              onChange={setSearchQuery}
              placeholder="Filter artists..."
            />
          </div>
        </>
      )}

      {/* Tracks View */}
      {viewMode === 'tracks' && !selectedArtist && (
        tracksLoading ? (
          <div className="loading-state">
            <p>Loading...</p>
          </div>
        ) : tracks.length === 0 ? (
          <div className="empty-state">
            <p className="text-muted">No tracks in your library. Heart individual tracks to add them here.</p>
          </div>
        ) : (
          <div className="track-list user-library-tracks">
            {tracks.map((track, index) => (
              <TrackRow
                key={track.id}
                track={track}
                onPlay={() => handlePlayTrack(track, index)}
                showAlbumInfo={true}
                onHeart={handleTrackHeart}
              />
            ))}
          </div>
        )
      )}

      {/* Albums View */}
      {viewMode === 'albums' && (
        isLoading ? (
          <div className="loading-state">
            <p>Loading...</p>
          </div>
        ) : selectedArtist ? (
          // Show albums for selected artist
          artistAlbums.length === 0 ? (
            <div className="empty-state">
              <p className="text-muted">No albums from this artist in your library</p>
            </div>
          ) : (
            <AlbumGrid
              albums={artistAlbums}
              onAlbumClick={handleAlbumClick}
              onAlbumDelete={() => refetch()}
            />
          )
        ) : filteredArtists.length === 0 ? (
          <div className="empty-state">
            <p className="text-muted">
              {searchQuery || selectedLetter
                ? 'No artists match your filter'
                : 'No albums in your library. Heart albums to add them here.'}
            </p>
          </div>
        ) : (
          // Show artists
          <ArtistGrid
            artists={filteredArtists}
            onArtistClick={handleArtistClick}
          />
        )
      )}

      {selectedAlbum && (
        <AlbumModal
          album={selectedAlbum}
          onClose={handleCloseModal}
        />
      )}
    </div>
  )
}

function BackIcon() {
  return (
    <svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" fill="none" strokeWidth="2">
      <polyline points="15 18 9 12 15 6" />
    </svg>
  )
}
