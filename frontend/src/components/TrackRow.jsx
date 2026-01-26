import { useState, useEffect } from 'react'
import { useQueryClient } from 'react-query'
import * as api from '../services/api'
import { usePlayerStore } from '../stores/player'

export default function TrackRow({ track, onPlay, showAlbumInfo = false, onHeart }) {
  const [isHearted, setIsHearted] = useState(track.is_hearted)
  const [isLoading, setIsLoading] = useState(false)

  // Sync local state when prop changes (e.g., after refetch)
  useEffect(() => {
    setIsHearted(track.is_hearted)
  }, [track.is_hearted, track.id])
  const queryClient = useQueryClient()

  const { currentTrack, isPlaying, pause, resume } = usePlayerStore()
  const isCurrentTrack = currentTrack?.id === track.id
  const isThisPlaying = isCurrentTrack && isPlaying

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
      // Invalidate ALL library caches so all pages update
      queryClient.invalidateQueries('user-library')
      queryClient.invalidateQueries('user-library-tracks')
      queryClient.invalidateQueries('artists')
      queryClient.invalidateQueries('artist-albums')
      queryClient.invalidateQueries('albums')
      queryClient.invalidateQueries('search-local')
      // Also invalidate album queries so track heart state updates in album views
      if (track.album_id) {
        queryClient.invalidateQueries(['album', track.album_id])
      }
      if (onHeart) onHeart(track.id, !isHearted)
    } catch (error) {
      console.error('Heart track failed:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const handlePlayPause = (e) => {
    e.stopPropagation()
    if (isCurrentTrack) {
      if (isPlaying) {
        pause()
      } else {
        resume()
      }
    } else {
      if (onPlay) onPlay()
    }
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
      className={`track-row ${isCurrentTrack ? 'is-playing' : ''}`}
      onClick={onPlay}
    >
      <button
        className={`track-heart ${isHearted ? 'is-active' : ''}`}
        onClick={handleHeart}
        disabled={isLoading}
        title={isHearted ? 'Remove from library' : 'Add to library'}
      >
        <HeartIcon filled={isHearted} size={32} />
      </button>

      <button
        className={`track-play ${isThisPlaying ? 'is-playing' : ''}`}
        onClick={handlePlayPause}
        title={isThisPlaying ? 'Pause' : 'Play'}
      >
        {isThisPlaying ? <PauseIcon size={32} /> : <PlayIcon size={32} />}
      </button>

      <span className="track-number">{track.track_number || '-'}</span>

      <div className="track-info">
        <span className="track-title">{track.title}</span>
        {showAlbumInfo && (track.album?.title || track.album_title) && (
          <span className="track-album">
            {track.artist_name && `${track.artist_name} - `}
            {track.album?.title || track.album_title}
          </span>
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

function HeartIcon({ filled, size = 32 }) {
  // Braun spec: xl (32px) = 2.5px stroke, lg (24px) = 2px stroke
  const strokeWidth = size >= 32 ? 2.5 : 2
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} stroke="currentColor" fill={filled ? 'currentColor' : 'none'} strokeWidth={strokeWidth}>
      <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
    </svg>
  )
}

function PlayIcon({ size = 24 }) {
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} fill="currentColor" stroke="none">
      <polygon points="5 3 19 12 5 21 5 3" />
    </svg>
  )
}

function PauseIcon({ size = 24 }) {
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} fill="currentColor" stroke="none">
      <rect x="6" y="4" width="4" height="16" />
      <rect x="14" y="4" width="4" height="16" />
    </svg>
  )
}
