# Phase 4: Frontend GUI

**Goal:** React frontend with all user-facing pages operational.

**Prerequisites:** Phase 3 complete (API + WebSocket working)

---

## Checklist

- [ ] Project setup (Vite + React)
- [ ] API client with auth
- [ ] WebSocket connection
- [ ] Zustand stores
- [ ] Master Library page (A-Z nav, album grid)
- [ ] User Library page
- [ ] Downloads page
- [ ] Settings page (admin only)
- [ ] Login page
- [ ] Album detail modal
- [ ] TrackRow component (Heart, Track#, Title, Source, Quality)
- [ ] SearchBar component
- [ ] AlbumCard with icon positions (Heart bottom-left, Trash top-left, Source bottom-right)
- [ ] Trash icon 1-second hover delay
- [ ] Persistent audio player
- [ ] Toast notifications
- [ ] Dark mode support

---

## 1. Project Setup

### frontend/vite.config.js

```javascript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8080',
        changeOrigin: true
      },
      '/ws': {
        target: 'ws://localhost:8080',
        ws: true
      }
    }
  },
  build: {
    outDir: 'build'
  }
})
```

### frontend/src/index.jsx

```jsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from 'react-query'
import App from './App'
import './styles/design-system.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 5 * 60 * 1000
    }
  }
})

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <QueryClientProvider client={queryClient}>
        <App />
      </QueryClientProvider>
    </BrowserRouter>
  </React.StrictMode>
)
```

### frontend/src/App.jsx

```jsx
import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './stores/auth'
import Layout from './components/Layout'
import Login from './pages/Login'
import Library from './pages/Library'
import UserLibrary from './pages/UserLibrary'
import Downloads from './pages/Downloads'
import Settings from './pages/Settings'

function PrivateRoute({ children }) {
  const isAuthenticated = useAuthStore(state => state.isAuthenticated)
  return isAuthenticated ? children : <Navigate to="/login" />
}

function AdminRoute({ children }) {
  const isAdmin = useAuthStore(state => state.user?.is_admin)
  return isAdmin ? children : <Navigate to="/" />
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />

      <Route path="/" element={
        <PrivateRoute>
          <Layout />
        </PrivateRoute>
      }>
        <Route index element={<Library />} />
        <Route path="my-library" element={<UserLibrary />} />
        <Route path="downloads" element={<Downloads />} />
        <Route path="settings" element={
          <AdminRoute>
            <Settings />
          </AdminRoute>
        } />
      </Route>
    </Routes>
  )
}
```

---

## 2. API Client

### frontend/src/services/api.js

```javascript
import axios from 'axios'
import { useAuthStore } from '../stores/auth'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000
})

// Request interceptor - add auth token
api.interceptors.request.use(config => {
  const token = useAuthStore.getState().token
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Response interceptor - handle 401
api.interceptors.response.use(
  response => response,
  error => {
    if (error.response?.status === 401) {
      useAuthStore.getState().logout()
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

// Auth
export const login = (username, password) =>
  api.post('/auth/login', { username, password })

export const getMe = () =>
  api.get('/auth/me')

// Library
export const getArtists = (params) =>
  api.get('/artists', { params })

export const getArtist = (id) =>
  api.get(`/artists/${id}`)

export const getAlbums = (params) =>
  api.get('/albums', { params })

export const getAlbum = (id) =>
  api.get(`/albums/${id}`)

export const searchLibrary = (query, type = 'all') =>
  api.get('/search', { params: { q: query, type } })

export const deleteAlbum = (id) =>
  api.delete(`/albums/${id}`)

// User Library
export const getUserLibrary = () =>
  api.get('/me/library')

export const heartAlbum = (albumId) =>
  api.post(`/me/library/albums/${albumId}`)

export const unheartAlbum = (albumId) =>
  api.delete(`/me/library/albums/${albumId}`)

export const heartTrack = (trackId) =>
  api.post(`/me/library/tracks/${trackId}`)

export const unheartTrack = (trackId) =>
  api.delete(`/me/library/tracks/${trackId}`)

// Downloads
export const searchQobuz = (q, type, limit = 20) =>
  api.get('/downloads/search/qobuz', { params: { q, type, limit } })

export const downloadQobuz = (url, quality = 4, searchType = null) =>
  api.post('/downloads/qobuz', { url, quality, search_type: searchType })

export const downloadUrl = (url, confirmLossy = false, searchType = null) =>
  api.post('/downloads/url', { url, confirm_lossy: confirmLossy, search_type: searchType })

export const getDownloads = () =>
  api.get('/downloads/queue')

export const cancelDownload = (id) =>
  api.delete(`/downloads/${id}`)

// Admin
export const getUsers = () =>
  api.get('/admin/users')

export const createUser = (data) =>
  api.post('/admin/users', data)

export const deleteUser = (id) =>
  api.delete(`/admin/users/${id}`)

export const getSettings = () =>
  api.get('/settings')

export const updateSetting = (data) =>
  api.put('/settings', data)

export const rescanLibrary = () =>
  api.post('/admin/rescan')

export const getPendingReview = () =>
  api.get('/admin/review')

export const approveImport = (id, overrides) =>
  api.post(`/admin/review/${id}/approve`, overrides)

export const rejectImport = (id, reason) =>
  api.post(`/admin/review/${id}/reject`, { reason })

// Artwork
export const uploadArtwork = (albumId, file) => {
  const formData = new FormData()
  formData.append('artwork', file)
  return api.put(`/albums/${albumId}/artwork`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

export const restoreArtwork = (albumId) =>
  api.delete(`/albums/${albumId}/artwork`)

// Metadata
export const updateAlbumMetadata = (id, data) =>
  api.put(`/metadata/albums/${id}`, data)

export const updateTrackMetadata = (id, data) =>
  api.put(`/metadata/tracks/${id}`, data)

export const updateArtistMetadata = (id, data) =>
  api.put(`/metadata/artists/${id}`, data)

export default api
```

---

## 3. WebSocket Service

### frontend/src/services/websocket.js

```javascript
import { useAuthStore } from '../stores/auth'
import { useNotificationStore } from '../stores/notifications'
import { useDownloadStore } from '../stores/downloads'

let socket = null
let reconnectTimeout = null
const RECONNECT_DELAY = 5000

export function connectWebSocket() {
  const token = useAuthStore.getState().token
  if (!token) return

  const wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws?token=${token}`

  socket = new WebSocket(wsUrl)

  socket.onopen = () => {
    console.log('WebSocket connected')
    // Subscribe to channels
    socket.send(JSON.stringify({ type: 'subscribe', channel: 'activity' }))

    if (useAuthStore.getState().user?.is_admin) {
      socket.send(JSON.stringify({ type: 'subscribe', channel: 'downloads' }))
    }
  }

  socket.onmessage = (event) => {
    const data = JSON.parse(event.data)
    handleMessage(data)
  }

  socket.onclose = () => {
    console.log('WebSocket disconnected')
    // Reconnect
    reconnectTimeout = setTimeout(connectWebSocket, RECONNECT_DELAY)
  }

  socket.onerror = (error) => {
    console.error('WebSocket error:', error)
  }
}

