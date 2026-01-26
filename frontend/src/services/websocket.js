import { useAuthStore } from '../stores/auth'
import { useNotificationStore } from '../stores/notifications'
import { useDownloadStore } from '../stores/downloads'
import { queryClient } from '../queryClient'

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
    socket.send(JSON.stringify({ type: 'subscribe', channel: 'library' }))
    socket.send(JSON.stringify({ type: 'subscribe', channel: 'downloads' }))
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

    case 'download:progress':
      useDownloadStore.getState().updateProgress(
        data.download_id,
        data.percent,
        data.speed,
        data.eta
      )
      break

    case 'download:complete':
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
      useNotificationStore.getState().addNotification({
        type: 'error',
        message: `Download failed: ${data.error || 'Unknown error'}`
      })
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
