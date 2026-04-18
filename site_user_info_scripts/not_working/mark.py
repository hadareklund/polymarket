"""Shortcut entrypoint for Crunchbase full-name search without API keys."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from crunchbase_full_name_search import main


if __name__ == "__main__":
    main()
