import { NavLink } from 'react-router-dom'
import { useAuthStore } from '../stores/auth'
import { useThemeStore } from '../stores/theme'

export default function Sidebar() {
  const { user, logout } = useAuthStore()
  const { theme, toggleTheme } = useThemeStore()

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <h1 className="text-2xl">barbossa</h1>
      </div>

      <nav className="sidebar-nav">
        <NavLink to="/" end className={({ isActive }) =>
          `nav-link ${isActive ? 'is-active' : ''}`
        }>
          Master Library
        </NavLink>

        <NavLink to="/my-library" className={({ isActive }) =>
          `nav-link ${isActive ? 'is-active' : ''}`
        }>
          My Library
        </NavLink>

        <NavLink to="/downloads" className={({ isActive }) =>
          `nav-link ${isActive ? 'is-active' : ''}`
        }>
          Downloads
        </NavLink>

        {user?.is_admin && (
          <NavLink to="/settings" className={({ isActive }) =>
            `nav-link ${isActive ? 'is-active' : ''}`
          }>
            Settings
          </NavLink>
        )}
      </nav>

      <div className="sidebar-footer">
        <div className="sidebar-footer-row">
          <span className="text-muted text-sm">{user?.username}</span>
          <button onClick={logout} className="btn-ghost text-sm">
            Logout
          </button>
        </div>
        <button onClick={toggleTheme} className="theme-toggle" title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}>
          {theme === 'dark' ? <SunIcon /> : <MoonIcon />}
          <span className="text-sm">{theme === 'dark' ? 'Light' : 'Dark'} Mode</span>
        </button>
      </div>
    </aside>
  )
}

function SunIcon() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" fill="none" strokeWidth="2">
      <circle cx="12" cy="12" r="5" />
      <line x1="12" y1="1" x2="12" y2="3" />
      <line x1="12" y1="21" x2="12" y2="23" />
      <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
      <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
      <line x1="1" y1="12" x2="3" y2="12" />
      <line x1="21" y1="12" x2="23" y2="12" />
      <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
      <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
    </svg>
  )
}

function MoonIcon() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" fill="none" strokeWidth="2">
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
    </svg>
  )
}
