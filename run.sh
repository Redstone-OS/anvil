#!/bin/bash

# Navigate to the script's directory ensuring we are in the project root
cd "$(dirname "$0")"

# Set terminal title
echo -ne "\033]0;Anvil 0.0.5 - RedstoneOS\007"

# Add src to PYTHONPATH so python modules can be found
export PYTHONPATH="$(pwd)/src"

if [ -z "$1" ]; then
    # No arguments provided: Run the Interactive TUI
    # We explicitly insert the path to ensure imports work correctly
    python3 -c "import sys; sys.path.insert(0, '$(pwd)/src'); from tui import run_tui; run_tui()"
else
    # Arguments provided: Run in CLI mode
    # python -m cli allows running the cli module directly
    python3 -m cli "$@"
fi