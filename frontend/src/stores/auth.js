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
