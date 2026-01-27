import { useState } from 'react'
import { useQuery } from 'react-query'
import * as api from '../services/api'
import { useAuthStore } from '../stores/auth'
import ArtistGrid from '../components/ArtistGrid'
import AlbumGrid from '../components/AlbumGrid'
import AlbumModal from '../components/AlbumModal'

const LETTERS = '#ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('')

export default function UserLibrary() {
  const [selectedLetter, setSelectedLetter] = useState(null)
  const [selectedArtist, setSelectedArtist] = useState(null)
  const [selectedAlbum, setSelectedAlbum] = useState(null)
  const user = useAuthStore(state => state.user)

  // Fetch artists when no artist is selected
  const { data: artists, isLoading: artistsLoading, refetch: refetchArtists } = useQuery(
    ['user-library-artists', user?.id, selectedLetter],
    () => api.getUserLibraryArtists({ letter: selectedLetter }).then(r => r.data.items || r.data || []),
    { enabled: !!user?.id && !selectedArtist }
  )

  // Fetch albums when an artist is selected
  const { data: albums, isLoading: albumsLoading, refetch: refetchAlbums } = useQuery(
    ['user-library-artist-albums', user?.id, selectedArtist?.id],
    () => api.getUserLibraryArtistAlbums(selectedArtist.id).then(r => r.data || []),
    { enabled: !!user?.id && !!selectedArtist }
  )

  const handleArtistClick = (artist) => {
    setSelectedArtist(artist)
    setSelectedLetter(null)
  }

  const handleBackToArtists = () => {
    setSelectedArtist(null)
  }

  const handleAlbumClick = (album) => {
    setSelectedAlbum(album)
  }

  const handleCloseModal = () => {
    setSelectedAlbum(null)
    if (selectedArtist) {
      refetchAlbums()
    }
    refetchArtists()
  }

  const handleArtistDelete = (artistId) => {
    // If we're viewing this artist's albums, go back to artist list
    if (selectedArtist?.id === artistId) {
      setSelectedArtist(null)
    }
    refetchArtists()
  }

  const handleAlbumDelete = (albumId) => {
    refetchAlbums()
    // If this was the last album, go back to artists
    if (albums && albums.length <= 1) {
      setSelectedArtist(null)
      refetchArtists()
    }
  }

  const isLoading = selectedArtist ? albumsLoading : artistsLoading

  return (
    <div className="page-library">
      <header className="page-header">
        <div className="page-header-content">
          {selectedArtist ? (
            <>
              <button className="btn-back" onClick={handleBackToArtists}>
                <BackIcon />
              </button>
              <h1 className="text-2xl">{selectedArtist.name}</h1>
              <span className="text-muted">{albums?.length || 0} albums</span>
            </>
          ) : (
            <h1 className="text-2xl">My Library</h1>
          )}
        </div>
      </header>

      {/* A-Z nav only shows when viewing artists */}
      {!selectedArtist && (
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
      )}

      {isLoading ? (
        <div className="loading-state">
          <p>Loading...</p>
        </div>
      ) : selectedArtist ? (
        // Show albums for selected artist
        albums?.length === 0 ? (
          <div className="empty-state">
            <p className="text-muted">No albums from this artist in your library</p>
          </div>
        ) : (
          <AlbumGrid
            albums={albums || []}
            onAlbumClick={handleAlbumClick}
            onAlbumDelete={handleAlbumDelete}
          />
        )
      ) : (artists?.length || 0) === 0 ? (
        <div className="empty-state">
          <p className="text-muted">
            {selectedLetter
              ? 'No artists match this letter'
              : 'Your library is empty. Heart albums to add them here.'}
          </p>
        </div>
      ) : (
        // Show artists
        <ArtistGrid
          artists={artists || []}
          onArtistClick={handleArtistClick}
          onArtistDelete={handleArtistDelete}
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
