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


@app.command("rebuild-symlinks")
def rebuild_symlinks(
    user: str = typer.Option(None, "--user", "-u", help="Rebuild for specific user only"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be done without changing"),
):
    """Regenerate all user library symlinks from database.

    Recreates symlinks for all hearted albums/tracks based on database records.
    Use this to fix missing or broken symlinks.
    """
    from pathlib import Path
    import shutil
    from app.config import settings
    from app.database import SessionLocal
    from app.models.user import User
    from app.models.album import Album
    from app.models.user_library import user_albums
    from app.services.symlink import SymlinkService
    from sqlalchemy import select

    db = SessionLocal()
    symlink_service = SymlinkService()

    try:
        users_path = Path(settings.music_users)

        # Get users to process
        if user:
            users = db.query(User).filter(User.username == user).all()
            if not users:
                console.print(f"[red]User not found: {user}[/red]")
                raise typer.Exit(1)
        else:
            users = db.query(User).all()

        total_albums = 0
        total_created = 0

        for u in users:
            console.print(f"\n[cyan]Processing user: {u.username}[/cyan]")

            # Get hearted albums for this user
            hearted = db.execute(
                select(user_albums.c.album_id).where(user_albums.c.user_id == u.id)
            ).fetchall()

            album_ids = [row[0] for row in hearted]
            albums = db.query(Album).filter(Album.id.in_(album_ids)).all() if album_ids else []

            console.print(f"  Found {len(albums)} hearted albums")
            total_albums += len(albums)

            for album in albums:
                if not album.path:
                    console.print(f"  [yellow]Skip (no path): {album.title}[/yellow]")
                    continue

                if dry_run:
                    console.print(f"  Would rebuild: {album.title}")
                else:
                    # Remove existing symlinks for this album
                    try:
                        source = Path(album.path)
                        relative = source.relative_to(Path(settings.music_library))
                        dest = users_path / u.username / relative
                        if dest.exists():
                            shutil.rmtree(dest)
                    except (ValueError, Exception):
                        pass

                    # Recreate symlinks
                    symlink_service.create_album_links(u.username, album.path)
                    console.print(f"  [green]Rebuilt:[/green] {album.title}")
                    total_created += 1

        console.print(f"\n[bold]Summary:[/bold]")
        if dry_run:
            console.print(f"  Would rebuild: {total_albums} albums")
        else:
            console.print(f"  Rebuilt: {total_created} albums")

    finally:
        db.close()


@app.command("fix-symlinks")
def fix_symlinks(
    user: str = typer.Option(None, "--user", "-u", help="Fix symlinks for specific user only"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be fixed without changing"),
):
    """Convert absolute symlinks to relative paths.

    Fixes Plex not recognizing symlinks by converting absolute paths to relative.
    For missing symlinks, use 'rebuild-symlinks' instead.
    """
    from pathlib import Path
    import os
    from app.config import settings
    from app.database import SessionLocal
    from app.models.user import User

    db = SessionLocal()
    try:
        users_path = Path(settings.music_users)
        library_path = Path(settings.music_library)

        if not users_path.exists():
            console.print(f"[red]Users path does not exist: {users_path}[/red]")
            raise typer.Exit(1)

        # Get users to process
        if user:
            users = db.query(User).filter(User.username == user).all()
            if not users:
                console.print(f"[red]User not found: {user}[/red]")
                raise typer.Exit(1)
        else:
            users = db.query(User).all()

        total_fixed = 0
        total_errors = 0

        for u in users:
            user_lib_path = users_path / u.username
            if not user_lib_path.exists():
                continue

            console.print(f"\n[cyan]Processing user: {u.username}[/cyan]")

            # Find all symlinks in user's library
            for root, dirs, files in os.walk(user_lib_path):
                for filename in files:
                    filepath = Path(root) / filename

                    # Skip non-symlinks (hardlinks don't need fixing)
                    if not filepath.is_symlink():
                        continue

                    target = os.readlink(filepath)

                    # Skip already-relative symlinks
                    if not os.path.isabs(target):
                        continue

                    # Convert to relative
                    try:
                        relative_target = os.path.relpath(target, filepath.parent)

                        if dry_run:
                            console.print(f"  Would fix: {filepath.name}")
                            console.print(f"    From: {target}")
                            console.print(f"    To:   {relative_target}")
                        else:
                            # Remove old symlink and create new one
                            filepath.unlink()
                            os.symlink(relative_target, filepath)
                            console.print(f"  [green]Fixed:[/green] {filepath.name}")

                        total_fixed += 1
                    except Exception as e:
                        console.print(f"  [red]Error fixing {filepath}: {e}[/red]")
                        total_errors += 1

        console.print(f"\n[bold]Summary:[/bold]")
        if dry_run:
            console.print(f"  Would fix: {total_fixed} symlinks")
        else:
            console.print(f"  Fixed: {total_fixed} symlinks")
        if total_errors:
            console.print(f"  [red]Errors: {total_errors}[/red]")

        if total_fixed > 0 and not dry_run:
            console.print("\n[yellow]Trigger a Plex library scan to pick up the changes.[/yellow]")

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


@app.command("backfill-years")
def backfill_years(
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Show what would be done without making changes"),
):
    """Backfill missing album years from folder names, file metadata, MusicBrainz, and Qobuz.

    Finds all albums with NULL or 0 year and tries to recover from:
    1. Folder name pattern (YYYY) -- fast, no IO
    2. ExifTool re-read of audio files
    3. Beets/MusicBrainz lookup
    4. Qobuz API search -- searches by artist + album title
    """
    import asyncio
    import re
    from pathlib import Path
    from app.database import SessionLocal
    from app.models.album import Album

    db = SessionLocal()
    try:
        from sqlalchemy import or_
        albums = db.query(Album).filter(or_(Album.year.is_(None), Album.year == 0)).all()
        console.print(f"Found {len(albums)} albums with missing year")

        if not albums:
            return

        fixed_folder = 0
        fixed_exiftool = 0
        fixed_beets = 0
        fixed_qobuz = 0
        failed = 0

        async def process():
            nonlocal fixed_folder, fixed_exiftool, fixed_beets, fixed_qobuz, failed
            from app.integrations.exiftool import ExifToolClient
            from app.integrations.beets import BeetsClient
            from app.integrations.qobuz_api import get_qobuz_api

            exiftool = ExifToolClient()
            beets = BeetsClient()
            qobuz = get_qobuz_api()

            for album in albums:
                album_path = Path(album.path) if album.path else None
                artist_name = album.artist.name if album.artist else None

                # 1. Try folder name
                if album_path:
                    match = re.search(r'\((\d{4})\)', album_path.name)
                    if match:
                        year = int(match.group(1))
                        if dry_run:
                            console.print(f"  [folder] {album.title} -> {year}")
                        else:
                            album.year = year
                        fixed_folder += 1
                        continue

                # 2. Try ExifTool re-read
                if album_path and album_path.exists():
                    try:
                        tracks_meta = await exiftool.get_album_metadata(album_path)
                        if tracks_meta and tracks_meta[0].get("year"):
                            year = tracks_meta[0]["year"]
                            if dry_run:
                                console.print(f"  [exiftool] {album.title} -> {year}")
                            else:
                                album.year = year
                            fixed_exiftool += 1
                            continue
                    except Exception:
                        pass

                    # 3. Try beets/MusicBrainz lookup
                    try:
                        identification = await beets.identify(album_path)
                        beets_year = identification.get("year")
                        if beets_year and int(beets_year) >= 1000:
                            year = int(beets_year)
                            if dry_run:
                                console.print(f"  [musicbrainz] {album.title} -> {year}")
                            else:
                                album.year = year
                            fixed_beets += 1
                            continue
                    except Exception:
                        pass

                # 4. Try Qobuz API search (works even if path is missing)
                if artist_name:
                    try:
                        query = f"{artist_name} {album.title}"
                        results = await qobuz.search_albums(query, limit=5)
                        found = False
                        for r in results:
                            if artist_name.lower() in r.get("artist_name", "").lower():
                                qobuz_year = r.get("year")
                                if qobuz_year:
                                    parsed = int(str(qobuz_year)[:4])
                                    if 1000 <= parsed <= 9999:
                                        if dry_run:
                                            console.print(f"  [qobuz] {album.title} -> {parsed}")
                                        else:
                                            album.year = parsed
                                        fixed_qobuz += 1
                                        found = True
                                        break
                        if found:
                            continue
                    except Exception:
                        pass

                failed += 1
                console.print(f"  [unknown] {album.title} -- no year found")

        asyncio.run(process())

        if not dry_run:
            db.commit()

        console.print(f"\nResults:")
        console.print(f"  From folder name: {fixed_folder}")
        console.print(f"  From file metadata: {fixed_exiftool}")
        console.print(f"  From MusicBrainz: {fixed_beets}")
        console.print(f"  From Qobuz API: {fixed_qobuz}")
        console.print(f"  Could not determine: {failed}")
        if dry_run:
            console.print("\n[yellow]Dry run -- no changes made[/yellow]")
    finally:
        db.close()
