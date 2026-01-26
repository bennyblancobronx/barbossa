import ArtistCard from './ArtistCard'

export default function ArtistGrid({ artists, onArtistClick, onArtistDelete }) {
  if (!artists.length) {
    return (
      <div className="empty-state">
        <p className="text-muted">No artists found</p>
      </div>
    )
  }

  return (
    <div className="album-grid">
      {artists.map(artist => (
        <ArtistCard
          key={artist.id}
          artist={artist}
          onClick={() => onArtistClick(artist)}
          onDelete={onArtistDelete}
        />
      ))}
    </div>
  )
}
