import { useNotificationStore } from '../stores/notifications'

export default function ToastContainer() {
  const { notifications, removeNotification } = useNotificationStore()

  return (
    <div className="toast-container">
      {notifications.map(notification => (
        <div
          key={notification.id}
          className={`toast toast-${notification.type}`}
        >
          <span className="toast-message">{notification.message}</span>
          <button
            className="toast-close"
            onClick={() => removeNotification(notification.id)}
          >
            <CloseIcon />
          </button>
        </div>
      ))}
    </div>
  )
}

function CloseIcon() {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" fill="none" strokeWidth="2">
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  )
}
