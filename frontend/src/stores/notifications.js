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
