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
  const [showFallbackModal, setShowFallbackModal] = useState(false)
  const [modalContext, setModalContext] = useState(null) // 'local' | 'empty'

  const queryClient = useQueryClient()
  const { addNotification } = useNotificationStore()

  // Reset state when query/type changes
  useEffect(() => {
    setShowFallbackModal(false)
    setModalContext(null)
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

  // Compute local results state (must be before Qobuz query for enabled condition)
  const hasLocalResults = localResults && (
    (localResults.albums?.length > 0) ||
    (localResults.artists?.length > 0) ||
    (localResults.tracks?.length > 0)
  )

  // External search (Qobuz) - auto-cascade when local is empty
  // Uses new searchQobuzCatalog endpoint with artwork URLs
  const {
    data: qobuzResults,
    isLoading: qobuzLoading,
    error: qobuzError,
    refetch: searchQobuz
  } = useQuery(
    ['search-qobuz', query, type],
    () => api.searchQobuzCatalog(query, type).then(r => r.data),
    {
      // Auto-trigger when local search completes with no results
      enabled: !!query && !localLoading && !hasLocalResults,
      retry: 1
    }
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

  const hasQobuzResults = qobuzResults && (
    (qobuzResults.albums?.length > 0) ||
    (qobuzResults.artists?.length > 0) ||
    (qobuzResults.tracks?.length > 0)
  )

  // Show fallback when: both empty OR Qobuz errored out
  const qobuzFailed = qobuzError && !qobuzLoading
  const shouldShowFallback = !localLoading && !qobuzLoading &&
    !hasLocalResults && (!hasQobuzResults || qobuzFailed) && query

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
          {/* Search More Button - shown when local results exist */}
          <div className="search-more-section">
            <button
              className="btn-secondary"
              onClick={() => {
                setModalContext('local')
                setShowFallbackModal(true)
              }}
            >
              Search more sources (Qobuz, Lidarr, YouTube)
            </button>
          </div>
        </section>
      )}

      {/* Qobuz Loading state when triggered from modal with local results */}
      {hasLocalResults && qobuzLoading && (
        <section className="search-section">
          <div className="section-header">
            <h2 className="section-title">Qobuz Results</h2>
          </div>
          <div className="loading-state">
            <div className="spinner" />
            <p>Searching Qobuz...</p>
          </div>
        </section>
      )}

      {/* Qobuz Results alongside local (when user manually triggered from modal) */}
      {hasLocalResults && !qobuzLoading && hasQobuzResults && (
        <section className="search-section">
          <div className="section-header">
            <h2 className="section-title">Qobuz Results</h2>
            <span className="text-muted text-sm">Higher quality available</span>
          </div>

          {type === 'album' && qobuzResults.albums?.length > 0 && (
            <div className="qobuz-results-grid">
              {qobuzResults.albums.map(album => (
                <div key={album.id} className="qobuz-album-card">
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
                    {album.hires && (
                      <span className="quality-badge hires">
                        {album.maximum_bit_depth}/{album.maximum_sampling_rate}
                      </span>
                    )}
                    {album.in_library && (
                      <span className="in-library-badge" title="Already in your library">
                        In Library
                      </span>
                    )}
                  </div>
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

          {type === 'artist' && qobuzResults.artists?.length > 0 && (
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

          {type === 'track' && qobuzResults.tracks?.length > 0 && (
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
        </section>
      )}

      {/* Auto-cascade: Show search progress when local is empty */}
      {!localLoading && !hasLocalResults && (
        <>
          {/* Loading Sequence Feedback */}
          {qobuzLoading && (
            <div className="loading-state">
              <div className="spinner" />
              <div className="search-progress">
                <p className="search-progress-done">No results in library</p>
                <p className="search-progress-active">Searching Qobuz...</p>
              </div>
            </div>
          )}

          {/* Qobuz Results */}
          {!qobuzLoading && !qobuzError && hasQobuzResults && (
            <section className="search-section">
              <div className="section-header">
                <h2 className="section-title">Qobuz Results</h2>
                <span className="text-muted text-sm">Not in your library</span>
              </div>

              {/* Album Results Grid */}
              {type === 'album' && qobuzResults.albums?.length > 0 && (
                <div className="qobuz-results-grid">
                  {qobuzResults.albums.map(album => (
                    <div key={album.id} className="qobuz-album-card">
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
                        {album.hires && (
                          <span className="quality-badge hires">
                            {album.maximum_bit_depth}/{album.maximum_sampling_rate}
                          </span>
                        )}
                        {album.in_library && (
                          <span className="in-library-badge" title="Already in your library">
                            In Library
                          </span>
                        )}
                      </div>
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
              {type === 'artist' && qobuzResults.artists?.length > 0 && (
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
              {type === 'track' && qobuzResults.tracks?.length > 0 && (
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

              {/* Search More at bottom of Qobuz results */}
              <div className="search-more-section">
                <button
                  className="btn-secondary"
                  onClick={() => {
                    setModalContext('empty')
                    setShowFallbackModal(true)
                  }}
                >
                  Try other sources (Lidarr, YouTube)
                </button>
              </div>
            </section>
          )}

          {/* Qobuz Error - Show fallback options */}
          {!qobuzLoading && qobuzError && (
            <div className="empty-state">
              <div className="search-exhausted">
                <p className="search-progress-done">No results in library</p>
                <p className="text-warning">Qobuz search failed</p>
              </div>
              <div className="error-actions">
                <button className="btn-secondary" onClick={() => searchQobuz()}>
                  Retry Qobuz
                </button>
                <button
                  className="btn-primary"
                  onClick={() => {
                    setModalContext('empty')
                    setShowFallbackModal(true)
                  }}
                >
                  Try other sources
                </button>
              </div>
            </div>
          )}

          {/* No results anywhere - detailed messaging */}
          {shouldShowFallback && !qobuzError && !showFallbackModal && (
            <div className="empty-state">
              <div className="search-exhausted">
                <p className="search-progress-done">No results in library</p>
                <p className="search-progress-done">No results on Qobuz</p>
              </div>
              <button
                className="btn-primary"
                onClick={() => {
                  setModalContext('empty')
                  setShowFallbackModal(true)
                }}
              >
                Try other sources
              </button>
            </div>
          )}
        </>
      )}

      {/* Fallback Modal - All External Sources */}
      {showFallbackModal && (
        <div className="modal-backdrop" onClick={() => setShowFallbackModal(false)}>
          <div className="modal modal-sm" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h2 className="modal-title">Search Other Sources</h2>
              <button
                className="modal-close"
                onClick={() => setShowFallbackModal(false)}
              >
                <svg viewBox="0 0 24 24" width="20" height="20" stroke="currentColor" fill="none" strokeWidth="2">
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>
            <div className="modal-body">
              <p className="text-muted">"{query}" - try alternative sources</p>

              <div className="fallback-options">
                {/* Show Qobuz option if user has local results (quality upgrade) */}
                {modalContext === 'local' && (
                  <button
                    className="btn-primary fallback-option"
                    onClick={() => {
                      setShowFallbackModal(false)
                      searchQobuz()
                    }}
                  >
                    <span>Search Qobuz</span>
                    <span className="text-sm text-muted">Find higher quality (24/192)</span>
                  </button>
                )}

                <button
                  className="btn-secondary fallback-option"
                  onClick={() => {
                    setShowFallbackModal(false)
                    navigate('/downloads')
                  }}
                >
                  <span>Request via Lidarr</span>
                  <span className="text-sm text-muted">Automated monitoring</span>
                </button>

                <button
                  className="btn-secondary fallback-option"
                  onClick={() => {
                    setShowFallbackModal(false)
                    navigate(`/downloads?url=https://music.youtube.com/search?q=${encodeURIComponent(query)}`)
                  }}
                >
                  <span>Search YouTube</span>
                  <span className="text-sm text-warning">Lossy source (~256kbps)</span>
                </button>

                <button
                  className="btn-ghost fallback-option"
                  onClick={() => {
                    setShowFallbackModal(false)
                    navigate('/downloads')
                  }}
                >
                  <span>Paste URL</span>
                  <span className="text-sm text-muted">Bandcamp, Soundcloud, etc</span>
                </button>
              </div>
            </div>
          </div>
        </div>
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
