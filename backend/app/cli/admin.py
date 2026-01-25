"""Barbossa CLI - Admin commands."""
import typer
from rich.console import Console
from rich.table import Table
from rich.prompt import Confirm

from app.cli.auth import get_current_user

app = typer.Typer()
console = Console()


def require_admin():
    """Require admin privileges."""
    user, db = get_current_user()
    if not user.is_admin:
        console.print("[red]Admin privileges required[/red]")
        db.close()
        raise typer.Exit(1)
    return user, db


@app.command("create-user")
def create_user(
    username: str = typer.Argument(..., help="Username for new user"),
    admin: bool = typer.Option(False, "--admin", "-a", help="Grant admin privileges"),
    password: str = typer.Option(None, "--password", "-p", help="Password (will prompt if not provided)"),
):
    """Create a new user (admin only, or first user)."""
    from app.database import SessionLocal
    from app.services.auth import AuthService

    db = SessionLocal()
    try:
        auth_service = AuthService(db)

        # Check if any users exist
        from app.models.user import User
        user_count = db.query(User).count()

        if user_count > 0:
            # Require admin to create more users
            try:
                current_user, _ = require_admin()
            except typer.Exit:
                console.print("[red]Only admins can create users (or create first user)[/red]")
                return

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
        user = auth_service.create_user(username, password, is_admin=admin)

        console.print(f"[green]User '{username}' created successfully[/green]")
        if admin:
            console.print("[cyan]Admin privileges granted[/cyan]")
    finally:
        db.close()


@app.command("list-users")
def list_users():
    """List all users (admin only)."""
    user, db = require_admin()
    try:
        from app.models.user import User

        users = db.query(User).order_by(User.username).all()

        table = Table(title="Users")
        table.add_column("ID", style="dim")
        table.add_column("Username", style="cyan")
        table.add_column("Admin", justify="center")
        table.add_column("Created")

        for u in users:
            admin_badge = "[green]Yes[/green]" if u.is_admin else ""
            table.add_row(
                str(u.id),
                u.username,
                admin_badge,
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
    """Delete a user (admin only)."""
    user, db = require_admin()
    try:
        from app.models.user import User

        target = db.query(User).filter(User.username == username).first()
        if not target:
            console.print(f"[red]User '{username}' not found[/red]")
            raise typer.Exit(1)

        if target.id == user.id:
            console.print("[red]Cannot delete yourself[/red]")
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
    """Rescan the music library (admin only)."""
    user, db = require_admin()
    try:
        console.print("[yellow]Library rescan not yet implemented[/yellow]")
        console.print("This will scan /music/library and update the database.")
    finally:
        db.close()


@app.command("seed")
def seed_data(
    admin_username: str = typer.Option("admin", "--admin-user", help="Admin username"),
    admin_password: str = typer.Option(None, "--admin-pass", help="Admin password"),
):
    """Seed database with initial admin user."""
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
        if not admin_password:
            admin_password = typer.prompt("Admin password", hide_input=True)
            password_confirm = typer.prompt("Confirm password", hide_input=True)
            if admin_password != password_confirm:
                console.print("[red]Passwords do not match[/red]")
                raise typer.Exit(1)

        # Create admin user
        auth_service = AuthService(db)
        user = auth_service.create_user(admin_username, admin_password, is_admin=True)

        console.print(f"[green]Admin user '{admin_username}' created successfully[/green]")
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
