import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useQuery } from 'react-query'
import * as api from '../services/api'
import AlbumGrid from '../components/AlbumGrid'
import AlbumModal from '../components/AlbumModal'

const LETTERS = '#ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('')

export default function Library() {
  const [searchParams] = useSearchParams()
  const searchQuery = searchParams.get('q') || ''
  const [selectedLetter, setSelectedLetter] = useState(null)
  const [selectedAlbum, setSelectedAlbum] = useState(null)

  const { data: albums, isLoading, refetch } = useQuery(
    ['albums', selectedLetter, searchQuery],
    () => {
      if (searchQuery) {
        return api.searchLibrary(searchQuery, 'album').then(r => r.data.albums || r.data.items || [])
      }
      return api.getAlbums({ letter: selectedLetter }).then(r => r.data.items || r.data || [])
    }
  )

  const handleAlbumClick = (album) => {
    setSelectedAlbum(album)
  }

  const handleCloseModal = () => {
    setSelectedAlbum(null)
    refetch()
  }

  return (
    <div className="page-library">
      <header className="page-header">
        <h1 className="text-2xl">Master Library</h1>
        {searchQuery && (
          <span className="text-muted">Results for "{searchQuery}"</span>
        )}
      </header>

      {!searchQuery && (
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
      ) : (
        <AlbumGrid
          albums={albums || []}
          onAlbumClick={handleAlbumClick}
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
