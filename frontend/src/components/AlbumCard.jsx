import { useState, useRef, useEffect } from 'react'
import { useQueryClient } from 'react-query'
import * as api from '../services/api'

export default function AlbumCard({ album, onClick, onDelete, onArtworkChange, onHeart }) {
  const [isHearted, setIsHearted] = useState(album.is_hearted)
  const [isLoading, setIsLoading] = useState(false)

  // Sync local state when prop changes (e.g., after refetch)
  useEffect(() => {
    setIsHearted(album.is_hearted)
  }, [album.is_hearted, album.id])
  const queryClient = useQueryClient()
  const [showTrash, setShowTrash] = useState(false)
  const [showEdit, setShowEdit] = useState(false)
  const [imageKey, setImageKey] = useState(0)
  const trashTimeout = useRef(null)
  const fileInputRef = useRef(null)

  // 1-second delay for trash icon visibility (per contracts.md)
  // Edit icon shows immediately on hover
  const handleMouseEnter = () => {
    setShowEdit(true)
    trashTimeout.current = setTimeout(() => setShowTrash(true), 1000)
  }

  const handleMouseLeave = () => {
    if (trashTimeout.current) clearTimeout(trashTimeout.current)
    setShowTrash(false)
    setShowEdit(false)
  }

  const handleHeart = async (e) => {
    e.stopPropagation()
    setIsLoading(true)

    try {
      if (isHearted) {
        await api.unheartAlbum(album.id)
        setIsHearted(false)
      } else {
        await api.heartAlbum(album.id)
        setIsHearted(true)
      }
      // Invalidate ALL library caches so all pages update
      queryClient.invalidateQueries('user-library')
      queryClient.invalidateQueries('user-library-artists')
      queryClient.invalidateQueries('user-library-artist-albums')
      queryClient.invalidateQueries('user-library-tracks')
      queryClient.invalidateQueries('artists')
      queryClient.invalidateQueries('artist-albums')
      queryClient.invalidateQueries('albums')
      queryClient.invalidateQueries('search-local')
      if (onHeart) onHeart(album.id, !isHearted)
    } catch (error) {
      console.error('Heart action failed:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleDelete = async (e) => {
    e.stopPropagation()
    const artistName = album.artist?.name || album.artist_name || 'Unknown'
    if (!confirm(`Delete "${artistName} - ${album.title}" from disk?`)) {
      return
    }

    try {
      await api.deleteAlbum(album.id)
      // Notify parent to refresh the list
      if (onDelete) {
        onDelete(album.id)
      }
    } catch (error) {
      console.error('Delete failed:', error)
    }
  }

  const handleEditClick = (e) => {
    e.stopPropagation()
    fileInputRef.current?.click()
  }

  const handleFileChange = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return

    try {
      await api.uploadArtwork(album.id, file)
      setImageKey(prev => prev + 1)
      if (onArtworkChange) onArtworkChange()
    } catch (error) {
      console.error('Artwork upload failed:', error)
    }
    e.target.value = ''
  }

  const artistName = album.artist?.name || album.artist_name || 'Unknown Artist'

  return (
    <div
      className="album-card"
      onClick={onClick}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      <div className="album-card-artwork">
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileChange}
          accept="image/jpeg,image/png"
          style={{ display: 'none' }}
        />
        {album.artwork_path || imageKey > 0 ? (
          <img
            key={imageKey}
            src={`/api/albums/${album.id}/artwork?v=${imageKey}`}
            alt={album.title}
          />
        ) : (
          <div className="artwork-placeholder">
            <span>{album.title[0]}</span>
          </div>
        )}

        {/* Trash icon: top-left, appears after 1s hover */}
        {showTrash && (
          <button
            className="btn-icon delete-btn album-action-top-left"
            onClick={handleDelete}
            title="Delete album"
          >
            <TrashIcon />
          </button>
        )}

        {/* Edit icon: top-right, appears on hover */}
        {showEdit && (
          <button
            className="btn-icon edit-btn album-action-top-right"
            onClick={handleEditClick}
            title="Edit artwork"
          >
            <PencilIcon />
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
        <h3 className="album-card-title">{album.title}</h3>
        <p className="album-card-artist">{artistName}</p>
        {album.year && (
          <span className="album-card-year">{album.year}</span>
        )}
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

function PencilIcon() {
  return (
    <svg viewBox="0 0 24 24" width="20" height="20" stroke="currentColor" fill="none" strokeWidth="2">
      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
      <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
    </svg>
  )
}
