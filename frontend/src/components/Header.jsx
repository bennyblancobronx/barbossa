import { useLocation } from 'react-router-dom'

const pageTitles = {
  '/': 'Master Library',
  '/search': 'Search',
  '/my-library': 'My Library',
  '/downloads': 'Downloads',
  '/settings': 'Settings'
}

export default function Header() {
  const location = useLocation()
  const basePath = '/' + (location.pathname.split('/')[1] || '')
  const title = pageTitles[basePath] || 'Barbossa'

  return (
    <header className="app-header">
      <div className="header-left">
        <h2 className="header-title">{title}</h2>
      </div>
      <div className="header-right">
        {/* Search moved to sidebar */}
      </div>
    </header>
  )
}
