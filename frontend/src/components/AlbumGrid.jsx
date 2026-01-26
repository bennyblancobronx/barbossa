import AlbumCard from './AlbumCard'

export default function AlbumGrid({ albums, onAlbumClick, onAlbumDelete }) {
  if (!albums.length) {
    return (
      <div className="empty-state">
        <p className="text-muted">No albums found</p>
      </div>
    )
  }

  return (
    <div className="album-grid">
      {albums.map(album => (
        <AlbumCard
          key={album.id}
          album={album}
          onClick={() => onAlbumClick(album)}
          onDelete={onAlbumDelete}
        />
      ))}
    </div>
  )
}
