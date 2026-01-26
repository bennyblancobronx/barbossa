import { useState, useRef } from 'react'
import * as api from '../services/api'

export default function ArtistCard({ artist, onClick, onDelete }) {
  const [isHearted, setIsHearted] = useState(artist.is_hearted)
  const [isLoading, setIsLoading] = useState(false)
  const [showTrash, setShowTrash] = useState(false)
  const [imageError, setImageError] = useState(false)
  const trashTimeout = useRef(null)

  // Use first letter of name as placeholder
  const initial = (artist.name || 'A')[0].toUpperCase()

  // 1-second delay for trash icon visibility (per contracts.md)
  const handleMouseEnter = () => {
    trashTimeout.current = setTimeout(() => setShowTrash(true), 1000)
  }

  const handleMouseLeave = () => {
    if (trashTimeout.current) clearTimeout(trashTimeout.current)
    setShowTrash(false)
  }

  const handleHeart = async (e) => {
    e.stopPropagation()
    setIsLoading(true)

    try {
      if (isHearted) {
        await api.unheartArtist(artist.id)
        setIsHearted(false)
      } else {
        await api.heartArtist(artist.id)
        setIsHearted(true)
      }
    } catch (error) {
      console.error('Heart action failed:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleDelete = async (e) => {
    e.stopPropagation()
    if (!confirm(`Delete "${artist.name}" and ALL their albums from disk?`)) {
      return
    }

    try {
      await api.deleteArtist(artist.id)
      if (onDelete) {
        onDelete(artist.id)
      }
    } catch (error) {
      console.error('Delete failed:', error)
    }
  }

  return (
    <div
      className="album-card"
      onClick={onClick}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      <div className="album-card-artwork">
        {!imageError ? (
          <img
            src={`/api/artists/${artist.id}/artwork`}
            alt={artist.name}
            onError={() => setImageError(true)}
          />
        ) : (
          <div className="artwork-placeholder">
            <span>{initial}</span>
          </div>
        )}

        {/* Trash icon: top-left, appears after 1s hover */}
        {showTrash && (
          <button
            className="btn-icon delete-btn album-action-top-left"
            onClick={handleDelete}
            title="Delete artist"
          >
            <TrashIcon />
          </button>
        )}

        {/* Heart icon: bottom-left */}
        <button
          className={`btn-icon heart-btn album-action-bottom-left ${isHearted ? 'is-active' : ''}`}
          onClick={handleHeart}
          disabled={isLoading}
          title={isHearted ? 'Remove from library' : 'Add to library'}
        >
          <HeartIcon filled={isHearted} />
        </button>
      </div>

      <div className="album-card-info">
        <h3 className="album-card-title">{artist.name}</h3>
      </div>
    </div>
  )
}

function HeartIcon({ filled }) {
  return (
    <svg viewBox="0 0 24 24" width="20" height="20" stroke="currentColor" fill={filled ? 'currentColor' : 'none'} strokeWidth="2">
      <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
    </svg>
  )
}

function TrashIcon() {
  return (
    <svg viewBox="0 0 24 24" width="20" height="20" stroke="currentColor" fill="none" strokeWidth="2">
      <polyline points="3 6 5 6 21 6" />
      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
    </svg>
  )
}
