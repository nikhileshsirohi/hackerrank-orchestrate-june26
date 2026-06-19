"""Compatibility evaluation entry point for the original starter layout."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from evaluator import main


if __name__ == "__main__":
    main()

