import sys
import tty
import termios
import webbrowser
from typing import List, Optional, Callable

from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

from ..core import setup_logger

logger = setup_logger("oauth_automator.github.manager")


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

logger = setup_logger("oauth_automator.github.manager")


class OAuthAppManager:
    def __init__(self, apps: List[dict], delete_callback: Callable[[str], bool]):
        self.apps = apps
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
        # Table of Apps
        table = Table(show_header=True, header_style="bold magenta", expand=True, box=None)
        table.add_column("X", width=3, justify="center")
        table.add_column("Name", style="white")
        table.add_column("URL", style="dim")

        # Viewport logic (simple scrolling)
        max_rows = 15
        start_idx = 0
        if self.cursor > max_rows - 3:
            start_idx = self.cursor - (max_rows - 3)
        
        visible_apps = self.apps[start_idx : start_idx + max_rows]

        for i, app in enumerate(visible_apps):
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
                style = Style(dim=(i % 2 == 0)) # Zebra striping slightly

            # Render row
            table.add_row(
                Text(checkbox, style=check_style),
                Text(app.get("name", "Unknown")),
                Text(app.get("url", "")),
                style=style
            )
            
        # Status Bar
        if self.status_message:
            status_text = Text(f" {self.status_message} ", style=f"reverse {self.status_style}")
        else:
            status_text = Text(f" {len(self.apps)} apps loaded", style="dim")

        # Footer Help
        help_text = Text.from_markup(
            "\n[bold cyan]Controls:[/]\n"
            " [bold]↑/↓[/] Move   [bold]Space[/] Select/Deselect   [bold]a[/] Select All\n"
            " [bold red]x,d[/] Delete Selected   [bold green]o[/] Open in Browser   [bold]q[/] Quit"
        )
        
        # Combine into a grid or just append
        from rich.console import Group
        return Panel(
            Group(table, Text(""), status_text, help_text),
            title="[bold]OAuth App Manager[/]",
            border_style="blue"
        )

    def _delete_selected(self):
        if not self.selected:
            self.status_message = "No apps selected to delete"
            self.status_style = "yellow"
            return

        count = len(self.selected)
        self.status_message = f"Deleting {count} app(s)..."
        self.status_style = "red"
        # We need to re-render to show the message
        return True # Signal that we are in a 'busy' state if needed

    def _perform_delete(self):
        """Actually delete items (blocking operation)"""
        to_delete = sorted(list(self.selected), reverse=True)
        deleted_count = 0
        
        for idx in to_delete:
            if idx < len(self.apps):
                app = self.apps[idx]
                success = self.delete_callback(app["name"])
                if success:
                    self.apps.pop(idx)
                    deleted_count += 1
        
        self.selected.clear()
        
        # Adjust cursor
        if self.cursor >= len(self.apps):
            self.cursor = max(0, len(self.apps) - 1)
            
        self.status_message = f"Successfully deleted {deleted_count} apps."
        self.status_style = "green"

    def _open_selected(self):
        if not self.selected:
            if self.apps:
                url = self.apps[self.cursor].get("url")
                if url:
                    webbrowser.open(url)
                    self.status_message = f"Opened {self.apps[self.cursor]['name']}"
                    self.status_style = "green"
        else:
            count = 0
            for idx in self.selected:
                url = self.apps[idx].get("url")
                if url:
                    webbrowser.open(url)
                    count += 1
            self.status_message = f"Opened {count} apps"
            self.status_style = "green"

    def run(self):
        if not self.apps:
            self.console.print("[yellow]No OAuth apps found.[/]")
            return

        self.console.show_cursor(False)
        try:
            # auto_refresh=False prevents flickering, we update manually on input
            with Live(self._renderable(), console=self.console, auto_refresh=False, screen=True) as live:
                while self.running and self.apps:
                    live.update(self._renderable(), refresh=True)
                    
                    key = self._get_key()
                    self.status_message = "" # Clear permanent status on new keypress

                    if key in ('q', '\x03'): # q or ctrl+c
                        self.running = False
                    elif key == 'up' and self.cursor > 0:
                        self.cursor -= 1
                    elif key == 'down' and self.cursor < len(self.apps) - 1:
                        self.cursor += 1
                    elif key == ' ':
                        if self.cursor in self.selected:
                            self.selected.remove(self.cursor)
                        else:
                            self.selected.add(self.cursor)
                    elif key == 'a':
                        if len(self.selected) == len(self.apps):
                            self.selected.clear()
                        else:
                            self.selected = set(range(len(self.apps)))
                    elif key in ('x', 'd'):
                        if not self.selected:
                            # If nothing selected, select current
                            self.selected.add(self.cursor)
                        
                        # Show deleting status immediately
                        self._delete_selected() 
                        live.update(self._renderable(), refresh=True)
                        
                        # Perform actual deletion (blocking)
                        self._perform_delete()
                        
                        if not self.apps:
                            self.running = False
                    elif key == 'o':
                        self._open_selected()
        finally:
            self.console.show_cursor(True)
            if not self.apps:
               self.console.print("[yellow]All apps have been deleted.[/]")


def interactive_manage(automator) -> None:
    # Initial loading message
    Console().print("[cyan]📋 Fetching OAuth apps list... (this may take a few seconds)[/]")
    apps = automator.list_oauth_apps()

    def delete_app(name: str) -> bool:
        return automator.delete_oauth_app(name)

    manager = OAuthAppManager(apps, delete_app)
    manager.run()