export function disconnectWebSocket() {
  if (reconnectTimeout) {
    clearTimeout(reconnectTimeout)
  }
  if (socket) {
    socket.close()
    socket = null
  }
}

function handleMessage(data) {
  switch (data.type) {
    case 'heartbeat':
      // Connection alive
      break

    case 'download_progress':
      useDownloadStore.getState().updateProgress(
        data.download_id,
        data.percent,
        data.speed,
        data.eta
      )
      break

    case 'activity':
      handleActivity(data)
      break

    case 'notification':
      useNotificationStore.getState().addNotification(data)
      break
  }
}

function handleActivity(data) {
  const { addNotification } = useNotificationStore.getState()

  switch (data.action) {
    case 'new_album':
      addNotification({
        type: 'info',
        message: `New album: ${data.artist} - ${data.title}`
      })
      break

    case 'heart':
      // Optional: show in activity feed
      break
  }
}
```

---

## 4. Stores (Zustand)

### frontend/src/stores/auth.js

```javascript
import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import * as api from '../services/api'
import { connectWebSocket, disconnectWebSocket } from '../services/websocket'

export const useAuthStore = create(
  persist(
    (set, get) => ({
      token: null,
      user: null,
      isAuthenticated: false,

      login: async (username, password) => {
        const response = await api.login(username, password)
        const { token } = response.data

        set({ token })

        // Fetch user info
        const userResponse = await api.getMe()
        set({
          user: userResponse.data,
          isAuthenticated: true
        })

        // Connect WebSocket
        connectWebSocket()

        return userResponse.data
      },

      logout: () => {
        disconnectWebSocket()
        set({
          token: null,
          user: null,
          isAuthenticated: false
        })
      },

      checkAuth: async () => {
        const token = get().token
        if (!token) return false

        try {
          const response = await api.getMe()
          set({ user: response.data, isAuthenticated: true })
          connectWebSocket()
          return true
        } catch {
          get().logout()
          return false
        }
      }
    }),
    {
      name: 'barbossa-auth',
      partialize: (state) => ({ token: state.token })
    }
  )
)
```

### frontend/src/stores/notifications.js

```javascript
import { create } from 'zustand'

