# ⬡ Ollama TUI

A slick terminal interface for managing your local Ollama models — browse, chat, download and delete models without leaving the terminal.

![Python](https://img.shields.io/badge/python-3.10+-blue) ![Textual](https://img.shields.io/badge/TUI-Textual-green) ![Ollama](https://img.shields.io/badge/requires-Ollama-orange) ![License](https://img.shields.io/badge/license-MIT-lightgrey)

## Requirements

- [Ollama](https://ollama.com) installed and running
- Python 3.10+

## Installation

```bash
# Clone the repo
git clone https://github.com/youruser/ollama-tui
cd ollama-tui

# Create a virtual environment and install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Usage

```bash
source venv/bin/activate   # if not already active
python3 ollama_tui.py
```

## Keybindings

| Key | Action |
|-----|--------|
| `↑ ↓` | Navigate models |
| `c` | Chat with selected model |
| `p` | Download a new model |
| `d` | Delete selected model |
| `i` | Show model info |
| `r` | Refresh list |
| `?` | Help |
| `q` | Quit |

## Features

- List all installed models with size and status (running / idle)
- Quick chat directly from the TUI — thinking blocks filtered automatically
- Download new models with live progress output
- Delete models with a confirmation dialog
- Auto-refresh every 30 seconds
- Sidebar with Ollama version and model stats
