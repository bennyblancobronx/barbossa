import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from 'react-query'
import * as api from '../services/api'
import { useNotificationStore } from '../stores/notifications'

export default function Settings() {
  const [activeTab, setActiveTab] = useState('general')
  const queryClient = useQueryClient()

  const { data: settings } = useQuery('settings', () => api.getSettings().then(r => r.data))
  const { data: users } = useQuery('users', () => api.getUsers().then(r => r.data.items || r.data || []))
  const { data: pending } = useQuery('pending-review', () => api.getPendingReview().then(r => r.data.items || r.data || []))

  const tabs = [
    { id: 'general', label: 'General' },
    { id: 'users', label: 'Users' },
    { id: 'sources', label: 'Sources' },
    { id: 'review', label: `Review Queue (${pending?.length || 0})` },
    { id: 'backup', label: 'Backup' },
  ]

  return (
    <div className="page-settings">
      <header className="page-header">
        <h1 className="text-2xl">Settings</h1>
      </header>

      <nav className="settings-tabs">
        {tabs.map(tab => (
          <button
            key={tab.id}
            className={`settings-tab ${activeTab === tab.id ? 'is-active' : ''}`}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      <div className="settings-content">
        {activeTab === 'general' && <GeneralSettings settings={settings} />}
        {activeTab === 'users' && <UserManagement users={users} />}
        {activeTab === 'sources' && <SourceSettings settings={settings} />}
        {activeTab === 'review' && <ReviewQueue items={pending} />}
        {activeTab === 'backup' && <BackupSettings settings={settings} />}
      </div>
    </div>
  )
}

function GeneralSettings({ settings }) {
  return (
    <section className="settings-section">
      <h2 className="text-lg">Library Settings</h2>

      <div className="form-group">
        <label className="form-label">Music Library Path</label>
        <input
          type="text"
          className="input-default"
          value={settings?.music_path || '/music/library'}
          disabled
        />
        <p className="form-hint text-muted">Set via environment variable</p>
      </div>

      <div className="form-group">
        <label className="form-label">Library Stats</label>
        <div className="stats-grid">
          <div className="stat-item">
            <span className="stat-value">{settings?.stats?.artists || 0}</span>
            <span className="stat-label">Artists</span>
          </div>
          <div className="stat-item">
            <span className="stat-value">{settings?.stats?.albums || 0}</span>
            <span className="stat-label">Albums</span>
          </div>
          <div className="stat-item">
            <span className="stat-value">{settings?.stats?.tracks || 0}</span>
            <span className="stat-label">Tracks</span>
          </div>
        </div>
      </div>
    </section>
  )
}

function UserManagement({ users }) {
  const [showAddUser, setShowAddUser] = useState(false)
  const queryClient = useQueryClient()
  const { addNotification } = useNotificationStore()

  const deleteUser = useMutation(
    (id) => api.deleteUser(id),
    {
      onSuccess: () => {
        queryClient.invalidateQueries('users')
        addNotification({ type: 'success', message: 'User deleted' })
      }
    }
  )

  return (
    <section className="settings-section">
      <div className="section-header">
        <h2 className="text-lg">User Management</h2>
        <button className="btn-secondary" onClick={() => setShowAddUser(true)}>
          Add User
        </button>
      </div>

      <div className="user-list">
        {(users || []).map(user => (
          <div key={user.id} className="user-item">
            <div className="user-info">
              <span className="user-name">{user.username}</span>
              {user.is_admin && <span className="badge">Admin</span>}
            </div>
            <div className="user-stats">
              <span>{user.album_count || 0} albums</span>
            </div>
            {!user.is_admin && (
              <button
                className="btn-ghost text-error"
                onClick={() => {
                  if (confirm(`Delete user ${user.username}?`)) {
                    deleteUser.mutate(user.id)
                  }
                }}
              >
                Delete
              </button>
            )}
          </div>
        ))}
      </div>

      {showAddUser && <AddUserModal onClose={() => setShowAddUser(false)} />}
    </section>
  )
}

function AddUserModal({ onClose }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [isAdmin, setIsAdmin] = useState(false)
  const queryClient = useQueryClient()
  const { addNotification } = useNotificationStore()

  const createUser = useMutation(
    (data) => api.createUser(data),
    {
      onSuccess: () => {
        queryClient.invalidateQueries('users')
        addNotification({ type: 'success', message: 'User created' })
        onClose()
      },
      onError: (error) => {
        addNotification({ type: 'error', message: error.response?.data?.detail || 'Failed to create user' })
      }
    }
  )

  const handleSubmit = (e) => {
    e.preventDefault()
    createUser.mutate({ username, password, is_admin: isAdmin })
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <h3 className="text-lg">Add User</h3>

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label">Username</label>
            <input
              type="text"
              className="input-default"
              value={username}
              onChange={e => setUsername(e.target.value)}
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label">Password</label>
            <input
              type="password"
              className="input-default"
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
            />
          </div>

          <div className="form-group">
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={isAdmin}
                onChange={e => setIsAdmin(e.target.checked)}
              />
              Admin privileges
            </label>
          </div>

          <div className="modal-actions">
            <button type="button" className="btn-ghost" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn-primary" disabled={createUser.isLoading}>
              Create User
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

function SourceSettings({ settings }) {
  return (
    <section className="settings-section">
      <h2 className="text-lg">Download Sources</h2>

      <div className="source-config">
        <h3 className="text-base">Qobuz</h3>
        <div className="form-group">
          <label className="form-label">Quality</label>
          <select className="input-select" defaultValue={settings?.qobuz_quality || 4}>
            <option value="0">MP3 128kbps</option>
            <option value="1">MP3 320kbps</option>
            <option value="2">FLAC 16/44.1</option>
            <option value="3">FLAC 24/96</option>
            <option value="4">FLAC 24/192 (Max)</option>
          </select>
        </div>
      </div>

      <div className="source-config">
        <h3 className="text-base">Lidarr</h3>
        <div className="form-group">
          <label className="form-label">URL</label>
          <input
            type="url"
            className="input-default"
            placeholder="http://lidarr:8686"
            defaultValue={settings?.lidarr_url || ''}
          />
        </div>
        <div className="form-group">
          <label className="form-label">API Key</label>
          <input
            type="password"
            className="input-default"
            placeholder="Enter API key"
            defaultValue={settings?.lidarr_key ? '********' : ''}
          />
        </div>
      </div>

      <div className="source-config">
        <h3 className="text-base">Plex</h3>
        <div className="form-group">
          <label className="form-label">URL</label>
          <input
            type="url"
            className="input-default"
            placeholder="http://plex:32400"
            defaultValue={settings?.plex_url || ''}
          />
        </div>
        <div className="form-group">
          <label className="form-label">Token</label>
          <input
            type="password"
            className="input-default"
            placeholder="Enter token"
            defaultValue={settings?.plex_token ? '********' : ''}
          />
        </div>
      </div>
    </section>
  )
}

function ReviewQueue({ items }) {
  const queryClient = useQueryClient()
  const { addNotification } = useNotificationStore()

  const approve = useMutation(
    ({ id, overrides }) => api.approveImport(id, overrides),
    {
      onSuccess: () => {
        queryClient.invalidateQueries('pending-review')
        addNotification({ type: 'success', message: 'Import approved' })
      }
    }
  )

  const reject = useMutation(
    (id) => api.rejectImport(id),
    {
      onSuccess: () => {
        queryClient.invalidateQueries('pending-review')
        addNotification({ type: 'info', message: 'Import rejected' })
      }
    }
  )

  if (!items?.length) {
    return (
      <section className="settings-section">
        <h2 className="text-lg">Pending Review</h2>
        <p className="text-muted">No items pending review</p>
      </section>
    )
  }

  return (
    <section className="settings-section">
      <h2 className="text-lg">Pending Review ({items.length})</h2>

      <div className="review-list">
        {items.map(item => (
          <div key={item.id} className="review-item">
            <div className="review-info">
              <span className="review-path">{item.path}</span>
              <span className="review-suggestion">
                Suggested: {item.suggested_artist} - {item.suggested_album}
              </span>
              <span className="review-confidence">
                Confidence: {Math.round((item.beets_confidence || 0) * 100)}%
              </span>
            </div>

            <div className="review-actions">
              <button
                className="btn-primary"
                onClick={() => approve.mutate({ id: item.id })}
                disabled={approve.isLoading}
              >
                Accept
              </button>
              <button
                className="btn-ghost text-error"
                onClick={() => reject.mutate(item.id)}
                disabled={reject.isLoading}
              >
                Reject
              </button>
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}

function BackupSettings({ settings }) {
  const { addNotification } = useNotificationStore()

  const triggerBackup = useMutation(
    () => api.default.post('/admin/backup/trigger'),
    {
      onSuccess: () => {
        addNotification({ type: 'success', message: 'Backup started' })
      },
      onError: () => {
        addNotification({ type: 'error', message: 'Backup failed to start' })
      }
    }
  )

  return (
    <section className="settings-section">
      <h2 className="text-lg">Backup</h2>

      <div className="form-group">
        <label className="form-label">Backup Destination</label>
        <input
          type="text"
          className="input-default"
          placeholder="/path/to/backup or rclone:remote"
          defaultValue={settings?.backup_destination || ''}
        />
      </div>

      <div className="form-group">
        <label className="form-label">Schedule</label>
        <select className="input-select" defaultValue={settings?.backup_schedule || 'weekly'}>
          <option value="daily">Daily</option>
          <option value="weekly">Weekly</option>
          <option value="monthly">Monthly</option>
        </select>
      </div>

      <button
        className="btn-secondary"
        onClick={() => triggerBackup.mutate()}
        disabled={triggerBackup.isLoading}
      >
        Run Backup Now
      </button>
    </section>
  )
}
