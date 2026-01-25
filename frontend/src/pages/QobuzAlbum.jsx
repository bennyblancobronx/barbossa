import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from 'react-query'
import * as api from '../services/api'
import { useNotificationStore } from '../stores/notifications'

export default function QobuzAlbum() {
  const { albumId } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { addNotification } = useNotificationStore()

  const { data: album, isLoading, error } = useQuery(
    ['qobuz-album', albumId],
    () => api.getQobuzAlbum(albumId).then(r => r.data),
    { enabled: !!albumId }
  )

  const downloadMutation = useMutation(
    () => api.downloadQobuz(album.url, 4, 'album'),
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

  const formatDuration = (seconds) => {
    if (!seconds) return '0:00'
    const hours = Math.floor(seconds / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    const secs = Math.floor(seconds % 60)
    if (hours > 0) {
      return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
    }
    return `${minutes}:${secs.toString().padStart(2, '0')}`
  }

  if (isLoading) {
    return (
      <div className="page-qobuz-album">
        <div className="loading-state">
          <div className="spinner" />
          <p>Loading album...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="page-qobuz-album">
        <div className="error-state">
          <p className="text-error">Failed to load album</p>
          <p className="text-muted">{error.response?.data?.detail || 'Unknown error'}</p>
          <button className="btn-primary" onClick={() => navigate(-1)}>
            Go Back
          </button>
        </div>
      </div>
    )
  }

  // Calculate total duration
  const totalDuration = album.tracks?.reduce((sum, t) => sum + (t.duration || 0), 0) || 0

  // Group tracks by disc number for multi-disc albums
  const tracksByDisc = album.tracks?.reduce((acc, track) => {
    const disc = track.disc_number || 1
    if (!acc[disc]) acc[disc] = []
    acc[disc].push(track)
    return acc
  }, {}) || {}
  const discCount = Object.keys(tracksByDisc).length

  return (
    <div className="page-qobuz-album">
      {/* Breadcrumb Navigation */}
      <nav className="breadcrumbs">
        <button className="btn-ghost btn-sm" onClick={() => navigate(-1)}>
          Back
        </button>
        <span className="breadcrumb-sep">/</span>
        <span
          className="breadcrumb-link"
          onClick={() => navigate(`/qobuz/artist/${album.artist_id}`)}
        >
          {album.artist_name}
        </span>
        <span className="breadcrumb-sep">/</span>
        <span className="breadcrumb-current">{album.title}</span>
      </nav>

      {/* Album Header */}
      <header className="album-header">
        <div className="album-artwork-large">
          <img
            src={album.artwork_large || album.artwork_url || '/placeholder-album.svg'}
            alt={album.title}
            onError={(e) => {
              e.target.onerror = null
              e.target.src = '/placeholder-album.svg'
            }}
          />
        </div>

        <div className="album-details">
          <span className="label">Qobuz Album</span>
          <h1>{album.title}</h1>
          <p
            className="artist-link"
            onClick={() => navigate(`/qobuz/artist/${album.artist_id}`)}
          >
            {album.artist_name}
          </p>

          <div className="album-meta">
            <span>{album.year}</span>
            <span>{album.track_count} tracks</span>
            <span>{formatDuration(totalDuration)}</span>
          </div>

          {/* Genre and Label */}
          <div className="album-extra-meta">
            {album.genre && <span className="genre-tag">{album.genre}</span>}
            {album.label && <span className="label-tag">{album.label}</span>}
          </div>

          {/* Quality Badge */}
          <div className="quality-info">
            {album.hires ? (
              <span className="quality-badge hires">
                Hi-Res {album.maximum_bit_depth}-bit / {album.maximum_sampling_rate}kHz
              </span>
            ) : (
              <span className="quality-badge cd">
                CD Quality 16-bit / 44.1kHz
              </span>
            )}
          </div>

          {/* In Library Status or Download Button */}
          {album.in_library ? (
            <div className="in-library-notice">
              <span className="in-library-badge large">Already in Library</span>
              <button
                className="btn-secondary btn-large"
                onClick={() => navigate(`/album/${album.local_album_id}`)}
              >
                View in Library
              </button>
            </div>
          ) : (
            <button
              className="btn-primary btn-large"
              onClick={() => downloadMutation.mutate()}
              disabled={downloadMutation.isLoading}
            >
              {downloadMutation.isLoading ? 'Starting...' : 'Download Album'}
            </button>
          )}
        </div>
      </header>

      {/* Track Listing */}
      <section className="track-listing">
        <h2>Tracks</h2>

        {/* Multi-disc handling */}
        {discCount > 1 ? (
          Object.entries(tracksByDisc).map(([discNum, tracks]) => (
            <div key={discNum} className="disc-section">
              <h3 className="disc-header">Disc {discNum}</h3>
              <table className="tracks-table">
                <thead>
                  <tr>
                    <th className="col-num">#</th>
                    <th className="col-title">Title</th>
                    <th className="col-duration">Duration</th>
                    <th className="col-quality">Quality</th>
                  </tr>
                </thead>
                <tbody>
                  {tracks.map(track => (
                    <tr key={track.id}>
                      <td className="col-num">{track.track_number}</td>
                      <td className="col-title">{track.title}</td>
                      <td className="col-duration">{formatDuration(track.duration)}</td>
                      <td className="col-quality">
                        {track.hires ? (
                          <span className="quality-indicator hires">Hi-Res</span>
                        ) : (
                          <span className="quality-indicator cd">CD</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))
        ) : (
          <table className="tracks-table">
            <thead>
              <tr>
                <th className="col-num">#</th>
                <th className="col-title">Title</th>
                <th className="col-duration">Duration</th>
                <th className="col-quality">Quality</th>
              </tr>
            </thead>
            <tbody>
              {album.tracks?.map(track => (
                <tr key={track.id}>
                  <td className="col-num">{track.track_number}</td>
                  <td className="col-title">{track.title}</td>
                  <td className="col-duration">{formatDuration(track.duration)}</td>
                  <td className="col-quality">
                    {track.hires ? (
                      <span className="quality-indicator hires">Hi-Res</span>
                    ) : (
                      <span className="quality-indicator cd">CD</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {(!album.tracks || album.tracks.length === 0) && (
          <div className="empty-state">
            <p className="text-muted">No tracks found for this album</p>
          </div>
        )}
      </section>
    </div>
  )
}
