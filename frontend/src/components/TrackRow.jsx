import { useState } from 'react'
import * as api from '../services/api'

export default function TrackRow({ track, onPlay, showAlbumInfo = false }) {
  const [isHearted, setIsHearted] = useState(track.is_hearted)
  const [isLoading, setIsLoading] = useState(false)
  const [isHovered, setIsHovered] = useState(false)

  const handleHeart = async (e) => {
    e.stopPropagation()
    setIsLoading(true)

    try {
      if (isHearted) {
        await api.unheartTrack(track.id)
        setIsHearted(false)
      } else {
        await api.heartTrack(track.id)
        setIsHearted(true)
      }
    } catch (error) {
      console.error('Heart track failed:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const handlePlay = (e) => {
    e.stopPropagation()
    if (onPlay) onPlay()
  }

  const formatDuration = (seconds) => {
    if (!seconds) return '--:--'
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  const getQualityLabel = () => {
    if (track.is_lossy) {
      return `${track.bitrate || '~256'}kbps`
    }
    return `${track.bit_depth || 16}/${Math.round((track.sample_rate || 44100) / 1000)}kHz`
  }

  const sourceLabels = {
    qobuz: 'Qobuz',
    lidarr: 'Lidarr',
    youtube: 'YT',
    import: 'Import'
  }

  return (
    <div
      className="track-row"
      onClick={onPlay}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <button
        className={`btn-icon track-heart ${isHearted ? 'is-active' : ''}`}
        onClick={handleHeart}
        disabled={isLoading}
      >
        <HeartIcon filled={isHearted} size={24} />
      </button>

      <button
        className={`btn-icon track-play ${isHovered ? 'is-visible' : ''}`}
        onClick={handlePlay}
        title="Play track"
      >
        <PlayIcon size={20} />
      </button>

      <span className="track-number">{track.track_number || '-'}</span>

      <div className="track-info">
        <span className="track-title">{track.title}</span>
        {showAlbumInfo && track.album?.title && (
          <span className="track-album">{track.album.title}</span>
        )}
      </div>

      {track.source && (
        <span className={`track-source badge badge-${track.source}`}>
          {sourceLabels[track.source] || track.source}
        </span>
      )}

      <span className={`track-quality ${track.is_lossy ? 'is-lossy' : ''}`}>
        {getQualityLabel()}
      </span>

      <span className="track-duration">{formatDuration(track.duration)}</span>
    </div>
  )
}

function HeartIcon({ filled, size = 20 }) {
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} stroke="currentColor" fill={filled ? 'currentColor' : 'none'} strokeWidth="2">
      <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
    </svg>
  )
}

function PlayIcon({ size = 16 }) {
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} fill="currentColor" stroke="none">
      <polygon points="5 3 19 12 5 21 5 3" />
    </svg>
  )
}
