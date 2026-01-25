import { useEffect, useRef } from 'react'
import { usePlayerStore } from '../stores/player'

export default function Player() {
  const audioRef = useRef(null)
  const {
    currentTrack,
    isPlaying,
    volume,
    progress,
    duration,
    toggle,
    next,
    previous,
    setProgress,
    setDuration,
    clearTrack
  } = usePlayerStore()

  useEffect(() => {
    if (!audioRef.current || !currentTrack) return

    const audio = audioRef.current
    audio.src = `/api/tracks/${currentTrack.id}/stream`

    if (isPlaying) {
      audio.play().catch(console.error)
    }
  }, [currentTrack])

  useEffect(() => {
    if (!audioRef.current) return

    if (isPlaying) {
      audioRef.current.play().catch(console.error)
    } else {
      audioRef.current.pause()
    }
  }, [isPlaying])

  useEffect(() => {
    if (audioRef.current) {
      audioRef.current.volume = volume
    }
  }, [volume])

  const handleTimeUpdate = () => {
    if (audioRef.current) {
      setProgress(audioRef.current.currentTime)
    }
  }

  const handleLoadedMetadata = () => {
    if (audioRef.current) {
      setDuration(audioRef.current.duration)
    }
  }

  const handleSeek = (e) => {
    const rect = e.currentTarget.getBoundingClientRect()
    const percent = (e.clientX - rect.left) / rect.width
    const newTime = percent * duration

    if (audioRef.current) {
      audioRef.current.currentTime = newTime
      setProgress(newTime)
    }
  }

  const formatTime = (seconds) => {
    if (!seconds || isNaN(seconds)) return '0:00'
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  if (!currentTrack) return null

  const artistName = currentTrack.album?.artist?.name || currentTrack.artist_name || ''

  return (
    <div className="player-bar">
      <audio
        ref={audioRef}
        onTimeUpdate={handleTimeUpdate}
        onLoadedMetadata={handleLoadedMetadata}
        onEnded={next}
      />

      <div className="player-track-info">
        <span className="player-title">{currentTrack.title}</span>
        <span className="player-artist">{artistName}</span>
      </div>

      <div className="player-controls">
        <button className="btn-icon" onClick={previous}>
          <PreviousIcon />
        </button>

        <button className="btn-icon player-play-btn" onClick={toggle}>
          {isPlaying ? <PauseIcon /> : <PlayIcon />}
        </button>

        <button className="btn-icon" onClick={next}>
          <NextIcon />
        </button>
      </div>

      <div className="player-progress">
        <span className="player-time">{formatTime(progress)}</span>

        <div className="player-progress-bar" onClick={handleSeek}>
          <div
            className="player-progress-fill"
            style={{ width: `${duration ? (progress / duration) * 100 : 0}%` }}
          />
        </div>

        <span className="player-time">{formatTime(duration)}</span>
      </div>

      <div className="player-volume">
        <VolumeIcon />
        <input
          type="range"
          min="0"
          max="1"
          step="0.01"
          value={volume}
          onChange={e => usePlayerStore.getState().setVolume(parseFloat(e.target.value))}
        />
      </div>

      <button className="btn-icon player-close" onClick={clearTrack}>
        <CloseIcon />
      </button>
    </div>
  )
}

function PlayIcon() {
  return (
    <svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor">
      <polygon points="5 3 19 12 5 21 5 3" />
    </svg>
  )
}

function PauseIcon() {
  return (
    <svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor">
      <rect x="6" y="4" width="4" height="16" />
      <rect x="14" y="4" width="4" height="16" />
    </svg>
  )
}

function PreviousIcon() {
  return (
    <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
      <polygon points="19 20 9 12 19 4 19 20" />
      <line x1="5" y1="19" x2="5" y2="5" stroke="currentColor" strokeWidth="2" />
    </svg>
  )
}

function NextIcon() {
  return (
    <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
      <polygon points="5 4 15 12 5 20 5 4" />
      <line x1="19" y1="5" x2="19" y2="19" stroke="currentColor" strokeWidth="2" />
    </svg>
  )
}

function VolumeIcon() {
  return (
    <svg viewBox="0 0 24 24" width="20" height="20" stroke="currentColor" fill="none" strokeWidth="2">
      <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" fill="currentColor" />
      <path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07" />
    </svg>
  )
}

function CloseIcon() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" fill="none" strokeWidth="2">
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  )
}
