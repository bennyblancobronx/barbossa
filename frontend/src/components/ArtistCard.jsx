export default function ArtistCard({ artist, onClick }) {
  // Use first letter of name as placeholder
  const initial = (artist.name || 'A')[0].toUpperCase()

  return (
    <div className="album-card" onClick={onClick}>
      <div className="album-card-artwork">
        {artist.artwork_path ? (
          <img src={`/api/artists/${artist.id}/artwork`} alt={artist.name} />
        ) : (
          <div className="artwork-placeholder">
            <span>{initial}</span>
          </div>
        )}
      </div>

      <div className="album-card-info">
        <h3 className="album-card-title">{artist.name}</h3>
      </div>
    </div>
  )
}