export const useNotificationStore = create((set, get) => ({
  notifications: [],

  addNotification: (notification) => {
    const id = Date.now()
    const newNotification = {
      id,
      type: 'info',
      duration: 4000,
      ...notification
    }

    set(state => ({
      notifications: [...state.notifications, newNotification]
    }))

    // Auto-remove
    if (newNotification.duration > 0) {
      setTimeout(() => {
        get().removeNotification(id)
      }, newNotification.duration)
    }
  },

  removeNotification: (id) => {
    set(state => ({
      notifications: state.notifications.filter(n => n.id !== id)
    }))
  }
}))
```

### frontend/src/stores/downloads.js

```javascript
import { create } from 'zustand'

export const useDownloadStore = create((set) => ({
  downloads: [],

  setDownloads: (downloads) => set({ downloads }),

  updateProgress: (id, percent, speed, eta) => {
    set(state => ({
      downloads: state.downloads.map(d =>
        d.id === id ? { ...d, progress: percent, speed, eta } : d
      )
    }))
  },

  addDownload: (download) => {
    set(state => ({
      downloads: [download, ...state.downloads]
    }))
  },

  removeDownload: (id) => {
    set(state => ({
      downloads: state.downloads.filter(d => d.id !== id)
    }))
  }
}))
```

### frontend/src/stores/player.js

```javascript
import { create } from 'zustand'

export const usePlayerStore = create((set, get) => ({
  currentTrack: null,
  queue: [],
  isPlaying: false,
  volume: 1,
  progress: 0,
  duration: 0,

  play: (track, queue = []) => {
    set({
      currentTrack: track,
      queue: queue.length ? queue : [track],
      isPlaying: true,
      progress: 0
    })
  },

  pause: () => set({ isPlaying: false }),

  resume: () => set({ isPlaying: true }),

  toggle: () => set(state => ({ isPlaying: !state.isPlaying })),

  next: () => {
    const { queue, currentTrack } = get()
    const currentIndex = queue.findIndex(t => t.id === currentTrack?.id)
    const nextTrack = queue[currentIndex + 1]

    if (nextTrack) {
      set({ currentTrack: nextTrack, progress: 0 })
    }
  },

  previous: () => {
    const { queue, currentTrack, progress } = get()

    // If more than 3 seconds in, restart current track
    if (progress > 3) {
      set({ progress: 0 })
      return
    }

    const currentIndex = queue.findIndex(t => t.id === currentTrack?.id)
    const prevTrack = queue[currentIndex - 1]

    if (prevTrack) {
      set({ currentTrack: prevTrack, progress: 0 })
    }
  },

  setProgress: (progress) => set({ progress }),

  setDuration: (duration) => set({ duration }),

  setVolume: (volume) => set({ volume })
}))
```

---

## 5. Components

### frontend/src/components/Layout.jsx

```jsx
import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import Player from './Player'
import ToastContainer from './ToastContainer'

export default function Layout() {
  return (
    <div className="layout-dashboard">
      <Sidebar />

      <main className="main-content">
        <Header />
        <Outlet />
      </main>

      <Player />
      <ToastContainer />
    </div>
  )
}
```

### frontend/src/components/Header.jsx

```jsx
import { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import SearchBar from './SearchBar'

export default function Header() {
  const [searchQuery, setSearchQuery] = useState('')
  const navigate = useNavigate()
  const location = useLocation()

  const handleSearch = (query) => {
    setSearchQuery(query)
    // Navigate to library with search param
    navigate(`/?q=${encodeURIComponent(query)}`)
  }

  return (
    <header className="app-header">
      <div className="header-left">
        {/* Breadcrumbs or page title can go here */}
      </div>

      <div className="header-right">
        <SearchBar
          value={searchQuery}
          onChange={handleSearch}
          placeholder="Search library..."
        />
      </div>
    </header>
  )
}
```

### frontend/src/components/Sidebar.jsx

```jsx
import { NavLink } from 'react-router-dom'
import { useAuthStore } from '../stores/auth'

export default function Sidebar() {
  const { user, logout } = useAuthStore()

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <h1 className="text-2xl">barbossa</h1>
      </div>

      <nav className="sidebar-nav">
        <NavLink to="/" className={({ isActive }) =>
          `nav-link ${isActive ? 'is-active' : ''}`
        }>
          Master Library
        </NavLink>

        <NavLink to="/my-library" className={({ isActive }) =>
          `nav-link ${isActive ? 'is-active' : ''}`
        }>
          My Library
        </NavLink>

        <NavLink to="/downloads" className={({ isActive }) =>
          `nav-link ${isActive ? 'is-active' : ''}`
        }>
          Downloads
        </NavLink>

        {user?.is_admin && (
          <NavLink to="/settings" className={({ isActive }) =>
            `nav-link ${isActive ? 'is-active' : ''}`
          }>
            Settings
          </NavLink>
        )}
      </nav>

      <div className="sidebar-footer">
        <span className="text-muted text-sm">{user?.username}</span>
        <button onClick={logout} className="btn-ghost text-sm">
          Logout
        </button>
      </div>
    </aside>
  )
}
```

### frontend/src/components/AlbumGrid.jsx

```jsx
import AlbumCard from './AlbumCard'

