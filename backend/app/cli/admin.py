"""Barbossa CLI - Admin commands."""
import typer
from rich.console import Console
from rich.table import Table
from rich.prompt import Confirm

from app.cli.auth import get_current_user

app = typer.Typer()
console = Console()


@app.command("create-user")
def create_user(
    username: str = typer.Argument(..., help="Username for new user"),
    password: str = typer.Option(None, "--password", "-p", help="Password (will prompt if not provided)"),
):
    """Create a new user."""
    from app.database import SessionLocal
    from app.services.auth import AuthService
    from app.models.user import User

    db = SessionLocal()
    try:
        auth_service = AuthService(db)

        # Check if username exists
        existing = db.query(User).filter(User.username == username).first()
        if existing:
            console.print(f"[red]Username '{username}' already exists[/red]")
            raise typer.Exit(1)

        # Get password
        if not password:
            password = typer.prompt("Password", hide_input=True)
            password_confirm = typer.prompt("Confirm password", hide_input=True)
            if password != password_confirm:
                console.print("[red]Passwords do not match[/red]")
                raise typer.Exit(1)

        # Create user
        user = auth_service.create_user(username, password)

        console.print(f"[green]User '{username}' created successfully[/green]")
    finally:
        db.close()


@app.command("list-users")
def list_users():
    """List all users."""
    from app.database import SessionLocal
    from app.models.user import User

    db = SessionLocal()
    try:
        users = db.query(User).order_by(User.username).all()

        table = Table(title="Users")
        table.add_column("ID", style="dim")
        table.add_column("Username", style="cyan")
        table.add_column("Created")

        for u in users:
            table.add_row(
                str(u.id),
                u.username,
                str(u.created_at.date()) if u.created_at else "",
            )

        console.print(table)
    finally:
        db.close()


