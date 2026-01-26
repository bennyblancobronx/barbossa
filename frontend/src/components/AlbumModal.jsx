import { useRef, useState } from 'react'
import { useQuery } from 'react-query'
import * as api from '../services/api'
import { usePlayerStore } from '../stores/player'
import TrackRow from './TrackRow'

export default function AlbumModal({ album, onClose }) {
  const [imageKey, setImageKey] = useState(0)
  const [isArtworkHovered, setIsArtworkHovered] = useState(false)
  const fileInputRef = useRef(null)

  const { data, isLoading, refetch } = useQuery(
    ['album', album.id],
    () => api.getAlbum(album.id).then(r => r.data),
    {
      initialData: album,
      staleTime: 0,  // Always refetch to get tracks
    }
  )

  const play = usePlayerStore(state => state.play)

  const handlePlayAll = () => {
    if (data.tracks?.length) {
      play(data.tracks[0], data.tracks)
    }
  }

  const handlePlayTrack = (track) => {
    play(track, data.tracks)
  }

  const handleEditArtwork = () => {
    fileInputRef.current?.click()
  }

  const handleFileChange = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return

    try {
      await api.uploadArtwork(data.id, file)
      setImageKey(prev => prev + 1)
      refetch()
    } catch (error) {
      console.error('Artwork upload failed:', error)
    }
    e.target.value = ''
  }

  const artistName = data.artist?.name || data.artist_name || 'Unknown Artist'

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal modal-lg" onClick={e => e.stopPropagation()}>
        <button className="modal-close" onClick={onClose}>
          <CloseIcon />
        </button>

        <div className="album-detail">
          <div className="album-detail-header">
            <div
              className="album-detail-artwork"
              style={{ position: 'relative' }}
              onMouseEnter={() => setIsArtworkHovered(true)}
              onMouseLeave={() => setIsArtworkHovered(false)}
            >
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleFileChange}
                accept="image/jpeg,image/png"
                style={{ display: 'none' }}
              />
              {data.artwork_path || imageKey > 0 ? (
                <img
                  key={imageKey}
                  src={`/api/albums/${data.id}/artwork?v=${imageKey}`}
                  alt={data.title}
                  onClick={handleEditArtwork}
                  style={{ cursor: 'pointer' }}
                />
              ) : (
                <div
                  className="artwork-placeholder-lg"
                  onClick={handleEditArtwork}
                  style={{ cursor: 'pointer' }}
                >
                  <span>{data.title[0]}</span>
                </div>
              )}
              {isArtworkHovered && (
                <button
                  className="btn-icon edit-btn"
                  onClick={handleEditArtwork}
                  title="Edit artwork"
                  style={{
                    position: 'absolute',
                    bottom: '8px',
                    right: '8px',
                    background: 'rgba(0,0,0,0.7)',
                    borderRadius: '4px',
                    padding: '6px'
                  }}
                >
                  <PencilIcon />
                </button>
              )}
            </div>

            <div className="album-detail-info">
              <h2 className="text-2xl">{data.title}</h2>
              <p className="text-lg text-secondary">{artistName}</p>

              <div className="album-detail-meta">
                {data.year && <span>{data.year}</span>}
                {data.genre && <span>{data.genre}</span>}
                <span>{data.available_tracks || data.tracks?.length || 0} tracks</span>
              </div>

              <div className="album-detail-quality">
                <QualityBadge track={data.tracks?.[0]} />
              </div>

              <div className="album-detail-actions">
                <button className="btn-primary" onClick={handlePlayAll}>
                  Play All
                </button>
              </div>
            </div>
          </div>

          <div className="album-detail-tracks">
            {isLoading ? (
              <p className="text-muted">Loading...</p>
            ) : (
              <div className="track-list">
                {data.tracks?.map(track => (
                  <TrackRow
                    key={track.id}
                    track={track}
                    onPlay={() => handlePlayTrack(track)}
                  />
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

function QualityBadge({ track }) {
  if (!track) return null

  const quality = track.is_lossy
    ? `${track.bitrate || '~256'}kbps ${track.format || ''}`
    : `${track.bit_depth || 16}/${(track.sample_rate || 44100) / 1000}kHz ${track.format || 'FLAC'}`

  return <span className="badge">{quality}</span>
}

function CloseIcon() {
  return (
    <svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" fill="none" strokeWidth="2">
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  )
}

function PencilIcon() {
  return (
    <svg viewBox="0 0 24 24" width="20" height="20" stroke="currentColor" fill="none" strokeWidth="2">
      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
      <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
    </svg>
  )
}
