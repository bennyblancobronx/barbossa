import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from 'react-query'
import * as api from '../services/api'
import { useNotificationStore } from '../stores/notifications'

export default function QobuzArtist() {
  const { artistId } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { addNotification } = useNotificationStore()

  const [sortBy, setSortBy] = useState('year')
  const [explicitOnly, setExplicitOnly] = useState(false)

  const { data: artist, isLoading, error } = useQuery(
    ['qobuz-artist', artistId, sortBy, explicitOnly],
    () => api.getQobuzArtist(artistId, sortBy, explicitOnly).then(r => r.data),
    { enabled: !!artistId }
  )

  const downloadMutation = useMutation(
    (album) => api.downloadQobuz(album.url, 4, 'album'),
    {
      onSuccess: () => {
        addNotification({ type: 'success', message: 'Download started' })
        queryClient.invalidateQueries('downloads')
      },
      onError: (err) => {
        addNotification({
          type: 'error',
          message: err.response?.data?.detail || 'Download failed'
        })
      }
    }
  )

  if (isLoading) {
    return (
      <div className="page-qobuz-artist">
        <div className="loading-state">
          <div className="spinner" />
          <p>Loading artist...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="page-qobuz-artist">
        <div className="error-state">
          <p className="text-error">Failed to load artist</p>
          <p className="text-muted">{error.response?.data?.detail || 'Unknown error'}</p>
          <button className="btn-primary" onClick={() => navigate(-1)}>
            Go Back
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="page-qobuz-artist">
      {/* Breadcrumb Navigation */}
      <nav className="breadcrumbs">
        <button className="btn-ghost btn-sm" onClick={() => navigate(-1)}>
          Back
        </button>
        <span className="breadcrumb-sep">/</span>
        <span className="breadcrumb-current">Artist</span>
      </nav>

      {/* Artist Header */}
      <header className="artist-header">
        <div className="artist-image-large">
          {artist.image_url ? (
            <img
              src={artist.image_large || artist.image_url}
              alt={artist.name}
              onError={(e) => {
                e.target.onerror = null
                e.target.src = '/placeholder-artist.svg'
              }}
            />
          ) : (
            <img src="/placeholder-artist.svg" alt="" />
          )}
        </div>
        <div className="artist-details">
          <span className="label">Qobuz Artist</span>
          <h1>{artist.name}</h1>
          <p className="album-count">{artist.album_count} albums available</p>
        </div>
      </header>

      {/* Discography */}
      <section className="discography">
        <div className="section-header">
          <h2>Discography</h2>
          <div className="sort-options">
            <label>Sort by:</label>
            <select value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
              <option value="year">Year (newest first)</option>
              <option value="title">Title (A-Z)</option>
              <option value="popularity">Most Popular</option>
            </select>
            <label className="filter-toggle">
              <input
                type="checkbox"
                checked={explicitOnly}
                onChange={(e) => setExplicitOnly(e.target.checked)}
              />
              Explicit Only
            </label>
          </div>
        </div>

        <div className="albums-grid">
          {artist.albums?.map(album => (
            <div key={album.id} className="album-card">
              <div
                className="album-artwork"
                onClick={() => navigate(`/qobuz/album/${album.id}`)}
              >
                <img
                  src={album.artwork_url || '/placeholder-album.svg'}
                  alt={album.title}
                  onError={(e) => {
                    e.target.onerror = null
                    e.target.src = '/placeholder-album.svg'
                  }}
                />

                {album.hires && (
                  <span className="quality-badge hires">
                    {album.maximum_bit_depth}/{album.maximum_sampling_rate}
                  </span>
                )}

                {album.in_library && (
                  <span className="in-library-badge">In Library</span>
                )}
              </div>

              <div className="album-info">
                <h3
                  className="album-title clickable"
                  onClick={() => navigate(`/qobuz/album/${album.id}`)}
                >
                  {album.title}
                </h3>
                <p className="album-year">{album.year}</p>
                <p className="album-meta">{album.track_count} tracks</p>
              </div>

              <div className="album-actions">
                {album.in_library ? (
                  <button
                    className="btn-ghost btn-sm"
                    onClick={() => navigate(`/album/${album.local_album_id}`)}
                  >
                    View in Library
                  </button>
                ) : (
                  <button
                    className="btn-primary btn-sm"
                    onClick={(e) => {
                      e.stopPropagation()
                      downloadMutation.mutate(album)
                    }}
                    disabled={downloadMutation.isLoading}
                  >
                    Download
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>

        {(!artist.albums || artist.albums.length === 0) && (
          <div className="empty-state">
            <p className="text-muted">No albums found for this artist</p>
          </div>
        )}
      </section>

      {/* Biography (if available) */}
      {artist.biography && (
        <section className="biography">
          <h2>About</h2>
          <div
            className="biography-content"
            dangerouslySetInnerHTML={{ __html: artist.biography }}
          />
        </section>
      )}
    </div>
  )
}
