import sys
import tty
import termios
import webbrowser
import time
from typing import List, Optional, Callable

from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.panel import Panel
from rich.text import Text
from rich.layout import Layout
from rich.style import Style

from ..core import setup_logger

logger = setup_logger("oauth_automator.google.manager")


class OAuthClientManager:
    def __init__(self, clients: List[dict], delete_callback: Callable[[str], bool]):
        self.clients = clients
        self.delete_callback = delete_callback
        self.selected: set = set()
        self.cursor = 0
        self.console = Console()
        self.running = True
        self.status_message = ""
        self.status_style = "dim"

    def _get_key(self) -> str:
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            sys.stdin.flush()
            ch = sys.stdin.read(1)
            if ch == '\x1b':
                # Non-blocking read for sequence
                import select
                if select.select([sys.stdin], [], [], 0.1)[0]:
                    ch2 = sys.stdin.read(1)
                    if select.select([sys.stdin], [], [], 0.1)[0]:
                        ch3 = sys.stdin.read(1)
                        if ch2 == '[':
                            if ch3 == 'A': return 'up'
                            if ch3 == 'B': return 'down'
            return ch
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    def _renderable(self) -> Panel:
        # Table of Clients
        table = Table(show_header=True, header_style="bold magenta", expand=True, box=None)
        table.add_column("X", width=3, justify="center")
        table.add_column("Name", style="white")

        # Viewport logic
        max_rows = 15
        start_idx = 0
        if self.cursor > max_rows - 3:
            start_idx = self.cursor - (max_rows - 3)
        
        visible_clients = self.clients[start_idx : start_idx + max_rows]

        for i, client in enumerate(visible_clients):
            real_idx = start_idx + i
            is_cursor = real_idx == self.cursor
            is_selected = real_idx in self.selected

            # Checkbox state
            if is_selected:
                checkbox = "[x]"
                check_style = "green"
            else:
                checkbox = "[ ]"
                check_style = "dim"

            # Row styling
            if is_cursor:
                style = Style(bgcolor="blue", color="white", bold=True)
                check_style = "bold white"
            else:
                style = Style(dim=(i % 2 == 0)) 

            # Render row
            table.add_row(
                Text(checkbox, style=check_style),
                Text(client.get("name", "Unknown")),
                style=style
            )
            
        # Status Bar
        if self.status_message:
            status_text = Text(f" {self.status_message} ", style=f"reverse {self.status_style}")
        else:
            status_text = Text(f" {len(self.clients)} clients loaded", style="dim")

        # Footer Help
        help_text = Text.from_markup(
            "\n[bold cyan]Controls:[/]\n"
            " [bold]↑/↓[/] Move   [bold]Space[/] Select/Deselect   [bold]a[/] Select All\n"
            " [bold red]x,d[/] Delete Selected   [bold]q[/] Quit"
        )
        
        from rich.console import Group
        return Panel(
            Group(table, Text(""), status_text, help_text),
            title="[bold]Google OAuth Manager[/]",
            border_style="blue"
        )

    def _delete_selected(self):
        if not self.selected:
            self.status_message = "No clients selected to delete"
            self.status_style = "yellow"
            return False

        count = len(self.selected)
        self.status_message = f"Deleting {count} client(s)..."
        self.status_style = "red"
        return True

    def _perform_delete(self):
        """Actually delete items (blocking operation)"""
        to_delete = sorted(list(self.selected), reverse=True)
        deleted_count = 0
        
        for idx in to_delete:
            if idx < len(self.clients):
                client = self.clients[idx]
                success = self.delete_callback(client["name"])
                if success:
                    self.clients.pop(idx)
                    deleted_count += 1
        
        self.selected.clear()
        
        # Adjust cursor
        if self.cursor >= len(self.clients):
            self.cursor = max(0, len(self.clients) - 1)
            
        self.status_message = f"Successfully deleted {deleted_count} clients."
        self.status_style = "green"

    def run(self):
        if not self.clients:
            self.console.print("[yellow]No OAuth clients found.[/]")
            return

        self.console.show_cursor(False)
        try:
            with Live(self._renderable(), console=self.console, auto_refresh=False, screen=True) as live:
                while self.running and self.clients:
                    live.update(self._renderable(), refresh=True)
                    
                    key = self._get_key()
                    self.status_message = "" 

                    if key in ('q', '\x03'):
                        self.running = False
                    elif key == 'up' and self.cursor > 0:
                        self.cursor -= 1
                    elif key == 'down' and self.cursor < len(self.clients) - 1:
                        self.cursor += 1
                    elif key == ' ':
                        if self.cursor in self.selected:
                            self.selected.remove(self.cursor)
                        else:
                            self.selected.add(self.cursor)
                    elif key == 'a':
                        if len(self.selected) == len(self.clients):
                            self.selected.clear()
                        else:
                            self.selected = set(range(len(self.clients)))
                    elif key in ('x', 'd'):
                        if not self.selected:
                            self.selected.add(self.cursor)
                        
                        self._delete_selected() 
                        live.update(self._renderable(), refresh=True)
                        
                        self._perform_delete()
                        
                        if not self.clients:
                            self.running = False

        finally:
            self.console.show_cursor(True)
            if not self.clients:
               self.console.print("[yellow]All clients have been deleted.[/]")


def interactive_manage(automator) -> None:
    Console().print("[cyan]📋 Fetching Google OAuth clients... (this may take a few seconds)[/]")
    clients = automator.list_oauth_clients()

    def delete_client(name: str) -> bool:
        return automator.delete_oauth_client(name)

    manager = OAuthClientManager(clients, delete_client)
    manager.run()
