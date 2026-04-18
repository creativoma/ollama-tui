.PHONY: run install clean

run:
	@bash run.sh

install:
	@python3 -m venv .venv
	@.venv/bin/pip install --quiet textual rich
	@echo "Done. Run: make run"

clean:
	@rm -rf .venv
	@echo "Virtual environment removed."