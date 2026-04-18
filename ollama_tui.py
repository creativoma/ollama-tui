#!/usr/bin/env python3
"""
╔═══════════════════════════════╗
║   OLLAMA TUI — Model Manager  ║
╚═══════════════════════════════╝
Manage your local Ollama models with style.
"""

import subprocess
import json
import sys
import os
from datetime import datetime

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import (
    Header, Footer, Static, Button, Label, Input,
    DataTable, RichLog, ProgressBar, TextArea
)
from textual.screen import Screen, ModalScreen
from textual.reactive import reactive
from textual import work, on, events
from rich.text import Text
from rich.panel import Panel
from rich.table import Table
from rich import box
import threading
import time


# ─── Helpers Ollama ──────────────────────────────────────────────────────────

def ollama_cmd(*args) -> tuple[bool, str]:
    """Run an ollama command and return (ok, output)."""
    try:
        result = subprocess.run(
            ["ollama", *args],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
        return False, result.stderr.strip()
    except FileNotFoundError:
        return False, "❌  Ollama not found. Is it installed and in PATH?"
    except subprocess.TimeoutExpired:
        return False, "⏱  Timeout waiting for Ollama response."


def get_models() -> list[dict]:
    """Return list of installed models."""
    ok, out = ollama_cmd("list")
    if not ok or not out:
        return []
    models = []
    lines = out.splitlines()
    if len(lines) < 2:
        return []
    for line in lines[1:]:  # skip header
        parts = line.split()
        if not parts:
            continue
        name = parts[0]
        size = parts[2] + " " + parts[3] if len(parts) > 3 else "?"
        modified = " ".join(parts[4:]) if len(parts) > 4 else "?"
        models.append({"name": name, "size": size, "modified": modified})
    return models


def get_running_models() -> list[str]:
    """Return currently running models."""
    ok, out = ollama_cmd("ps")
    if not ok or not out:
        return []
    lines = out.splitlines()
    running = []
    for line in lines[1:]:
        parts = line.split()
        if parts:
            running.append(parts[0])
    return running


def get_ollama_version() -> str:
    ok, out = ollama_cmd("--version")
    return out if ok else "unknown"


# ─── Screen: Confirm deletion ─────────────────────────────────────────────────

class ConfirmDialog(ModalScreen):
    DEFAULT_CSS = """
    ConfirmDialog {
        align: center middle;
        background: #0a0a0a 70%;
    }
    ConfirmDialog > Container {
        background: #141414;
        border: heavy #da7756;
        padding: 2 4;
        width: 50;
        height: auto;
    }
    ConfirmDialog Label {
        width: 100%;
        text-align: center;
        margin-bottom: 1;
        color: #e8e8e8;
    }
    ConfirmDialog Horizontal {
        align: center middle;
        margin-top: 1;
    }
    ConfirmDialog Button {
        margin: 0 2;
        background: #1a1a1a;
        color: #e8e8e8;
        border: solid #2a2a2a;
    }
    ConfirmDialog Button:hover {
        border: solid #da7756;
        color: #da7756;
    }
    ConfirmDialog #confirm {
        color: #e05555;
        border: solid #3a1a1a;
    }
    ConfirmDialog #confirm:hover {
        background: #2a1010;
        border: solid #e05555;
    }
    """

    def __init__(self, model_name: str):
        super().__init__()
        self.model_name = model_name

    def compose(self) -> ComposeResult:
        with Container():
            yield Label(f"Delete model?", id="dialog-title")
            yield Label(f"[bold #da7756]{self.model_name}[/]")
            yield Label("[dim]This action cannot be undone.[/]")
            with Horizontal():
                yield Button("Cancel", variant="default", id="cancel")
                yield Button("Delete", variant="error", id="confirm")

    @on(Button.Pressed, "#cancel")
    def cancel(self):
        self.dismiss(False)

    @on(Button.Pressed, "#confirm")
    def confirm(self):
        self.dismiss(True)


# ─── Screen: Quick chat ───────────────────────────────────────────────────────

class ChatScreen(Screen):
    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("ctrl+s", "send", "Send"),
    ]

    DEFAULT_CSS = """
    ChatScreen {
        background: #0a0a0a;
    }
    #chat-title {
        dock: top;
        background: #141414;
        color: #da7756;
        padding: 0 2;
        height: 3;
        content-align: center middle;
        text-style: bold;
        border-bottom: solid #2a2a2a;
    }
    #chat-log {
        border: solid #2a2a2a;
        margin: 0 1;
        padding: 1;
        background: #0f0f0f;
        color: #e8e8e8;
    }
    #input-row {
        dock: bottom;
        height: 8;
        margin: 1;
    }
    #chat-input {
        width: 1fr;
        background: #141414;
        color: #e8e8e8;
        border: solid #2a2a2a;
    }
    #chat-input:focus {
        border: solid #da7756;
    }
    #send-btn {
        width: 12;
        margin-left: 1;
        height: 100%;
        background: #da7756;
        color: #0a0a0a;
        border: solid #da7756;
        text-style: bold;
    }
    #send-btn:hover {
        background: #f0906a;
        border: solid #f0906a;
    }
    #thinking-indicator {
        height: 1;
        padding: 0 2;
        color: #606060;
    }
    """

    def __init__(self, model_name: str):
        super().__init__()
        self.model_name = model_name
        self.history = []

    def compose(self) -> ComposeResult:
        yield Static(f"  chat  /  {self.model_name}   [dim]esc to go back  ·  ctrl+s to send[/]", id="chat-title")
        yield RichLog(id="chat-log", markup=True, wrap=True)
        yield Static("", id="thinking-indicator")
        with Horizontal(id="input-row"):
            yield TextArea(id="chat-input")
            yield Button("Send\nctrl+s", variant="primary", id="send-btn")
        yield Footer()

    def on_mount(self):
        log = self.query_one("#chat-log", RichLog)
        log.write(f"[dim]Connected to [bold]{self.model_name}[/]. Type something to start.[/]")
        self.query_one("#chat-input").focus()

    @on(Button.Pressed, "#send-btn")
    def action_send(self):
        inp = self.query_one("#chat-input", TextArea)
        msg = inp.text.strip()
        if not msg:
            return
        inp.clear()
        log = self.query_one("#chat-log", RichLog)
        display = msg.replace("\n", " ↵ ")
        log.write(f"\n[bold #da7756]you:[/] {display}")
        self.history.append({"role": "user", "content": msg})
        self._thinking = True
        self._stream_response(msg)
        self._animate_thinking()

    @work(thread=True)
    def _animate_thinking(self):
        """Show animated dots while the model is thinking."""
        import time
        frames = ["·", "· ·", "· · ·"]
        i = 0
        while getattr(self, "_thinking", False):
            frame = frames[i % len(frames)]
            self.app.call_from_thread(self._set_thinking_text, frame)
            time.sleep(0.4)
            i += 1

    def _set_thinking_text(self, frame: str):
        try:
            indicator = self.query_one("#thinking-indicator", Static)
            if getattr(self, "_thinking", False):
                indicator.update(f"[dim]{self.model_name}: {frame}[/]")
        except Exception:
            pass

    @work(thread=True)
    def _stream_response(self, msg: str):
        try:
            proc = subprocess.Popen(
                ["ollama", "run", self.model_name, msg],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            response = ""
            for chunk in proc.stdout:
                response += chunk
            proc.wait()
            output = self._filter_thinking(response.strip())
            output = output or "[dim]No response.[/]"
            self._thinking = False
            self.app.call_from_thread(self._append_response, output)
        except Exception as e:
            self._thinking = False
            self.app.call_from_thread(self._append_response, f"[#e05555]Error: {e}[/]")

    def _filter_thinking(self, text: str) -> str:
        """Strip internal reasoning blocks from model output."""
        import re
        # <think>...</think> format (DeepSeek, QwQ, etc.)
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
        # "Thinking...\n...\ndone thinking." format (Gemma4, etc.)
        text = re.sub(r"Thinking\.+.*?\.\.\.done thinking\.", "", text, flags=re.DOTALL)
        # Strip "Thinking Process:" and everything up to double blank line
        text = re.sub(r"Thinking Process:.*?\n\n", "", text, flags=re.DOTALL)
        return text.strip()

    def _append_response(self, text: str):
        try:
            self.query_one("#thinking-indicator", Static).update("")
            log = self.query_one("#chat-log", RichLog)
            log.write(f"\n[bold #e8e8e8]{self.model_name}:[/] {text}")
        except Exception:
            pass


# ─── Screen: Pull model ───────────────────────────────────────────────────────

class PullScreen(Screen):
    BINDINGS = [Binding("escape", "app.pop_screen", "Back")]

    DEFAULT_CSS = """
    PullScreen {
        align: center middle;
        background: #0a0a0a 70%;
    }
    #pull-box {
        background: #141414;
        border: heavy #da7756;
        padding: 2 4;
        width: 60;
        height: auto;
        color: #e8e8e8;
    }
    #pull-title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
        color: #da7756;
    }
    #pull-input {
        margin-bottom: 1;
        background: #0f0f0f;
        color: #e8e8e8;
        border: solid #2a2a2a;
    }
    #pull-input:focus {
        border: solid #da7756;
    }
    #pull-log {
        height: 12;
        border: solid #2a2a2a;
        margin-top: 1;
        padding: 1;
        background: #0a0a0a;
        color: #e8e8e8;
    }
    #pull-actions {
        align: center middle;
        margin-top: 1;
    }
    #start-pull {
        background: #da7756;
        color: #0a0a0a;
        border: solid #da7756;
        text-style: bold;
    }
    #start-pull:hover {
        background: #f0906a;
        border: solid #f0906a;
    }
    #cancel-pull {
        background: #1a1a1a;
        color: #e8e8e8;
        border: solid #2a2a2a;
    }
    #cancel-pull:hover {
        border: solid #da7756;
        color: #da7756;
    }
    """

    def compose(self) -> ComposeResult:
        with Container(id="pull-box"):
            yield Label("Download model", id="pull-title")
            yield Label("[dim]e.g.: llama3.2, mistral, phi3, gemma2:9b[/]")
            yield Input(placeholder="model name...", id="pull-input")
            with Horizontal(id="pull-actions"):
                yield Button("Cancel", id="cancel-pull", variant="default")
                yield Button("Download", id="start-pull", variant="success")
            yield RichLog(id="pull-log", markup=True, wrap=True)
        yield Footer()

    def on_mount(self):
        self.query_one("#pull-input").focus()

    @on(Button.Pressed, "#cancel-pull")
    def cancel(self):
        self.app.pop_screen()

    @on(Button.Pressed, "#start-pull")
    @on(Input.Submitted, "#pull-input")
    def start_pull(self):
        name = self.query_one("#pull-input", Input).value.strip()
        if not name:
            return
        log = self.query_one("#pull-log", RichLog)
        log.write(f"[cyan]Downloading [bold]{name}[/]...[/]")
        self._do_pull(name)

    @work(thread=True)
    def _do_pull(self, name: str):
        log = self.query_one("#pull-log", RichLog)
        try:
            proc = subprocess.Popen(
                ["ollama", "pull", name],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
            )
            for line in proc.stdout:
                line = line.strip()
                if line:
                    self.app.call_from_thread(log.write, line)
            proc.wait()
            if proc.returncode == 0:
                self.app.call_from_thread(log.write, f"\n[bold #55a868]✓ {name} downloaded successfully.[/]")
                self.app.call_from_thread(self.app.refresh_models)
            else:
                self.app.call_from_thread(log.write, f"[bold #e05555]✗ Error downloading {name}.[/]")
        except FileNotFoundError:
            self.app.call_from_thread(log.write, "[#e05555]Ollama not found.[/]")


# ─── Main app ────────────────────────────────────────────────────────────────

class OllamaTUI(App):
    TITLE = "ollama tui"

    # ── Claude palette: black, grays, orange ──────────────────────────────
    DESIGN_TOKENS = {
        "background":   "#0a0a0a",   # near-pure black
        "surface":      "#141414",   # very dark gray
        "surface2":     "#1e1e1e",   # dark gray
        "border":       "#2a2a2a",   # border gray
        "text":         "#e8e8e8",   # soft white
        "text_muted":   "#606060",   # muted gray
        "orange":       "#da7756",   # Claude orange
        "orange_dim":   "#8a3a28",   # dark orange
        "orange_bright":"#f0906a",   # light orange hover
        "error":        "#e05555",
        "success":      "#55a868",
    }

    CSS = """
    /* ── Global layout ── */
    Screen {
        background: #0a0a0a;
        color: #e8e8e8;
    }

    /* ── Header ── */
    Header {
        background: #141414;
        color: #da7756;
        text-style: bold;
        height: 3;
        border-bottom: solid #2a2a2a;
    }
    Header > .header--title {
        color: #da7756;
    }

    /* ── Sidebar ── */
    #sidebar {
        width: 26;
        border-right: solid #2a2a2a;
        padding: 1;
        background: #0f0f0f;
    }
    #sidebar-title {
        text-align: center;
        text-style: bold;
        color: #da7756;
        margin-bottom: 1;
        padding: 0 0 1 0;
        border-bottom: solid #2a2a2a;
    }
    .nav-btn {
        width: 100%;
        margin-bottom: 1;
        background: #1a1a1a;
        color: #e8e8e8;
        border: solid #2a2a2a;
    }
    .nav-btn:hover {
        background: #252525;
        color: #da7756;
        border: solid #da7756;
    }
    .nav-btn:focus {
        background: #da7756;
        color: #0a0a0a;
        border: solid #da7756;
        text-style: bold;
    }
    #stats-box {
        margin-top: 1;
        padding: 1;
        border: solid #2a2a2a;
        background: #0a0a0a;
        color: #606060;
    }

    /* ── Main area ── */
    #main-area {
        padding: 1 2;
        background: #0a0a0a;
    }
    #section-title {
        text-style: bold;
        color: #da7756;
        margin-bottom: 1;
        padding-bottom: 1;
        border-bottom: solid #2a2a2a;
    }

    /* ── Table ── */
    #models-table {
        height: 1fr;
    }
    DataTable {
        background: #0f0f0f;
        border: solid #2a2a2a;
        color: #e8e8e8;
    }
    DataTable > .datatable--header {
        background: #1a1a1a;
        color: #da7756;
        text-style: bold;
    }
    DataTable > .datatable--cursor {
        background: #da7756;
        color: #0a0a0a;
        text-style: bold;
    }
    DataTable > .datatable--hover {
        background: #1e1e1e;
    }

    /* ── Actions ── */
    #actions-bar {
        height: auto;
        margin-top: 1;
        padding-top: 1;
        border-top: solid #2a2a2a;
    }
    .action-btn {
        margin-right: 1;
        background: #1a1a1a;
        color: #e8e8e8;
        border: solid #2a2a2a;
    }
    .action-btn:hover {
        background: #252525;
        color: #da7756;
        border: solid #da7756;
    }
    #btn-chat {
        background: #da7756;
        color: #0a0a0a;
        text-style: bold;
        border: solid #da7756;
    }
    #btn-chat:hover {
        background: #f0906a;
        border: solid #f0906a;
    }
    #btn-delete {
        color: #e05555;
        border: solid #2a2a2a;
        background: #1a1a1a;
    }
    #btn-delete:hover {
        background: #2a1010;
        border: solid #e05555;
    }

    /* ── Status bar ── */
    #status-bar {
        dock: bottom;
        height: 1;
        background: #0f0f0f;
        padding: 0 2;
        color: #606060;
        border-top: solid #1e1e1e;
    }

    /* ── Footer ── */
    Footer {
        background: #0f0f0f;
        color: #606060;
        border-top: solid #1e1e1e;
    }
    Footer > .footer--key {
        color: #da7756;
        background: #1a1a1a;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("p", "pull", "Download"),
        Binding("d", "delete_model", "Delete"),
        Binding("c", "chat", "Chat"),
        Binding("i", "model_info", "Info"),
        Binding("?", "help", "Help"),
    ]

    selected_model: reactive[str] = reactive("")
    status_msg: reactive[str] = reactive("Ready.")

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            # Sidebar
            with Vertical(id="sidebar"):
                yield Static("ollama  /  models", id="sidebar-title")
                yield Button("Models", classes="nav-btn", id="nav-models", variant="primary")
                yield Button("Download", classes="nav-btn", id="nav-pull", variant="default")
                yield Button("Chat", classes="nav-btn", id="nav-chat", variant="default")
                yield Static("", id="stats-box")

            # Main area
            with Vertical(id="main-area"):
                yield Static("Installed models", id="section-title")
                yield DataTable(id="models-table", cursor_type="row")
                with Horizontal(id="actions-bar"):
                    yield Button("Chat", id="btn-chat", variant="primary", classes="action-btn")
                    yield Button("Info", id="btn-info", variant="default", classes="action-btn")
                    yield Button("Copy name", id="btn-copy", variant="default", classes="action-btn")
                    yield Button("Delete", id="btn-delete", variant="error", classes="action-btn")

        yield Static("", id="status-bar")
        yield Footer()

    def on_mount(self):
        self._setup_table()
        self.refresh_models()
        self._update_stats()
        # Auto-refresh every 30s
        self.set_interval(30, self.refresh_models)

    def _setup_table(self):
        table = self.query_one("#models-table", DataTable)
        table.add_columns("  Model", "Size", "Modified", "Status")

    def refresh_models(self):
        self.status_msg = "Loading models..."
        self.query_one("#status-bar", Static).update(f"  ⟳  {self.status_msg}")
        self._load_models_bg()

    @work(thread=True)
    def _load_models_bg(self):
        models = get_models()
        running = get_running_models()
        self.call_from_thread(self._populate_table, models, running)

    def _populate_table(self, models: list, running: list):
        table = self.query_one("#models-table", DataTable)
        table.clear()
        if not models:
            table.add_row("  [dim]No models installed[/]", "", "", "")
        for m in models:
            is_running = any(m["name"] in r for r in running)
            status = Text("● running", style="bold green") if is_running else Text("○ idle", style="dim")
            table.add_row(
                f"  [bold]{m['name']}[/]",
                m["size"],
                m["modified"],
                status,
            )
        # Select first row
        if models:
            table.move_cursor(row=0)
            self.selected_model = models[0]["name"]
        self.status_msg = f"{len(models)} models installed"
        self.query_one("#status-bar", Static).update(
            f"  ✓  {self.status_msg}  ·  Last updated: {datetime.now().strftime('%H:%M:%S')}"
        )
        self._update_stats(len(models), len(running))

    def _update_stats(self, total=0, active=0):
        version = get_ollama_version()
        stats = (
            f"[dim]Version:[/]\n"
            f"[bold]{version}[/]\n\n"
            f"[dim]Models:[/]\n"
            f"[bold]{total}[/] installed\n"
            f"[bold green]{active}[/] running"
        )
        self.query_one("#stats-box", Static).update(stats)

    @on(DataTable.RowSelected)
    def on_row_selected(self, event: DataTable.RowSelected):
        table = self.query_one("#models-table", DataTable)
        try:
            row = table.get_row_at(event.cursor_row)
            if row:
                name = str(row[0]).strip().replace("[bold]", "").replace("[/]", "").strip()
                self.selected_model = name
                self.query_one("#status-bar", Static).update(f"  →  {name}")
        except Exception:
            pass

    # ── Actions ───────────────────────────────────────────────────────────────

    @on(Button.Pressed, "#nav-pull")
    @on(Button.Pressed, "#btn-download")
    def action_pull(self):
        self.push_screen(PullScreen())

    @on(Button.Pressed, "#nav-chat")
    @on(Button.Pressed, "#btn-chat")
    def action_chat(self):
        if not self.selected_model:
            self.notify("Select a model first.", severity="warning")
            return
        self.push_screen(ChatScreen(self.selected_model))

    @on(Button.Pressed, "#btn-delete")
    def action_delete_model(self):
        if not self.selected_model:
            self.notify("Select a model first.", severity="warning")
            return

        def handle_result(confirmed: bool):
            if confirmed:
                self._delete_model(self.selected_model)

        self.push_screen(ConfirmDialog(self.selected_model), handle_result)

    @work(thread=True)
    def _delete_model(self, name: str):
        self.call_from_thread(
            self.query_one("#status-bar", Static).update,
            f"  🗑  Deleting {name}..."
        )
        ok, msg = ollama_cmd("rm", name)
        if ok:
            self.call_from_thread(self.notify, f"✓ {name} deleted.", severity="information")
        else:
            self.call_from_thread(self.notify, f"✗ Error: {msg}", severity="error")
        self.call_from_thread(self.refresh_models)

    @on(Button.Pressed, "#btn-info")
    def action_model_info(self):
        if not self.selected_model:
            self.notify("Select a model first.", severity="warning")
            return
        self._show_info(self.selected_model)

    @work(thread=True)
    def _show_info(self, name: str):
        ok, out = ollama_cmd("show", name)
        if ok:
            self.call_from_thread(self.notify, out[:200] + "...", title=f"ℹ {name}", timeout=8)
        else:
            self.call_from_thread(self.notify, out, severity="error")

    @on(Button.Pressed, "#btn-copy")
    def copy_name(self):
        if self.selected_model:
            self.notify(f"Name copied: {self.selected_model}")

    def action_refresh(self):
        self.refresh_models()

    def action_help(self):
        help_text = (
            "[bold]Keyboard shortcuts[/]\n\n"
            "[#da7756]r[/] — Refresh models\n"
            "[#da7756]p[/] — Download new model\n"
            "[#da7756]c[/] — Chat with selected model\n"
            "[#da7756]d[/] — Delete selected model\n"
            "[#da7756]i[/] — Model info\n"
            "[#da7756]q[/] — Quit\n\n"
            "[dim]Use ↑↓ to navigate the table.[/]"
        )
        self.notify(help_text, title="Help", timeout=10)


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    app = OllamaTUI()
    app.run()


if __name__ == "__main__":
    main()