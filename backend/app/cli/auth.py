"""Barbossa CLI - Authentication commands."""
import os
import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer()
console = Console()

# Token storage location
TOKEN_FILE = Path.home() / ".barbossa" / "token.json"


def get_db_session():
    """Get a database session."""
    from app.database import SessionLocal
    return SessionLocal()


def save_token(token: str, username: str):
    """Save token to file."""
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(json.dumps({"token": token, "username": username}))
    TOKEN_FILE.chmod(0o600)


def load_token() -> Optional[dict]:
    """Load token from file."""
    if TOKEN_FILE.exists():
        return json.loads(TOKEN_FILE.read_text())
    return None


def clear_token():
    """Remove stored token."""
    if TOKEN_FILE.exists():
        TOKEN_FILE.unlink()


@app.command()
def login(
    username: str = typer.Argument(..., help="Username"),
    password: str = typer.Option(..., prompt=True, hide_input=True, help="Password"),
):
    """Login and store authentication token."""
    db = get_db_session()
    try:
        from app.services.auth import AuthService

        auth_service = AuthService(db)
        user = auth_service.authenticate(username, password)

        if not user:
            console.print("[red]Invalid credentials[/red]")
            raise typer.Exit(1)

        token = auth_service.create_token(user.id)
        save_token(token, user.username)

        console.print(f"[green]Logged in as {user.username}[/green]")
        if user.is_admin:
            console.print("[cyan]Admin privileges enabled[/cyan]")
    finally:
        db.close()


@app.command()
def logout():
    """Clear stored authentication token."""
    clear_token()
    console.print("[green]Logged out successfully[/green]")


@app.command()
def whoami():
    """Show current authenticated user."""
    token_data = load_token()

    if not token_data:
        console.print("[yellow]Not logged in[/yellow]")
        raise typer.Exit(1)

    db = get_db_session()
    try:
        from app.services.auth import AuthService

        auth_service = AuthService(db)
        user_id = auth_service.decode_token(token_data["token"])

        if not user_id:
            console.print("[red]Token expired or invalid. Please login again.[/red]")
            clear_token()
            raise typer.Exit(1)

        user = auth_service.get_user_by_id(user_id)
        if not user:
            console.print("[red]User not found. Please login again.[/red]")
            clear_token()
            raise typer.Exit(1)

        table = Table(title="Current User")
        table.add_column("Field", style="cyan")
        table.add_column("Value")

        table.add_row("Username", user.username)
        table.add_row("Admin", "Yes" if user.is_admin else "No")
        table.add_row("Created", str(user.created_at))

        console.print(table)
    finally:
        db.close()


def get_current_user():
    """Get current user from stored token. Raises Exit if not authenticated."""
    token_data = load_token()

    if not token_data:
        console.print("[red]Not logged in. Run 'barbossa auth login' first.[/red]")
        raise typer.Exit(1)

    db = get_db_session()
    from app.services.auth import AuthService

    auth_service = AuthService(db)
    user_id = auth_service.decode_token(token_data["token"])

    if not user_id:
        console.print("[red]Token expired. Please login again.[/red]")
        clear_token()
        db.close()
        raise typer.Exit(1)

    user = auth_service.get_user_by_id(user_id)
    if not user:
        console.print("[red]User not found. Please login again.[/red]")
        clear_token()
        db.close()
        raise typer.Exit(1)

    return user, db
