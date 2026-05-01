# Run me once after cloning if templates/solar_load_template.xlsx is missing.
#   python scripts/build_template.py
#
# The Streamlit app calls the same builder on first run, so this is
# really only here for CI / docker / "I want to see the file before
# spinning up streamlit".

import sys
from pathlib import Path

# allow running from any cwd: add the project root onto sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.excel.template_builder import build  # noqa: E402

if __name__ == "__main__":
    out = Path(__file__).resolve().parent.parent / "templates" / "solar_load_template.xlsx"
    build(out)
    print(f"Template written: {out}")