export default function AlbumGrid({ albums, onAlbumClick }) {
  if (!albums.length) {
    return (
      <div className="empty-state">
        <p className="text-muted">No albums found</p>
      </div>
    )
  }

  return (
    <div className="album-grid">
      {albums.map(album => (
        <AlbumCard
          key={album.id}
          album={album}
          onClick={() => onAlbumClick(album)}
        />
      ))}
    </div>
  )
}
```

### frontend/src/components/AlbumCard.jsx

```jsx
import { useState } from 'react'
import { useAuthStore } from '../stores/auth'
import * as api from '../services/api'

export default function AlbumCard({ album, onClick }) {
  const [isHearted, setIsHearted] = useState(album.is_hearted)
  const [isLoading, setIsLoading] = useState(false)
  const [showTrash, setShowTrash] = useState(false)
  const isAdmin = useAuthStore(state => state.user?.is_admin)

  // 1-second delay for trash icon visibility (per contracts.md)
  let trashTimeout = null

  const handleMouseEnter = () => {
    if (isAdmin) {
      trashTimeout = setTimeout(() => setShowTrash(true), 1000)
    }
  }

  const handleMouseLeave = () => {
    if (trashTimeout) clearTimeout(trashTimeout)
    setShowTrash(false)
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
    } catch (error) {
      console.error('Heart action failed:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleDelete = async (e) => {
    e.stopPropagation()
    if (!confirm(`Delete "${album.artist.name} - ${album.title}" from disk?`)) {
      return
    }

    try {
      await api.deleteAlbum(album.id)
      // Trigger refresh
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
        {album.artwork_path ? (
          <img src={`/api/albums/${album.id}/artwork`} alt={album.title} />
        ) : (
          <div className="artwork-placeholder">
            <span>{album.title[0]}</span>
          </div>
        )}

        {/* Trash icon: top-left, appears after 1s hover (admin only) */}
        {isAdmin && showTrash && (
          <button
            className="btn-icon delete-btn album-action-top-left"
            onClick={handleDelete}
            title="Delete album"
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

        {/* Source badge: bottom-right */}
        {album.source && (
          <span className={`album-source-badge badge badge-${album.source}`}>
            {album.source}
          </span>
        )}
      </div>

      <div className="album-card-info">
        <h3 className="album-card-title">{album.title}</h3>
        <p className="album-card-artist">{album.artist.name}</p>
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
```

### frontend/src/components/AlbumModal.jsx

```jsx
import { useState } from 'react'
import { useQuery } from 'react-query'
import * as api from '../services/api'
import { usePlayerStore } from '../stores/player'
import TrackRow from './TrackRow'

export default function AlbumModal({ album, onClose }) {
  const { data, isLoading } = useQuery(
    ['album', album.id],
    () => api.getAlbum(album.id).then(r => r.data),
    { initialData: album }
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
              <p className="text-lg text-secondary">{data.artist?.name}</p>

              <div className="album-detail-meta">
                {data.year && <span>{data.year}</span>}
                {data.genre && <span>{data.genre}</span>}
                <span>{data.available_tracks} tracks</span>
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
    ? `${track.bitrate}kbps ${track.format}`
    : `${track.bit_depth}/${track.sample_rate / 1000}kHz ${track.format}`

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
```

### frontend/src/components/Player.jsx

```jsx
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
    setDuration
  } = usePlayerStore()

  useEffect(() => {
    if (!audioRef.current || !currentTrack) return

    const audio = audioRef.current
    audio.src = `/api/tracks/${currentTrack.id}/stream`

    if (isPlaying) {
      audio.play()
    }
  }, [currentTrack])

  useEffect(() => {
    if (!audioRef.current) return

    if (isPlaying) {
      audioRef.current.play()
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
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  if (!currentTrack) return null

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
        <span className="player-artist">{currentTrack.album?.artist?.name}</span>
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
            style={{ width: `${(progress / duration) * 100}%` }}
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
```

### frontend/src/components/ToastContainer.jsx

```jsx
import { useNotificationStore } from '../stores/notifications'

export default function ToastContainer() {
  const { notifications, removeNotification } = useNotificationStore()

  return (
    <div className="toast-container">
      {notifications.map(notification => (
        <div
          key={notification.id}
          className={`toast toast-${notification.type}`}
        >
          <span className="toast-message">{notification.message}</span>
          <button
            className="toast-close"
            onClick={() => removeNotification(notification.id)}
          >
            <CloseIcon />
          </button>
        </div>
      ))}
    </div>
  )
}

function CloseIcon() {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" fill="none" strokeWidth="2">
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  )
}
```

### frontend/src/components/TrackRow.jsx

```jsx
import { useState } from 'react'
import * as api from '../services/api'

export default function TrackRow({ track, onPlay, showAlbumInfo = false }) {
  const [isHearted, setIsHearted] = useState(track.is_hearted)
  const [isLoading, setIsLoading] = useState(false)

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

  const formatDuration = (seconds) => {
    if (!seconds) return '--:--'
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  const getQualityLabel = () => {
    if (track.is_lossy) {
      return `${track.bitrate}kbps`
    }
    return `${track.bit_depth}/${Math.round(track.sample_rate / 1000)}kHz`
  }

  return (
    <div className="track-row" onClick={onPlay}>
      <button
        className={`btn-icon track-heart ${isHearted ? 'is-active' : ''}`}
        onClick={handleHeart}
        disabled={isLoading}
      >
        <HeartIcon filled={isHearted} size={16} />
      </button>

      <span className="track-number">{track.track_number}</span>

      <div className="track-info">
        <span className="track-title">{track.title}</span>
        {showAlbumInfo && (
          <span className="track-album">{track.album?.title}</span>
        )}
      </div>

      <span className={`track-source badge badge-${track.source}`}>
        {track.source}
      </span>

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
```

### frontend/src/components/SearchBar.jsx

Search behavior:
- Call `/api/search` for local results.
- If local results are empty, auto-fallback to Qobuz search and show results with download actions.
- Do not auto-search playlists; playlist search is available only on the Downloads page.

```jsx
import { useState, useCallback } from 'react'
import { debounce } from '../utils/debounce'

export default function SearchBar({
  value,
  onChange,
  placeholder = 'Search...',
  debounceMs = 300
}) {
  const [localValue, setLocalValue] = useState(value || '')

  const debouncedOnChange = useCallback(
    debounce((val) => onChange(val), debounceMs),
    [onChange, debounceMs]
  )

  const handleChange = (e) => {
    const newValue = e.target.value
    setLocalValue(newValue)
    debouncedOnChange(newValue)
  }

  const handleClear = () => {
    setLocalValue('')
    onChange('')
  }

  return (
    <div className="search-bar">
      <SearchIcon />
      <input
        type="text"
        value={localValue}
        onChange={handleChange}
        placeholder={placeholder}
        className="search-input"
      />
      {localValue && (
        <button className="search-clear" onClick={handleClear}>
          <CloseIcon />
        </button>
      )}
    </div>
  )
}

function SearchIcon() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" fill="none" strokeWidth="2">
      <circle cx="11" cy="11" r="8" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
  )
}

function CloseIcon() {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" fill="none" strokeWidth="2">
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  )
}
```

### frontend/src/utils/debounce.js

```javascript
export function debounce(fn, ms) {
  let timeout
  return (...args) => {
    clearTimeout(timeout)
    timeout = setTimeout(() => fn(...args), ms)
  }
}
```

---

## 6. Pages

### frontend/src/pages/Library.jsx

```jsx
import { useState } from 'react'
import { useQuery } from 'react-query'
import * as api from '../services/api'
import AlbumGrid from '../components/AlbumGrid'
import AlbumModal from '../components/AlbumModal'
import SearchBar from '../components/SearchBar'

const LETTERS = '#ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('')

export default function Library() {
  const [selectedLetter, setSelectedLetter] = useState(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedAlbum, setSelectedAlbum] = useState(null)

  const { data: albums, isLoading } = useQuery(
    ['albums', selectedLetter, searchQuery],
    () => {
      if (searchQuery) {
        return api.searchLibrary(searchQuery, 'album').then(r => r.data.albums)
      }
      return api.getAlbums({ letter: selectedLetter }).then(r => r.data.items)
    }
  )

  return (
    <div className="page-library">
      <header className="page-header">
        <h1 className="text-2xl">Master Library</h1>
        <SearchBar
          value={searchQuery}
          onChange={setSearchQuery}
          placeholder="Search albums, artists, tracks..."
        />
      </header>

      {!searchQuery && (
        <nav className="letter-nav">
          <button
            className={`letter-nav-item ${!selectedLetter ? 'is-active' : ''}`}
            onClick={() => setSelectedLetter(null)}
          >
            All
          </button>
          {LETTERS.map(letter => (
            <button
              key={letter}
              className={`letter-nav-item ${selectedLetter === letter ? 'is-active' : ''}`}
              onClick={() => setSelectedLetter(letter)}
            >
              {letter}
            </button>
          ))}
        </nav>
      )}

      {isLoading ? (
        <div className="loading-state">
          <p>Loading...</p>
        </div>
      ) : (
        <AlbumGrid
          albums={albums || []}
          onAlbumClick={setSelectedAlbum}
        />
      )}

      {selectedAlbum && (
        <AlbumModal
          album={selectedAlbum}
          onClose={() => setSelectedAlbum(null)}
        />
      )}
    </div>
  )
}
```

### frontend/src/pages/Downloads.jsx

```jsx
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from 'react-query'
import * as api from '../services/api'
import { useDownloadStore } from '../stores/downloads'
import { useNotificationStore } from '../stores/notifications'

export default function Downloads() {
  const [searchQuery, setSearchQuery] = useState('')
  const [searchType, setSearchType] = useState('album')
  const [urlInput, setUrlInput] = useState('')

  const queryClient = useQueryClient()
  const { addNotification } = useNotificationStore()
  const downloads = useDownloadStore(state => state.downloads)

  // Fetch download queue
  const { data: downloadQueue } = useQuery(
    'downloads',
    () => api.getDownloads().then(r => r.data),
    {
      onSuccess: (data) => {
        useDownloadStore.getState().setDownloads(data)
      },
      refetchInterval: 5000
    }
  )

  // Search Qobuz
  const { data: searchResults, isLoading: isSearching, refetch: doSearch } = useQuery(
    ['qobuz-search', searchQuery, searchType],
    () => api.searchQobuz(searchQuery, searchType).then(r => r.data),
    { enabled: false }
  )

  // Download mutations
  const downloadQobuz = useMutation(
    (url) => api.downloadQobuz(url, 4, searchType),
    {
      onSuccess: () => {
        addNotification({ type: 'success', message: 'Download started' })
        queryClient.invalidateQueries('downloads')
      }
    }
  )

  const downloadUrl = useMutation(
    ({ url, confirmLossy }) => api.downloadUrl(url, confirmLossy, searchType),
    {
      onSuccess: () => {
        addNotification({ type: 'success', message: 'Download started' })
        setUrlInput('')
        queryClient.invalidateQueries('downloads')
      },
      onError: (error) => {
        if (error.response?.data?.detail?.includes('lossy')) {
          if (confirm('This is a lossy source. Download anyway?')) {
            downloadUrl.mutate({ url: urlInput, confirmLossy: true })
          }
        }
      }
    }
  )

  const handleSearch = (e) => {
    e.preventDefault()
    if (searchQuery.trim()) {
      doSearch()
    }
  }

  const handleUrlDownload = (e) => {
    e.preventDefault()
    if (urlInput.trim()) {
      downloadUrl.mutate({ url: urlInput, confirmLossy: false })
    }
  }

  return (
    <div className="page-downloads">
      <header className="page-header">
        <h1 className="text-2xl">Downloads</h1>
        <p className="text-muted">Temporary staging only</p>
      </header>

      <section className="download-section">
        <h2 className="text-lg">Search Qobuz</h2>

        <form onSubmit={handleSearch} className="search-form">
          <select
            value={searchType}
            onChange={e => setSearchType(e.target.value)}
            className="input-select"
          >
            <option value="album">Album</option>
            <option value="artist">Artist</option>
            <option value="track">Track</option>
            <option value="playlist">Playlist</option>
          </select>

          <input
            type="text"
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            placeholder="Search Qobuz..."
            className="input-default"
          />

          <button type="submit" className="btn-primary" disabled={isSearching}>
            Search
          </button>
        </form>

        {searchResults && (
          <div className="search-results">
            {searchResults.map(result => (
              <div key={result.id} className="search-result-item">
                <div className="search-result-info">
                  <span className="search-result-title">{result.title}</span>
                  <span className="search-result-artist">{result.artist}</span>
                  {result.year && <span className="search-result-year">{result.year}</span>}
                </div>
                <button
                  className="btn-secondary"
                  onClick={() => downloadQobuz.mutate(result.url)}
                  disabled={downloadQobuz.isLoading}
                >
                  Download
                </button>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="download-section">
        <h2 className="text-lg">Download from URL</h2>
        <p className="text-sm text-muted">YouTube, Bandcamp, Soundcloud</p>

        <form onSubmit={handleUrlDownload} className="url-form">
          <input
            type="url"
            value={urlInput}
            onChange={e => setUrlInput(e.target.value)}
            placeholder="Paste URL..."
            className="input-default"
          />

          <button type="submit" className="btn-primary" disabled={downloadUrl.isLoading}>
            Download
          </button>
        </form>
      </section>

      <section className="download-section">
        <h2 className="text-lg">Download Queue</h2>

        {downloads.length === 0 ? (
          <p className="text-muted">No downloads in progress</p>
        ) : (
          <div className="download-queue">
            {downloads.map(download => (
              <DownloadItem key={download.id} download={download} />
            ))}
          </div>
        )}
      </section>
    </div>
  )
}

### frontend/src/pages/Login.jsx

```jsx
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../stores/auth'

export default function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [isLoading, setIsLoading] = useState(false)

  const login = useAuthStore(state => state.login)
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setIsLoading(true)

    try {
      await login(username, password)
      navigate('/')
    } catch (err) {
      setError(err.response?.data?.detail || 'Login failed')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="login-page">
      <div className="login-container">
        <h1 className="text-2xl login-title">barbossa</h1>

        <form onSubmit={handleSubmit} className="login-form">
          {error && (
            <div className="login-error">{error}</div>
          )}

          <div className="form-group">
            <label htmlFor="username" className="form-label">Username</label>
            <input
              id="username"
              type="text"
              value={username}
              onChange={e => setUsername(e.target.value)}
              className="input-default"
              required
              autoFocus
            />
          </div>

          <div className="form-group">
            <label htmlFor="password" className="form-label">Password</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              className="input-default"
              required
            />
          </div>

          <button
            type="submit"
            className="btn-primary login-submit"
            disabled={isLoading}
          >
            {isLoading ? 'Logging in...' : 'Login'}
          </button>
        </form>
      </div>
    </div>
  )
}
```

### frontend/src/pages/UserLibrary.jsx

```jsx
import { useState } from 'react'
import { useQuery } from 'react-query'
import * as api from '../services/api'
import { useAuthStore } from '../stores/auth'
import AlbumGrid from '../components/AlbumGrid'
import AlbumModal from '../components/AlbumModal'
import SearchBar from '../components/SearchBar'

export default function UserLibrary() {
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedAlbum, setSelectedAlbum] = useState(null)
  const user = useAuthStore(state => state.user)

  const { data, isLoading, refetch } = useQuery(
    ['user-library', user?.id],
    () => api.getUserLibrary().then(r => r.data),
    { enabled: !!user?.id }
  )

  const filteredAlbums = searchQuery
    ? data?.items?.filter(album =>
        album.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        album.artist?.name?.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : data?.items

  const handleUnheart = async (albumId) => {
    await api.unheartAlbum(albumId)
    refetch()
  }

  return (
    <div className="page-user-library">
      <header className="page-header">
        <h1 className="text-2xl">My Library</h1>
        <span className="text-muted">
          {data?.total || 0} albums
        </span>
      </header>

      <div className="library-toolbar">
        <SearchBar
          value={searchQuery}
          onChange={setSearchQuery}
          placeholder="Filter my library..."
        />
      </div>

      {isLoading ? (
        <div className="loading-state">
          <p>Loading...</p>
        </div>
      ) : filteredAlbums?.length === 0 ? (
        <div className="empty-state">
          <p className="text-muted">
            {searchQuery
              ? 'No albums match your search'
              : 'No albums in your library. Heart albums to add them here.'}
          </p>
        </div>
      ) : (
        <AlbumGrid
          albums={filteredAlbums || []}
          onAlbumClick={setSelectedAlbum}
          showHearted={true}
        />
      )}

      {selectedAlbum && (
        <AlbumModal
          album={selectedAlbum}
          onClose={() => setSelectedAlbum(null)}
          onUnheart={handleUnheart}
        />
      )}
    </div>
  )
}
```

### frontend/src/pages/Settings.jsx

```jsx
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from 'react-query'
import * as api from '../services/api'
import { useNotificationStore } from '../stores/notifications'

export default function Settings() {
  const [activeTab, setActiveTab] = useState('general')
  const queryClient = useQueryClient()
  const { addNotification } = useNotificationStore()

  const { data: settings } = useQuery('settings', () => api.getSettings().then(r => r.data))
  const { data: users } = useQuery('users', () => api.getUsers().then(r => r.data))
  const { data: pending } = useQuery('pending-review', () => api.getPendingReview().then(r => r.data))

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
          value={settings?.music_path || ''}
          disabled
        />
        <p className="form-hint text-muted">Set via environment variable</p>
      </div>

      <div className="form-group">
        <label className="form-label">Download Folders</label>
        <input
          type="text"
          className="input-default"
          placeholder="Watch folder"
          defaultValue={settings?.watch_folder || ''}
        />
        <input
          type="text"
          className="input-default"
          placeholder="Torrent folder"
          defaultValue={settings?.torrent_folder || ''}
        />
        <input
          type="text"
          className="input-default"
          placeholder="Usenet folder"
          defaultValue={settings?.usenet_folder || ''}
        />
        <input
          type="text"
          className="input-default"
          placeholder="Barbossa downloads location"
          defaultValue={settings?.download_folder || ''}
        />
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

  const deleteUser = useMutation(
    (id) => api.deleteUser(id),
    { onSuccess: () => queryClient.invalidateQueries('users') }
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
        {users?.map(user => (
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

  const createUser = useMutation(
    (data) => api.createUser(data),
    {
      onSuccess: () => {
        queryClient.invalidateQueries('users')
        onClose()
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

  const approve = useMutation(
    ({ id, overrides }) => api.approveImport(id, overrides),
    { onSuccess: () => queryClient.invalidateQueries('pending-review') }
  )

  const reject = useMutation(
    (id) => api.rejectImport(id),
    { onSuccess: () => queryClient.invalidateQueries('pending-review') }
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
                Confidence: {Math.round(item.beets_confidence * 100)}%
              </span>
            </div>

            <div className="review-actions">
              <button
                className="btn-primary"
                onClick={() => approve.mutate({ id: item.id })}
              >
                Accept
              </button>
              <button
                className="btn-ghost text-error"
                onClick={() => reject.mutate(item.id)}
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

      <button className="btn-secondary">
        Run Backup Now
      </button>
    </section>
  )
}
```

function DownloadItem({ download }) {
  const queryClient = useQueryClient()

  const cancel = useMutation(
    () => api.cancelDownload(download.id),
    {
      onSuccess: () => {
        queryClient.invalidateQueries('downloads')
      }
    }
  )

  const statusColors = {
    pending: 'text-muted',
    downloading: 'text-primary',
    importing: 'text-primary',
    complete: 'text-success',
    failed: 'text-error',
    cancelled: 'text-muted'
  }

  return (
    <div className="download-item">
      <div className="download-item-info">
        <span className="download-item-source">{download.source}</span>
        <span className="download-item-url">{download.source_url}</span>
      </div>

      <div className="download-item-status">
        <span className={statusColors[download.status]}>
          {download.status}
        </span>

        {download.status === 'downloading' && (
          <div className="download-progress">
            <div className="progress-bar">
              <div
                className="progress-fill"
                style={{ width: `${download.progress}%` }}
              />
            </div>
            <span className="download-speed">{download.speed}</span>
            <span className="download-eta">{download.eta}</span>
          </div>
        )}

        {download.error_message && (
          <span className="download-error">{download.error_message}</span>
        )}
      </div>

      {['pending', 'downloading'].includes(download.status) && (
        <button
          className="btn-ghost text-error"
          onClick={() => cancel.mutate()}
          disabled={cancel.isLoading}
        >
          Cancel
        </button>
      )}
    </div>
  )
}
```

---

## Validation

Before moving to Phase 5, verify:

1. [ ] Login/logout working
2. [ ] Library page shows albums with A-Z filter
3. [ ] Search filters results
4. [ ] Album modal shows track list
5. [ ] Heart/unheart updates state
6. [ ] Player plays tracks
7. [ ] Downloads page searches Qobuz
8. [ ] Download progress shows in queue
9. [ ] Toast notifications appear
10. [ ] Dark mode toggle works

---

## Exit Criteria

- [ ] All four pages functional
- [ ] WebSocket connected and receiving updates
- [ ] Audio playback working
- [ ] Heart state persists
- [ ] Admin sees Settings page
- [ ] Responsive on mobile viewport
