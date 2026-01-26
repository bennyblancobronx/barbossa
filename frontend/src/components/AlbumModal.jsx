import { useQuery } from 'react-query'
import * as api from '../services/api'
import { usePlayerStore } from '../stores/player'
import TrackRow from './TrackRow'

export default function AlbumModal({ album, onClose }) {
  const { data, isLoading } = useQuery(
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

  const artistName = data.artist?.name || data.artist_name || 'Unknown Artist'

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal modal-lg" onClick={e => e.stopPropagation()}>
        <button className="modal-close" onClick={onClose}>
          <CloseIcon />
        </button>

        <div className="album-detail">
          <div className="album-detail-header">
            <div className="album-detail-artwork">
              {data.artwork_path ? (
                <img src={`/api/albums/${data.id}/artwork`} alt={data.title} />
              ) : (
                <div className="artwork-placeholder-lg">
                  <span>{data.title[0]}</span>
                </div>
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
