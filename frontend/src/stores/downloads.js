import { create } from 'zustand'

export const useDownloadStore = create((set) => ({
  downloads: [],

  setDownloads: (downloads) => set({ downloads }),

  updateProgress: (id, percent, speed, eta) => {
    set(state => ({
      downloads: state.downloads.map(d =>
        d.id === id ? { ...d, progress: percent, speed, eta, status: 'downloading' } : d
      )
    }))
  },

  updateDownloadStatus: (id, status, extra = {}) => {
    set(state => ({
      downloads: state.downloads.map(d =>
        d.id === id ? { ...d, status, ...extra } : d
      )
    }))
  },

  addDownload: (download) => {
    set(state => ({
      downloads: state.downloads.some(d => d.id === download.id)
        ? state.downloads
        : [download, ...state.downloads]
    }))
  },

  removeDownload: (id) => {
    set(state => ({
      downloads: state.downloads.filter(d => d.id !== id)
    }))
  }
}))
