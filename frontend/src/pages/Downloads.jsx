import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from 'react-query'
import { useSearchParams } from 'react-router-dom'
import * as api from '../services/api'
import { useDownloadStore } from '../stores/downloads'
import { useNotificationStore } from '../stores/notifications'

export default function Downloads() {
  const [searchParams] = useSearchParams()
  const initialUrl = searchParams.get('url') || ''
  const [urlInput, setUrlInput] = useState(initialUrl)

  const queryClient = useQueryClient()
  const { addNotification } = useNotificationStore()
  const downloads = useDownloadStore(state => state.downloads)

  // Fetch download queue
  useQuery(
    'downloads',
    () => api.getDownloads().then(r => r.data),
    {
      onSuccess: (data) => {
        useDownloadStore.getState().setDownloads(data.items || data || [])
      },
      refetchInterval: 5000
    }
  )

  // Download mutations
  const downloadUrl = useMutation(
    ({ url, confirmLossy }) => api.downloadUrl(url, confirmLossy),
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
        } else {
          addNotification({ type: 'error', message: error.response?.data?.detail || 'Download failed' })
        }
      }
    }
  )

  const cancelDownload = useMutation(
    (id) => api.cancelDownload(id),
    {
      onSuccess: () => {
        queryClient.invalidateQueries('downloads')
      }
    }
  )

  const retryDownload = useMutation(
    (id) => api.retryDownload(id),
    {
      onSuccess: () => {
        addNotification({ type: 'success', message: 'Retrying download' })
        queryClient.invalidateQueries('downloads')
      },
      onError: (error) => {
        addNotification({ type: 'error', message: error.response?.data?.detail || 'Retry failed' })
      }
    }
  )

  const dismissDownload = useMutation(
    (id) => api.dismissDownload(id),
    {
      onSuccess: () => {
        queryClient.invalidateQueries('downloads')
      }
    }
  )

  // Separate active downloads from failed ones
  const activeDownloads = downloads.filter(d => d.status !== 'failed')
  const failedDownloads = downloads.filter(d => d.status === 'failed')

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
        <p className="text-muted">Temporary staging - imports land in master library</p>
      </header>

      <section className="download-section">
        <h2 className="text-lg">Download from URL</h2>
        <p className="text-sm text-muted">YouTube, Bandcamp, Soundcloud, and 1800+ other sites</p>

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
        <h2 className="text-lg">Lidarr Request</h2>
        <p className="text-sm text-muted">Request albums via Lidarr for automated monitoring</p>

        <LidarrSearch />
      </section>

      <section className="download-section">
        <h2 className="text-lg">Download Queue</h2>

        {activeDownloads.length === 0 ? (
          <p className="text-muted">No downloads in progress</p>
        ) : (
          <div className="download-queue">
            {activeDownloads.map(download => (
              <DownloadItem
                key={download.id}
                download={download}
                onCancel={() => cancelDownload.mutate(download.id)}
              />
            ))}
          </div>
        )}
      </section>

      {failedDownloads.length > 0 && (
        <section className="download-section">
          <h2 className="text-lg">Failed Downloads</h2>
          <p className="text-sm text-muted">Downloads that encountered errors</p>

          <div className="download-queue failed-downloads">
            {failedDownloads.map(download => (
              <FailedDownloadItem
                key={download.id}
                download={download}
                onRetry={() => retryDownload.mutate(download.id)}
                onDismiss={() => dismissDownload.mutate(download.id)}
                isRetrying={retryDownload.isLoading}
              />
            ))}
          </div>
        </section>
      )}
    </div>
  )
}

