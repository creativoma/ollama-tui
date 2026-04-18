#!/usr/bin/env bash
set -e

VENV_DIR=".venv"
SCRIPT="ollama_tui.py"

# ── Check Python 3 is available ───────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
  echo "Python 3 not found. Install it with:"
  echo "  brew install python"
  exit 1
fi

# ── Create virtual environment if it doesn't exist ────────────────────────────
if [ ! -d "$VENV_DIR" ]; then
  echo "Creating virtual environment..."
  python3 -m venv "$VENV_DIR"
fi

# ── Activate virtual environment ──────────────────────────────────────────────
source "$VENV_DIR/bin/activate"

# ── Install dependencies if missing ───────────────────────────────────────────
if ! python -c "import textual, rich" &>/dev/null; then
  echo "Installing dependencies..."
  pip install --quiet textual rich
fi

# ── Launch the app ────────────────────────────────────────────────────────────
python "$SCRIPT"