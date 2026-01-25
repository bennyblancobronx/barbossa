"""Barbossa CLI - Library commands."""
import typer
from rich.console import Console
from rich.table import Table

from app.cli.auth import get_current_user

app = typer.Typer()
console = Console()


@app.command()
def artists(
    letter: str = typer.Option(None, "--letter", "-l", help="Filter by first letter"),
    page: int = typer.Option(1, "--page", "-p", help="Page number"),
    limit: int = typer.Option(20, "--limit", "-n", help="Items per page"),
):
    """List artists in the library."""
    user, db = get_current_user()
    try:
        from app.services.library import LibraryService

        service = LibraryService(db)
        result = service.list_artists(letter, page, limit)

        table = Table(title=f"Artists (Page {result['page']}, Total: {result['total']})")
        table.add_column("ID", style="dim")
        table.add_column("Name", style="cyan")
        table.add_column("Albums", justify="right")

        for artist in result["items"]:
            album_count = len(artist.albums) if artist.albums else 0
            table.add_row(str(artist.id), artist.name, str(album_count))

        console.print(table)
    finally:
        db.close()


@app.command()
def albums(
    artist_id: int = typer.Option(None, "--artist", "-a", help="Filter by artist ID"),
    letter: str = typer.Option(None, "--letter", "-l", help="Filter by first letter"),
    page: int = typer.Option(1, "--page", "-p", help="Page number"),
    limit: int = typer.Option(20, "--limit", "-n", help="Items per page"),
):
    """List albums in the library."""
    user, db = get_current_user()
    try:
        from app.services.library import LibraryService
        from app.services.user_library import UserLibraryService

        service = LibraryService(db)
        user_lib = UserLibraryService(db)

        result = service.list_albums(artist_id, letter, page, limit)
        hearted_ids = user_lib.get_hearted_album_ids(user.id)

        table = Table(title=f"Albums (Page {result['page']}, Total: {result['total']})")
        table.add_column("ID", style="dim")
        table.add_column("Title", style="cyan")
        table.add_column("Artist")
        table.add_column("Year", justify="right")
        table.add_column("Source")
        table.add_column("Hearted", justify="center")

        for album in result["items"]:
            hearted = "[green]Y[/green]" if album.id in hearted_ids else ""
            artist_name = album.artist.name if album.artist else "Unknown"
            table.add_row(
                str(album.id),
                album.title,
                artist_name,
                str(album.year) if album.year else "",
                album.source or "",
                hearted,
            )

        console.print(table)
    finally:
        db.close()


@app.command()
def tracks(
    album_id: int = typer.Argument(..., help="Album ID"),
):
    """List tracks in an album."""
    user, db = get_current_user()
    try:
        from app.services.library import LibraryService
        from app.services.user_library import UserLibraryService

        service = LibraryService(db)
        user_lib = UserLibraryService(db)

        album = service.get_album(album_id)
        if not album:
            console.print(f"[red]Album {album_id} not found[/red]")
            raise typer.Exit(1)

        tracks = service.get_album_tracks(album_id)
        hearted_ids = user_lib.get_hearted_track_ids(user.id)

        table = Table(title=f"{album.artist.name} - {album.title} ({album.year})")
        table.add_column("#", justify="right", style="dim")
        table.add_column("Title", style="cyan")
        table.add_column("Quality")
        table.add_column("Source")
        table.add_column("Hearted", justify="center")

        for track in tracks:
            hearted = "[green]Y[/green]" if track.id in hearted_ids else ""
            quality = f"{track.bit_depth}/{track.sample_rate//1000}kHz" if track.sample_rate else ""
            if track.is_lossy:
                quality = f"[yellow]{track.bitrate}kbps[/yellow]"

            table.add_row(
                str(track.track_number),
                track.title,
                quality,
                track.source or "",
                hearted,
            )

        console.print(table)
    finally:
        db.close()


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query"),
    type: str = typer.Option("all", "--type", "-t", help="Search type: all, artist, album, track"),
    limit: int = typer.Option(10, "--limit", "-n", help="Results limit"),
):
    """Search the library."""
    user, db = get_current_user()
    try:
        from app.services.library import LibraryService

        service = LibraryService(db)
        results = service.search(query, type, limit)

        if results["artists"]:
            table = Table(title="Artists")
            table.add_column("ID", style="dim")
            table.add_column("Name", style="cyan")
            for artist in results["artists"]:
                table.add_row(str(artist.id), artist.name)
            console.print(table)

        if results["albums"]:
            table = Table(title="Albums")
            table.add_column("ID", style="dim")
            table.add_column("Title", style="cyan")
            table.add_column("Artist")
            for album in results["albums"]:
                artist_name = album.artist.name if album.artist else "Unknown"
                table.add_row(str(album.id), album.title, artist_name)
            console.print(table)

        if results["tracks"]:
            table = Table(title="Tracks")
            table.add_column("ID", style="dim")
            table.add_column("Title", style="cyan")
            table.add_column("Album")
            for track in results["tracks"]:
                album_title = track.album.title if track.album else "Unknown"
                table.add_row(str(track.id), track.title, album_title)
            console.print(table)

        total = len(results["artists"]) + len(results["albums"]) + len(results["tracks"])
        if total == 0:
            console.print("[yellow]No results found[/yellow]")
    finally:
        db.close()