@app.command("delete-user")
def delete_user(
    username: str = typer.Argument(..., help="Username to delete"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """Delete a user."""
    from app.database import SessionLocal
    from app.models.user import User

    db = SessionLocal()
    try:
        target = db.query(User).filter(User.username == username).first()
        if not target:
            console.print(f"[red]User '{username}' not found[/red]")
            raise typer.Exit(1)

        if not force:
            if not Confirm.ask(f"Delete user '{username}'?"):
                console.print("Cancelled")
                return

        db.delete(target)
        db.commit()

        console.print(f"[green]User '{username}' deleted[/green]")
    finally:
        db.close()


@app.command("rescan")
def rescan(
    path: str = typer.Option(None, "--path", "-p", help="Specific path to scan (defaults to library root)"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Show what would be done without making changes"),
):
    """Rescan the music library and update database."""
    import asyncio
    from pathlib import Path as PathLib
    from app.config import settings
    from app.database import SessionLocal
    from app.integrations.beets import BeetsClient
    from app.integrations.exiftool import ExifToolClient
    from app.services.import_service import ImportService
    from app.services.library import LibraryService

    scan_path = PathLib(path) if path else PathLib(settings.music_library)

    if not scan_path.exists():
        console.print(f"[red]Path not found: {scan_path}[/red]")
        raise typer.Exit(1)

    console.print(f"Scanning: {scan_path}")

    db = SessionLocal()
    try:
        library_service = LibraryService(db)
        import_service = ImportService(db)
        beets = BeetsClient()
        exiftool = ExifToolClient()

        # Find all album directories (contain audio files)
        audio_extensions = {".flac", ".mp3", ".m4a", ".ogg", ".wav", ".aiff"}
        albums_found = []
        albums_new = []
        albums_existing = []

        for artist_dir in scan_path.iterdir():
            if not artist_dir.is_dir():
                continue

            for album_dir in artist_dir.iterdir():
                if not album_dir.is_dir():
                    continue

                has_audio = any(
                    f.suffix.lower() in audio_extensions
                    for f in album_dir.iterdir()
                    if f.is_file()
                )

                if has_audio:
                    albums_found.append(album_dir)

        console.print(f"Found {len(albums_found)} album directories")

        if dry_run:
            console.print("\n[yellow]Dry run - no changes will be made[/yellow]")

        with console.status("Processing albums...") as status:
            for i, album_dir in enumerate(albums_found):
                status.update(f"Processing {i+1}/{len(albums_found)}: {album_dir.name}")

                # Check if already in database
                from app.models.album import Album
                existing = db.query(Album).filter(Album.path == str(album_dir)).first()

                if existing:
                    albums_existing.append(album_dir)
                    continue

                albums_new.append(album_dir)

                if dry_run:
                    continue

                # Import new album
                try:
                    async def do_import():
                        identification = await beets.identify(album_dir)
                        tracks_metadata = await exiftool.get_album_metadata(album_dir)

                        await import_service.import_album(
                            path=album_dir,
                            tracks_metadata=tracks_metadata,
                            source="rescan",
                            source_url="",
                            confidence=identification.get("confidence", 0.5)
                        )

                    asyncio.run(do_import())
                except Exception as e:
                    console.print(f"[red]Failed to import {album_dir.name}: {e}[/red]")

        console.print(f"\n[green]Scan complete[/green]")
        console.print(f"  Total albums: {len(albums_found)}")
        console.print(f"  Already in DB: {len(albums_existing)}")
        console.print(f"  New albums: {len(albums_new)}")

        if dry_run and albums_new:
            console.print("\n[yellow]New albums that would be imported:[/yellow]")
            for album in albums_new[:20]:
                console.print(f"  - {album.parent.name} / {album.name}")
            if len(albums_new) > 20:
                console.print(f"  ... and {len(albums_new) - 20} more")

    finally:
        db.close()


@app.command("import")
def import_album(
    path: str = typer.Argument(..., help="Path to album folder to import"),
    artist: str = typer.Option(None, "--artist", "-a", help="Override artist name"),
    album: str = typer.Option(None, "--album", "-A", help="Override album name"),
    year: int = typer.Option(None, "--year", "-y", help="Override year"),
    copy: bool = typer.Option(False, "--copy", "-c", help="Copy files instead of moving"),
    force: bool = typer.Option(False, "--force", "-f", help="Import even if duplicate detected"),
):
    """Import an album from a folder into the library."""
    import asyncio
    from pathlib import Path as PathLib
    from app.config import settings
    from app.database import SessionLocal
    from app.integrations.beets import BeetsClient
    from app.integrations.exiftool import ExifToolClient
    from app.services.import_service import ImportService

    folder = PathLib(path)
    if not folder.exists():
        console.print(f"[red]Path not found: {folder}[/red]")
        raise typer.Exit(1)

    if not folder.is_dir():
        console.print(f"[red]Not a directory: {folder}[/red]")
        raise typer.Exit(1)

    # Check for audio files
    audio_extensions = {".flac", ".mp3", ".m4a", ".ogg", ".wav", ".aiff"}
    audio_files = [f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in audio_extensions]

    if not audio_files:
        console.print(f"[red]No audio files found in {folder}[/red]")
        raise typer.Exit(1)

    console.print(f"Found {len(audio_files)} audio files")

    db = SessionLocal()
    try:
        beets = BeetsClient()
        exiftool = ExifToolClient()
        import_service = ImportService(db)

        async def do_import():
            # Identify album
            console.print("Identifying album...")
            if artist and album:
                identification = {"artist": artist, "album": album, "year": year, "confidence": 1.0}
            else:
                identification = await beets.identify(folder)

            detected_artist = identification.get("artist") or "Unknown Artist"
            detected_album = identification.get("album") or folder.name
            detected_year = identification.get("year")
            confidence = identification.get("confidence", 0)

            console.print(f"  Artist: {detected_artist}")
            console.print(f"  Album: {detected_album}")
            console.print(f"  Year: {detected_year or 'Unknown'}")
            console.print(f"  Confidence: {confidence:.0%}")

            # Check for duplicates
            existing = import_service.find_duplicate(detected_artist, detected_album)
            if existing and not force:
                console.print(f"\n[yellow]Duplicate detected: Album already exists (ID: {existing.id})[/yellow]")
                console.print(f"  Path: {existing.path}")
                console.print("Use --force to import anyway")
                return None

            # Import via beets
            console.print("\nImporting...")
            if artist or album:
                library_path = await beets.import_with_metadata(
                    folder,
                    artist=artist or detected_artist,
                    album=album or detected_album,
                    year=year or detected_year,
                    move=not copy
                )
            else:
                library_path = await beets.import_album(folder, move=not copy)

            console.print(f"  Imported to: {library_path}")

            # Extract metadata and save to database
            console.print("Extracting metadata...")
            tracks_metadata = await exiftool.get_album_metadata(library_path)

            imported = await import_service.import_album(
                path=library_path,
                tracks_metadata=tracks_metadata,
                source="cli",
                source_url="",
                confidence=confidence
            )

            return imported

        result = asyncio.run(do_import())

        if result:
            console.print(f"\n[green]Import complete![/green]")
            console.print(f"  Album ID: {result.id}")
            console.print(f"  Tracks: {result.total_tracks}")
            if result.artwork_path:
                console.print(f"  Artwork: Found")
            else:
                console.print(f"  Artwork: [yellow]Not found[/yellow]")

    except Exception as e:
        console.print(f"[red]Import failed: {e}[/red]")
        raise typer.Exit(1)
    finally:
        db.close()


@app.command("seed")
def seed_data(
    username: str = typer.Option("admin", "--user", "-u", help="Username"),
    password: str = typer.Option(None, "--pass", "-p", help="Password"),
):
    """Seed database with initial user."""
    from app.database import SessionLocal
    from app.services.auth import AuthService
    from app.models.user import User

    db = SessionLocal()
    try:
        # Check if users exist
        user_count = db.query(User).count()
        if user_count > 0:
            console.print(f"[yellow]Database already has {user_count} user(s). Skipping seed.[/yellow]")
            return

        # Get password
        if not password:
            password = typer.prompt("Password", hide_input=True)
            password_confirm = typer.prompt("Confirm password", hide_input=True)
            if password != password_confirm:
                console.print("[red]Passwords do not match[/red]")
                raise typer.Exit(1)

        # Create user
        auth_service = AuthService(db)
        user = auth_service.create_user(username, password)

        console.print(f"[green]User '{username}' created successfully[/green]")
    finally:
        db.close()


@app.command("db-init")
def db_init():
    """Initialize database tables (run migrations)."""
    import subprocess
    import os

    backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    console.print("Running database migrations...")
    result = subprocess.run(
        ["alembic", "upgrade", "head"],
        cwd=backend_dir,
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        console.print("[green]Database initialized successfully[/green]")
        if result.stdout:
            console.print(result.stdout)
    else:
        console.print("[red]Migration failed[/red]")
        console.print(result.stderr)
        raise typer.Exit(1)
