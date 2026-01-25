"""Barbossa CLI - Main entry point."""
import typer
from rich.console import Console
from rich.table import Table

from app.cli import auth, library, admin

app = typer.Typer(
    name="barbossa",
    help="Barbossa - Family music library manager",
    add_completion=True,
)

console = Console()

# Add subcommands
app.add_typer(auth.app, name="auth", help="Authentication commands")
app.add_typer(library.app, name="library", help="Library browsing commands")
app.add_typer(admin.app, name="admin", help="Admin commands")


@app.command()
def version():
    """Show version information."""
    from app import __version__
    console.print(f"Barbossa v{__version__}")


@app.command()
def status():
    """Check system status."""
    from app.config import settings

    table = Table(title="Barbossa Status")
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="green")

    # Check database
    try:
        from sqlalchemy import text
        from app.database import engine
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        table.add_row("Database", "Connected")
    except Exception as e:
        table.add_row("Database", f"[red]Error: {e}[/red]")

    # Check paths
    from pathlib import Path
    for name, path in [
        ("Music Library", settings.music_library),
        ("User Libraries", settings.music_users),
        ("Downloads", settings.music_downloads),
    ]:
        p = Path(path)
        if p.exists():
            table.add_row(name, f"OK ({path})")
        else:
            table.add_row(name, f"[yellow]Missing ({path})[/yellow]")

    console.print(table)


if __name__ == "__main__":
    app()