@app.command()
def heart(
    album_id: int = typer.Option(None, "--album", "-a", help="Album ID to heart"),
    track_id: int = typer.Option(None, "--track", "-t", help="Track ID to heart"),
):
    """Add album or track to your library."""
    if not album_id and not track_id:
        console.print("[red]Specify --album or --track[/red]")
        raise typer.Exit(1)

    user, db = get_current_user()
    try:
        from app.services.user_library import UserLibraryService

        service = UserLibraryService(db)

        if album_id:
            try:
                if service.heart_album(user.id, album_id, user.username):
                    console.print(f"[green]Album {album_id} added to your library[/green]")
                else:
                    console.print(f"[yellow]Album {album_id} already in your library[/yellow]")
            except ValueError as e:
                console.print(f"[red]{e}[/red]")
                raise typer.Exit(1)

        if track_id:
            try:
                if service.heart_track(user.id, track_id, user.username):
                    console.print(f"[green]Track {track_id} added to your library[/green]")
                else:
                    console.print(f"[yellow]Track {track_id} already in your library[/yellow]")
            except ValueError as e:
                console.print(f"[red]{e}[/red]")
                raise typer.Exit(1)
    finally:
        db.close()


@app.command()
def unheart(
    album_id: int = typer.Option(None, "--album", "-a", help="Album ID to unheart"),
    track_id: int = typer.Option(None, "--track", "-t", help="Track ID to unheart"),
):
    """Remove album or track from your library."""
    if not album_id and not track_id:
        console.print("[red]Specify --album or --track[/red]")
        raise typer.Exit(1)

    user, db = get_current_user()
    try:
        from app.services.user_library import UserLibraryService

        service = UserLibraryService(db)

        if album_id:
            if service.unheart_album(user.id, album_id, user.username):
                console.print(f"[green]Album {album_id} removed from your library[/green]")
            else:
                console.print(f"[yellow]Album {album_id} was not in your library[/yellow]")

        if track_id:
            if service.unheart_track(user.id, track_id, user.username):
                console.print(f"[green]Track {track_id} removed from your library[/green]")
            else:
                console.print(f"[yellow]Track {track_id} was not in your library[/yellow]")
    finally:
        db.close()


@app.command("my-library")
def my_library(
    page: int = typer.Option(1, "--page", "-p", help="Page number"),
    limit: int = typer.Option(20, "--limit", "-n", help="Items per page"),
):
    """Show your hearted albums."""
    user, db = get_current_user()
    try:
        from app.services.user_library import UserLibraryService

        service = UserLibraryService(db)
        result = service.get_library(user.id, page, limit)

        table = Table(title=f"My Library (Page {result['page']}, Total: {result['total']})")
        table.add_column("ID", style="dim")
        table.add_column("Title", style="cyan")
        table.add_column("Artist")
        table.add_column("Year", justify="right")

        for album in result["items"]:
            artist_name = album.artist.name if album.artist else "Unknown"
            table.add_row(
                str(album.id),
                album.title,
                artist_name,
                str(album.year) if album.year else "",
            )

        console.print(table)

        if result["total"] == 0:
            console.print("[yellow]Your library is empty. Use 'barbossa library heart' to add albums.[/yellow]")
    finally:
        db.close()
