import { useState } from 'react'
import { useQuery } from 'react-query'
import * as api from '../services/api'
import ArtistGrid from '../components/ArtistGrid'
import AlbumGrid from '../components/AlbumGrid'
import AlbumModal from '../components/AlbumModal'

const LETTERS = '#ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('')

export default function Library() {
  const [selectedLetter, setSelectedLetter] = useState(null)
  const [selectedArtist, setSelectedArtist] = useState(null)
  const [selectedAlbum, setSelectedAlbum] = useState(null)

  // Fetch artists when no artist is selected
  const { data: artists, isLoading: artistsLoading } = useQuery(
    ['artists', selectedLetter],
    () => api.getArtists({ letter: selectedLetter }).then(r => r.data.items || r.data || []),
    { enabled: !selectedArtist }
  )

  // Fetch albums when an artist is selected
  const { data: albums, isLoading: albumsLoading, refetch: refetchAlbums } = useQuery(
    ['artist-albums', selectedArtist?.id],
    () => api.getArtistAlbums(selectedArtist.id).then(r => r.data || []),
    { enabled: !!selectedArtist }
  )

  const handleArtistClick = (artist) => {
    setSelectedArtist(artist)
    setSelectedLetter(null) // Reset letter filter when drilling into artist
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
            <h1 className="text-2xl">Master Library</h1>
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
        <AlbumGrid
          albums={albums || []}
          onAlbumClick={handleAlbumClick}
          onAlbumDelete={() => refetchAlbums()}
        />
      ) : (
        // Show artists
        <ArtistGrid
          artists={artists || []}
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
