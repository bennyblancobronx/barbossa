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

export const updateSettings = (data) =>
  api.put('/settings', data)

export const rescanLibrary = () =>
  api.post('/admin/rescan')

export const getPendingReview = () =>
  api.get('/import/review')

export const approveImport = (id, overrides) =>
  api.post(`/import/review/${id}/approve`, overrides)

export const rejectImport = (id, reason) =>
  api.post(`/import/review/${id}/reject`, { reason })

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
export const updateAlbumMetadata = (albumId, data) =>
  api.put(`/metadata/albums/${albumId}`, data)

export const updateTrackMetadata = (trackId, data) =>
  api.put(`/metadata/tracks/${trackId}`, data)

export const updateArtistMetadata = (artistId, data) =>
  api.put(`/metadata/artists/${artistId}`, data)

// Exports
export const createExport = (data) =>
  api.post('/exports', data)

export const getExports = () =>
  api.get('/exports')

export const getExport = (id) =>
  api.get(`/exports/${id}`)

export const cancelExport = (id) =>
  api.post(`/exports/${id}/cancel`)

// Lidarr
export const getLidarrStatus = () =>
  api.get('/lidarr/status')

export const getLidarrArtists = () =>
  api.get('/lidarr/artists')

export const searchLidarr = (q) =>
  api.get('/lidarr/search', { params: { q } })

export const addArtistToLidarr = (mbid, name, searchForMissing = true) =>
  api.post('/lidarr/artists', { mbid, name, search_for_missing: searchForMissing })

export const getLidarrQueue = () =>
  api.get('/lidarr/queue')

export const getLidarrHistory = (limit = 50) =>
  api.get('/lidarr/history', { params: { limit } })

// TorrentLeech
export const checkTorrentLeech = (releaseName) =>
  api.get(`/tl/check/${encodeURIComponent(releaseName)}`)

export const uploadToTorrentLeech = (albumId) =>
  api.post(`/tl/upload/${albumId}`)

// Settings
export const testLidarrConnection = (url, apiKey) =>
  api.post('/settings/test/lidarr', null, { params: { url, api_key: apiKey } })

export const testPlexConnection = (url, token) =>
  api.post('/settings/test/plex', null, { params: { url, token } })

export const triggerBandcampSync = () =>
  api.post('/settings/bandcamp/sync')

// Directory browser
export const browseDirectory = (path) =>
  api.get('/settings/browse', { params: { path } })

// Admin - User Management
export const updateUser = (userId, data) =>
  api.put(`/admin/users/${userId}`, data)

export default api
