import sys
from pathlib import Path

# Allow tests to import the package without installing.
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

# Allow tests to import the parent harness package without installing.
PARENT = ROOT.parent
if (PARENT / "harness").is_dir():
    sys.path.insert(0, str(PARENT))
