import { useState } from 'react'
import { useQuery } from 'react-query'
import * as api from '../services/api'
import { useAuthStore } from '../stores/auth'
import AlbumGrid from '../components/AlbumGrid'
import AlbumModal from '../components/AlbumModal'
import SearchBar from '../components/SearchBar'

export default function UserLibrary() {
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedAlbum, setSelectedAlbum] = useState(null)
  const user = useAuthStore(state => state.user)

  const { data, isLoading, refetch } = useQuery(
    ['user-library', user?.id],
    () => api.getUserLibrary().then(r => r.data),
    { enabled: !!user?.id }
  )

  const albums = data?.items || data?.albums || []

  const filteredAlbums = searchQuery
    ? albums.filter(album =>
        album.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (album.artist?.name || album.artist_name || '').toLowerCase().includes(searchQuery.toLowerCase())
      )
    : albums

  const handleCloseModal = () => {
    setSelectedAlbum(null)
    refetch()
  }

  return (
    <div className="page-user-library">
      <header className="page-header">
        <h1 className="text-2xl">My Library</h1>
        <span className="text-muted">
          {albums.length || 0} albums
        </span>
      </header>

      <div className="library-toolbar">
        <SearchBar
          value={searchQuery}
          onChange={setSearchQuery}
          placeholder="Filter my library..."
        />
      </div>

      {isLoading ? (
        <div className="loading-state">
          <p>Loading...</p>
        </div>
      ) : filteredAlbums.length === 0 ? (
        <div className="empty-state">
          <p className="text-muted">
            {searchQuery
              ? 'No albums match your search'
              : 'No albums in your library. Heart albums to add them here.'}
          </p>
        </div>
      ) : (
        <AlbumGrid
          albums={filteredAlbums}
          onAlbumClick={setSelectedAlbum}
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
