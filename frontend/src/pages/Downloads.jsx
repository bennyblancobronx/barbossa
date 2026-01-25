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

  // Search Qobuz
  const { data: searchResults, isLoading: isSearching, refetch: doSearch } = useQuery(
    ['qobuz-search', searchQuery, searchType],
    () => api.searchQobuz(searchQuery, searchType).then(r => r.data.items || r.data || []),
    { enabled: false }
  )

  // Download mutations
  const downloadQobuz = useMutation(
    (url) => api.downloadQobuz(url, 4, searchType),
    {
      onSuccess: () => {
        addNotification({ type: 'success', message: 'Download started' })
        queryClient.invalidateQueries('downloads')
      },
      onError: (error) => {
        addNotification({ type: 'error', message: error.response?.data?.detail || 'Download failed' })
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
        <p className="text-muted">Temporary staging - imports land in master library</p>
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
            {isSearching ? 'Searching...' : 'Search'}
          </button>
        </form>

        {searchResults && searchResults.length > 0 && (
          <div className="search-results">
            {searchResults.map(result => (
              <div key={result.id} className="search-result-item">
                <div className="search-result-info">
                  <span className="search-result-title">{result.title}</span>
                  <span className="search-result-artist">{result.artist || result.artist_name}</span>
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
        <h2 className="text-lg">Download Queue</h2>

        {downloads.length === 0 ? (
          <p className="text-muted">No downloads in progress</p>
        ) : (
          <div className="download-queue">
            {downloads.map(download => (
              <DownloadItem
                key={download.id}
                download={download}
                onCancel={() => cancelDownload.mutate(download.id)}
              />
            ))}
          </div>
        )}
      </section>
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
    failed: 'text-error',
    cancelled: 'text-muted'
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

        {download.error_message && (
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
