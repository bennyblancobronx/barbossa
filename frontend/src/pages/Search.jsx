import { useState, useEffect } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from 'react-query'
import * as api from '../services/api'
import AlbumGrid from '../components/AlbumGrid'
import AlbumModal from '../components/AlbumModal'
import { useNotificationStore } from '../stores/notifications'

export default function Search() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const query = searchParams.get('q') || ''
  const type = searchParams.get('type') || 'album'

  const [selectedAlbum, setSelectedAlbum] = useState(null)
  const [showExternal, setShowExternal] = useState(false)
  const [externalSource, setExternalSource] = useState(null)

  const queryClient = useQueryClient()
  const { addNotification } = useNotificationStore()

  // Reset external state when query/type changes
  useEffect(() => {
    setShowExternal(false)
    setExternalSource(null)
  }, [query, type])

  // Local search
  const {
    data: localResults,
    isLoading: localLoading,
    error: localError,
    refetch: retryLocal
  } = useQuery(
    ['search-local', query, type],
    () => api.searchLibrary(query, type).then(r => r.data),
    {
      enabled: !!query,
      retry: 1
    }
  )

  // External search (Qobuz) - only when triggered
  // Uses new searchQobuzCatalog endpoint with artwork URLs
  const {
    data: qobuzResults,
    isLoading: qobuzLoading,
    error: qobuzError,
    refetch: searchQobuz
  } = useQuery(
    ['search-qobuz', query, type],
    () => api.searchQobuzCatalog(query, type).then(r => r.data),
    { enabled: false, retry: 1 }
  )

  // Download mutation
  const downloadMutation = useMutation(
    ({ url, source }) => {
      if (source === 'qobuz') {
        return api.downloadQobuz(url, 4, type)
      }
      return api.downloadUrl(url, false, type)
    },
    {
      onSuccess: () => {
        addNotification({ type: 'success', message: 'Download started' })
        queryClient.invalidateQueries('downloads')
      },
      onError: (error) => {
        const message = error.response?.data?.detail || 'Download failed'
        if (message.includes('lossy')) {
          addNotification({
            type: 'warning',
            message: 'This is a lossy source. Go to Downloads page to confirm.'
          })
          navigate('/downloads')
        } else {
          addNotification({ type: 'error', message })
        }
      }
    }
  )

  const hasLocalResults = localResults && (
    (localResults.albums?.length > 0) ||
    (localResults.artists?.length > 0) ||
    (localResults.tracks?.length > 0)
  )

  const handleSearchExternal = (source) => {
    setShowExternal(true)
    setExternalSource(source)
    if (source === 'qobuz') {
      searchQobuz()
    }
  }

  // No query state
  if (!query) {
    return (
      <div className="page-search">
        <div className="empty-state">
          <p className="text-muted">Enter a search term in the sidebar</p>
          <p className="text-sm text-muted">Press Enter to search</p>
        </div>
      </div>
    )
  }

  // Error state
  if (localError) {
    return (
      <div className="page-search">
        <div className="error-state">
          <p className="text-error">Search failed</p>
          <button className="btn-primary" onClick={() => retryLocal()}>
            Retry
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="page-search">
      <header className="page-header">
        <h1 className="text-2xl">Search Results</h1>
        <span className="text-muted">for "{query}" ({type}s)</span>
      </header>

      {/* Loading State */}
      {localLoading && (
        <div className="loading-state">
          <div className="spinner" />
          <p>Searching library...</p>
        </div>
      )}

      {/* Local Results */}
      {!localLoading && hasLocalResults && (
        <section className="search-section">
          <h2 className="section-title">In Your Library</h2>
          {type === 'album' && localResults.albums?.length > 0 && (
            <AlbumGrid
              albums={localResults.albums}
              onAlbumClick={setSelectedAlbum}
            />
          )}
          {type === 'artist' && localResults.artists?.length > 0 && (
            <div className="artist-list">
              {localResults.artists.map(artist => (
                <div
                  key={artist.id}
                  className="artist-item"
                  onClick={() => navigate(`/artist/${artist.id}`)}
                >
                  <span className="artist-name">{artist.name}</span>
                  <span className="text-muted">{artist.album_count || 0} albums</span>
                </div>
              ))}
            </div>
          )}
          {type === 'track' && localResults.tracks?.length > 0 && (
            <div className="track-list">
              {localResults.tracks.map(track => (
                <div key={track.id} className="track-item">
                  <span className="track-title">{track.title}</span>
                  <span className="track-artist text-muted">{track.artist_name}</span>
                  <span className="track-album text-muted">{track.album_title}</span>
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      {/* No Local Results - Show External Options */}
      {!localLoading && !hasLocalResults && !showExternal && (
        <section className="search-not-found">
          <div className="not-found-card">
            <p className="text-lg">"{query}" not found in your library</p>
            <p className="text-muted">Search externally:</p>

            <div className="external-options">
              <button
                className="btn-primary external-option"
                onClick={() => handleSearchExternal('qobuz')}
              >
                <span>Search Qobuz</span>
                <span className="text-sm text-muted">24/192 max</span>
              </button>

              <button
                className="btn-secondary external-option"
                onClick={() => navigate('/downloads')}
              >
                <span>Request via Lidarr</span>
                <span className="text-sm text-muted">automated</span>
              </button>

              <button
                className="btn-secondary external-option"
                onClick={() => handleSearchExternal('youtube')}
              >
                <span>Search YouTube</span>
                <span className="text-sm text-warning">lossy source</span>
              </button>

              <button
                className="btn-ghost external-option"
                onClick={() => navigate('/downloads')}
              >
                <span>Paste URL</span>
                <span className="text-sm text-muted">Bandcamp, Soundcloud, etc</span>
              </button>
            </div>
          </div>
        </section>
      )}

      {/* External Results (Qobuz) - Updated with artwork grid */}
      {showExternal && externalSource === 'qobuz' && (
        <section className="search-section">
          <div className="section-header">
            <h2 className="section-title">Qobuz Results</h2>
            <button
              className="btn-ghost text-sm"
              onClick={() => setShowExternal(false)}
            >
              Back to options
            </button>
          </div>

          {qobuzLoading && (
            <div className="loading-state">
              <div className="spinner" />
              <p>Searching Qobuz...</p>
            </div>
          )}

          {/* Qobuz Error State */}
          {!qobuzLoading && qobuzError && (
            <div className="error-state">
              <p className="text-error">
                {qobuzError.response?.data?.detail || 'Qobuz search failed'}
              </p>
              <div className="error-actions">
                <button className="btn-primary" onClick={() => searchQobuz()}>
                  Retry
                </button>
                <button className="btn-ghost" onClick={() => setShowExternal(false)}>
                  Back to options
                </button>
              </div>
            </div>
          )}

          {/* Album Results Grid */}
          {!qobuzLoading && qobuzResults?.albums?.length > 0 && (
            <div className="qobuz-results-grid">
              {qobuzResults.albums.map(album => (
                <div key={album.id} className="qobuz-album-card">
                  {/* Album Artwork */}
                  <div className="qobuz-album-artwork">
                    <img
                      src={album.artwork_url || '/placeholder-album.svg'}
                      alt={album.title}
                      loading="lazy"
                      onError={(e) => {
                        e.target.onerror = null
                        e.target.src = '/placeholder-album.svg'
                      }}
                    />

                    {/* Quality Badge */}
                    {album.hires && (
                      <span className="quality-badge hires">
                        {album.maximum_bit_depth}/{album.maximum_sampling_rate}
                      </span>
                    )}

                    {/* In Library Badge */}
                    {album.in_library && (
                      <span className="in-library-badge" title="Already in your library">
                        In Library
                      </span>
                    )}
                  </div>

                  {/* Album Info */}
                  <div className="qobuz-album-info">
                    <h3 className="album-title">{album.title}</h3>
                    <p className="album-artist">
                      <a
                        href="#"
                        onClick={(e) => {
                          e.preventDefault()
                          navigate(`/qobuz/artist/${album.artist_id}`)
                        }}
                      >
                        {album.artist_name}
                      </a>
                    </p>
                    <p className="album-meta">
                      {album.year} | {album.track_count} tracks
                    </p>
                  </div>

                  {/* Actions */}
                  <div className="qobuz-album-actions">
                    <button
                      className="btn-secondary"
                      onClick={() => navigate(`/qobuz/album/${album.id}`)}
                    >
                      View Tracks
                    </button>
                    {album.in_library ? (
                      <button
                        className="btn-ghost"
                        onClick={() => navigate(`/album/${album.local_album_id}`)}
                      >
                        View in Library
                      </button>
                    ) : (
                      <button
                        className="btn-primary"
                        onClick={() => downloadMutation.mutate({
                          url: album.url,
                          source: 'qobuz'
                        })}
                        disabled={downloadMutation.isLoading}
                      >
                        Download
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Artist Results */}
          {!qobuzLoading && qobuzResults?.artists?.length > 0 && (
            <div className="qobuz-artists-list">
              {qobuzResults.artists.map(artist => (
                <div
                  key={artist.id}
                  className="qobuz-artist-card"
                  onClick={() => navigate(`/qobuz/artist/${artist.id}`)}
                >
                  <div className="artist-image">
                    {artist.image_url ? (
                      <img
                        src={artist.image_url}
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
                  <div className="artist-info">
                    <h3>{artist.name}</h3>
                    <p>{artist.album_count} albums</p>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Track Results */}
          {!qobuzLoading && qobuzResults?.tracks?.length > 0 && (
            <div className="qobuz-tracks-list">
              {qobuzResults.tracks.map(track => (
                <div key={track.id} className="qobuz-track-item">
                  <div className="track-artwork">
                    <img
                      src={track.album_artwork || '/placeholder-album.svg'}
                      alt=""
                      onError={(e) => {
                        e.target.onerror = null
                        e.target.src = '/placeholder-album.svg'
                      }}
                    />
                  </div>
                  <div className="track-info">
                    <span className="track-title">{track.title}</span>
                    <span className="track-artist">{track.artist_name}</span>
                    <span className="track-album">{track.album_title}</span>
                  </div>
                  {track.hires && (
                    <span className="quality-badge-sm hires">Hi-Res</span>
                  )}
                  <button
                    className="btn-secondary btn-sm"
                    onClick={() => navigate(`/qobuz/album/${track.album_id}`)}
                  >
                    View Album
                  </button>
                </div>
              ))}
            </div>
          )}

          {!qobuzLoading && qobuzResults?.count === 0 && (
            <div className="empty-state">
              <p className="text-muted">No results found on Qobuz</p>
              <button
                className="btn-ghost"
                onClick={() => setShowExternal(false)}
              >
                Try other sources
              </button>
            </div>
          )}
        </section>
      )}

      {/* YouTube redirect notice */}
      {showExternal && externalSource === 'youtube' && (
        <section className="search-section">
          <div className="lossy-warning-card">
            <p className="text-warning">YouTube downloads are lossy (~256kbps max)</p>
            <p className="text-muted">
              Use only for content unavailable on Qobuz or Lidarr.
            </p>
            <button
              className="btn-primary"
              onClick={() => {
                navigate(`/downloads?url=https://music.youtube.com/search?q=${encodeURIComponent(query)}`)
              }}
            >
              Continue to Downloads
            </button>
            <button
              className="btn-ghost"
              onClick={() => setShowExternal(false)}
            >
              Back
            </button>
          </div>
        </section>
      )}

      {selectedAlbum && (
        <AlbumModal
          album={selectedAlbum}
          onClose={() => setSelectedAlbum(null)}
        />
      )}
    </div>
  )
}
