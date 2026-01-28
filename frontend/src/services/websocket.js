import { useAuthStore } from '../stores/auth'
import { useNotificationStore } from '../stores/notifications'
import { useDownloadStore } from '../stores/downloads'
import { queryClient } from '../queryClient'
import { getDownloads } from './api'

let socket = null
let reconnectTimeout = null
const RECONNECT_DELAY = 5000

function fetchDownloadQueue() {
  getDownloads()
    .then(r => {
      useDownloadStore.getState().setDownloads(r.data.items || r.data || [])
    })
    .catch(() => {})
}

export function connectWebSocket() {
  const token = useAuthStore.getState().token
  if (!token) return

  // Prevent duplicate connections
  if (socket && (socket.readyState === WebSocket.CONNECTING || socket.readyState === WebSocket.OPEN)) {
    return
  }

  const wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws?token=${token}`

  socket = new WebSocket(wsUrl)

  socket.onopen = () => {
    console.log('WebSocket connected')
    // Subscribe to channels
    socket.send(JSON.stringify({ type: 'subscribe', channel: 'activity' }))
    socket.send(JSON.stringify({ type: 'subscribe', channel: 'library' }))
    socket.send(JSON.stringify({ type: 'subscribe', channel: 'downloads' }))
    // Populate download store so sidebar badge is accurate from the start
    fetchDownloadQueue()
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

    case 'download:queued':
      // New download created - add to store so sidebar badge updates immediately
      useDownloadStore.getState().addDownload({
        id: data.download_id,
        source: data.source,
        source_url: data.source_url,
        search_query: data.search_query,
        status: 'pending',
        progress: 0
      })
      queryClient.invalidateQueries('downloads')
      break

    case 'download:progress':
      useDownloadStore.getState().updateProgress(
        data.download_id,
        data.percent,
        data.speed,
        data.eta
      )
      break

    case 'download:complete':
      useDownloadStore.getState().updateDownloadStatus(
        data.download_id, 'complete'
      )
      useNotificationStore.getState().addNotification({
        type: 'success',
        message: `Download complete: ${data.album_title || data.title || 'Album'}`
      })
      // Refresh ALL library queries to show new album everywhere
      queryClient.invalidateQueries('user-library')
      queryClient.invalidateQueries('user-library-artists')
      queryClient.invalidateQueries('user-library-artist-albums')
      queryClient.invalidateQueries('user-library-tracks')
      queryClient.invalidateQueries('artists')
      queryClient.invalidateQueries('artist-albums')
      queryClient.invalidateQueries('albums')
      queryClient.invalidateQueries('search-local')
      queryClient.invalidateQueries('downloads')
      break

    case 'download:error':
      useDownloadStore.getState().updateDownloadStatus(
        data.download_id, 'failed', { error_message: data.error }
      )
      useNotificationStore.getState().addNotification({
        type: 'error',
        message: `Download failed: ${data.error || 'Unknown error'}`
      })
      queryClient.invalidateQueries('downloads')
      break

    case 'import:complete':
      useNotificationStore.getState().addNotification({
        type: 'success',
        message: `Import complete: ${data.artist_name} - ${data.album_title}`
      })
      // Refresh ALL library queries to show new album everywhere
      queryClient.invalidateQueries('user-library')
      queryClient.invalidateQueries('user-library-artists')
      queryClient.invalidateQueries('user-library-artist-albums')
      queryClient.invalidateQueries('user-library-tracks')
      queryClient.invalidateQueries('artists')
      queryClient.invalidateQueries('artist-albums')
      queryClient.invalidateQueries('albums')
      queryClient.invalidateQueries('search-local')
      break

    case 'import:review':
      useNotificationStore.getState().addNotification({
        type: 'info',
        message: 'New item needs review'
      })
      break

    case 'library:updated':
      handleLibraryUpdate(data)
      break

    case 'notification':
      useNotificationStore.getState().addNotification(data)
      break
  }
}

function handleLibraryUpdate(data) {
  const { addNotification } = useNotificationStore.getState()

  // Invalidate ALL library queries to refresh data everywhere
  queryClient.invalidateQueries('user-library')
  queryClient.invalidateQueries('user-library-tracks')
  queryClient.invalidateQueries('artists')
  queryClient.invalidateQueries('artist-albums')
  queryClient.invalidateQueries('albums')
  queryClient.invalidateQueries('search-local')

  switch (data.action) {
    case 'created':
    case 'new_album':
      addNotification({
        type: 'success',
        message: `New album added to library`
      })
      break

    case 'quality_upgrade':
      addNotification({
        type: 'success',
        message: `Quality upgrade: ${data.title}`
      })
      break

    case 'deleted':
      // No notification needed, just refresh
      break
  }
}