function LidarrSearch() {
  const [searchQuery, setSearchQuery] = useState('')
  const { addNotification } = useNotificationStore()

  const { data: searchResults, isLoading, refetch } = useQuery(
    ['lidarr-search', searchQuery],
    () => api.searchLidarr(searchQuery).then(r => r.data.items || r.data || []),
    { enabled: false }
  )

  const addToLidarr = useMutation(
    ({ mbid, name }) => api.addArtistToLidarr(mbid, name),
    {
      onSuccess: () => {
        addNotification({ type: 'success', message: 'Artist added to Lidarr' })
      },
      onError: (error) => {
        addNotification({ type: 'error', message: error.response?.data?.detail || 'Failed to add artist' })
      }
    }
  )

  const handleSearch = (e) => {
    e.preventDefault()
    if (searchQuery.trim()) {
      refetch()
    }
  }

  return (
    <div>
      <form onSubmit={handleSearch} className="search-form">
        <input
          type="text"
          value={searchQuery}
          onChange={e => setSearchQuery(e.target.value)}
          placeholder="Search artist to add..."
          className="input-default"
        />
        <button type="submit" className="btn-secondary" disabled={isLoading}>
          {isLoading ? 'Searching...' : 'Search Lidarr'}
        </button>
      </form>

      {searchResults && searchResults.length > 0 && (
        <div className="search-results">
          {searchResults.map(result => (
            <div key={result.mbid || result.id} className="search-result-item">
              <div className="search-result-info">
                <span className="search-result-title">{result.artistName || result.name}</span>
                {result.overview && (
                  <span className="search-result-meta text-sm text-muted">
                    {result.overview.slice(0, 100)}...
                  </span>
                )}
              </div>
              <button
                className="btn-secondary"
                onClick={() => addToLidarr.mutate({
                  mbid: result.foreignArtistId || result.mbid,
                  name: result.artistName || result.name
                })}
                disabled={addToLidarr.isLoading}
              >
                Add to Lidarr
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function DownloadItem({ download, onCancel }) {
  const statusColors = {
    pending: 'text-muted',
    downloading: 'text-primary',
    processing: 'text-primary',
    importing: 'text-primary',
    complete: 'text-success',
    duplicate: 'text-warning',
    failed: 'text-error',
    cancelled: 'text-muted',
    pending_review: 'text-warning'
  }

  return (
    <div className="download-item">
      <div className="download-item-info">
        <span className="download-item-source badge">{download.source}</span>
        <span className="download-item-url">{download.search_query || download.source_url}</span>
      </div>

      <div className="download-item-status">
        <span className={statusColors[download.status] || 'text-muted'}>
          {download.status}
        </span>

        {download.status === 'downloading' && (
          <div className="download-progress">
            <div className="progress-bar">
              <div
                className="progress-fill"
                style={{ width: `${download.progress || 0}%` }}
              />
            </div>
            {download.speed && <span className="download-speed">{download.speed}</span>}
            {download.eta && <span className="download-eta">{download.eta}</span>}
          </div>
        )}

        {download.status === 'pending_review' && (
          <span className="download-review text-warning">
            {download.error_message || 'Needs manual review - low confidence match'}
          </span>
        )}

        {download.status === 'duplicate' && (
          <span className="download-review text-warning">
            Duplicate detected - kept existing album
          </span>
        )}

        {download.error_message && download.status !== 'pending_review' && (
          <span className="download-error text-error">{download.error_message}</span>
        )}
      </div>

      {['pending', 'downloading'].includes(download.status) && (
        <button
          className="btn-ghost text-error"
          onClick={onCancel}
        >
          Cancel
        </button>
      )}
    </div>
  )
}

function FailedDownloadItem({ download, onRetry, onDismiss, isRetrying }) {
  return (
    <div className="download-item failed-download-item">
      <div className="download-item-info">
        <span className="download-item-source badge badge-error">{download.source}</span>
        <span className="download-item-url">{download.search_query || download.source_url}</span>
      </div>

      <div className="download-item-status">
        <div className="failed-reason">
          <span className="failed-label text-error">Failed</span>
          <span className="failed-message text-muted">
            {download.error_message || 'Unknown error'}
          </span>
        </div>
        {download.completed_at && (
          <span className="failed-time text-muted">
            {new Date(download.completed_at).toLocaleString()}
          </span>
        )}
      </div>

      <div className="download-actions">
        <button
          className="btn-secondary btn-sm"
          onClick={onRetry}
          disabled={isRetrying}
        >
          Retry
        </button>
        <button
          className="btn-ghost btn-sm"
          onClick={onDismiss}
        >
          Dismiss
        </button>
      </div>
    </div>
  )
}
