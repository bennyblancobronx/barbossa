import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import SearchBar from './SearchBar'

export default function Header() {
  const [searchQuery, setSearchQuery] = useState('')
  const navigate = useNavigate()

  const handleSearch = (query) => {
    setSearchQuery(query)
    if (query) {
      navigate(`/?q=${encodeURIComponent(query)}`)
    } else {
      navigate('/')
    }
  }

  return (
    <header className="app-header">
      <div className="header-left">
        {/* Breadcrumbs or page title can go here */}
      </div>

      <div className="header-right">
        <SearchBar
          value={searchQuery}
          onChange={handleSearch}
          placeholder="Search library..."
        />
      </div>
    </header>
  )
}
