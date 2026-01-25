import { useState } from 'react'
import { useMutation, useQueryClient } from 'react-query'
import * as api from '../services/api'
import { useNotificationStore } from '../stores/notifications'

export default function MetadataEditor({ type, item, onClose }) {
  const [formData, setFormData] = useState({
    title: item.title || item.name || '',
    year: item.year || '',
    genre: item.genre || '',
    track_number: item.track_number || ''
  })

  const queryClient = useQueryClient()
  const { addNotification } = useNotificationStore()

  const updateMutation = useMutation(
    (data) => {
      if (type === 'album') {
        return api.updateAlbumMetadata(item.id, data)
      } else if (type === 'track') {
        return api.updateTrackMetadata(item.id, data)
      } else if (type === 'artist') {
        return api.updateArtistMetadata(item.id, { name: data.title })
      }
    },
    {
      onSuccess: () => {
        queryClient.invalidateQueries(['album', item.id])
        queryClient.invalidateQueries(['artist', item.artist_id])
        addNotification({ type: 'success', message: 'Metadata updated' })
        onClose()
      },
      onError: (error) => {
        addNotification({
          type: 'error',
          message: error.response?.data?.detail || 'Update failed'
        })
      }
    }
  )

  const handleSubmit = (e) => {
    e.preventDefault()
    updateMutation.mutate(formData)
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal modal-sm" onClick={e => e.stopPropagation()}>
        <header className="modal-header">
          <h2 className="text-lg">Edit {type}</h2>
          <button className="btn-icon" onClick={onClose}>X</button>
        </header>

        <form onSubmit={handleSubmit} className="modal-body">
          {(type === 'album' || type === 'track') && (
            <div className="form-field">
              <label>Title</label>
              <input
                type="text"
                value={formData.title}
                onChange={e => setFormData({ ...formData, title: e.target.value })}
                className="input-default"
              />
            </div>
          )}

          {type === 'artist' && (
            <div className="form-field">
              <label>Artist Name</label>
              <input
                type="text"
                value={formData.title}
                onChange={e => setFormData({ ...formData, title: e.target.value })}
                className="input-default"
              />
            </div>
          )}

          {type === 'album' && (
            <>
              <div className="form-field">
                <label>Year</label>
                <input
                  type="number"
                  value={formData.year}
                  onChange={e => setFormData({ ...formData, year: e.target.value })}
                  className="input-default"
                />
              </div>
              <div className="form-field">
                <label>Genre</label>
                <input
                  type="text"
                  value={formData.genre}
                  onChange={e => setFormData({ ...formData, genre: e.target.value })}
                  className="input-default"
                />
              </div>
            </>
          )}

          {type === 'track' && (
            <div className="form-field">
              <label>Track Number</label>
              <input
                type="number"
                value={formData.track_number}
                onChange={e => setFormData({ ...formData, track_number: e.target.value })}
                className="input-default"
              />
            </div>
          )}

          <div className="modal-footer">
            <button type="button" className="btn-secondary" onClick={onClose}>
              Cancel
            </button>
            <button
              type="submit"
              className="btn-primary"
              disabled={updateMutation.isLoading}
            >
              Save
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
