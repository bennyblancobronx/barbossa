import { create } from 'zustand'
import { persist } from 'zustand/middleware'

// Apply theme to document
function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme)
}

// Detect system preference
function getSystemTheme() {
  if (typeof window !== 'undefined' && window.matchMedia) {
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  }
  return 'dark'
}

export const useThemeStore = create(
  persist(
    (set, get) => ({
      theme: 'dark',

      setTheme: (theme) => {
        applyTheme(theme)
        set({ theme })
      },

      toggleTheme: () => {
        const newTheme = get().theme === 'dark' ? 'light' : 'dark'
        applyTheme(newTheme)
        set({ theme: newTheme })
      },

      initTheme: () => {
        const theme = get().theme || getSystemTheme()
        applyTheme(theme)
      }
    }),
    {
      name: 'barbossa-theme',
      onRehydrateStorage: () => (state) => {
        // Apply theme after rehydration from localStorage
        if (state?.theme) {
          applyTheme(state.theme)
        }
      }
    }
  )
)
