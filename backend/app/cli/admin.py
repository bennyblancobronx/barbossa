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
def rescan():
    """Rescan the music library."""
    console.print("[yellow]Library rescan not yet implemented[/yellow]")
    console.print("This will scan /music/artists and update the database.")


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
