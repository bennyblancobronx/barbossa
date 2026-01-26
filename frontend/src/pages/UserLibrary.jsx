import { useState, useMemo } from 'react'
import { useQuery } from 'react-query'
import * as api from '../services/api'
import { useAuthStore } from '../stores/auth'
import ArtistGrid from '../components/ArtistGrid'
import AlbumGrid from '../components/AlbumGrid'
import AlbumModal from '../components/AlbumModal'
import SearchBar from '../components/SearchBar'

const LETTERS = '#ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('')

export default function UserLibrary() {
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedLetter, setSelectedLetter] = useState(null)
  const [selectedArtist, setSelectedArtist] = useState(null)
  const [selectedAlbum, setSelectedAlbum] = useState(null)
  const user = useAuthStore(state => state.user)

  const { data, isLoading, refetch } = useQuery(
    ['user-library', user?.id],
    () => api.getUserLibrary().then(r => r.data),
    { enabled: !!user?.id }
  )

  const albums = data?.items || data?.albums || []

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
              <span className="text-muted">{artists.length} artists</span>
            </>
          )}
        </div>
      </header>

      {/* A-Z nav and search only when viewing artists */}
      {!selectedArtist && (
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

      {isLoading ? (
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
