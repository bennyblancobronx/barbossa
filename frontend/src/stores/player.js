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

  setVolume: (volume) => set({ volume }),

  clearTrack: () => set({ currentTrack: null, isPlaying: false, progress: 0 })
}))
