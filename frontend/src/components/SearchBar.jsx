import { useState, useCallback } from 'react'
import { debounce } from '../utils/debounce'

export default function SearchBar({
  value,
  onChange,
  placeholder = 'Search...',
  debounceMs = 300
}) {
  const [localValue, setLocalValue] = useState(value || '')

  const debouncedOnChange = useCallback(
    debounce((val) => onChange(val), debounceMs),
    [onChange, debounceMs]
  )

  const handleChange = (e) => {
    const newValue = e.target.value
    setLocalValue(newValue)
    debouncedOnChange(newValue)
  }

  const handleClear = () => {
    setLocalValue('')
    onChange('')
  }

  return (
    <div className="search-bar">
      <SearchIcon />
      <input
        type="text"
        value={localValue}
        onChange={handleChange}
        placeholder={placeholder}
        className="search-input"
      />
      {localValue && (
        <button className="search-clear" onClick={handleClear}>
          <CloseIcon />
        </button>
      )}
    </div>
  )
}

function SearchIcon() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" fill="none" strokeWidth="2">
      <circle cx="11" cy="11" r="8" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
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
