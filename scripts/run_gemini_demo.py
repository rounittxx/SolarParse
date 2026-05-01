# Sanity-check + headless demo.
#   python scripts/run_gemini_demo.py
#
# What it does:
#   1. Loads GOOGLE_API_KEY from .env
#   2. Calls Gemini 1.5 Flash on samples/sample_msedcl_bill.pdf
#   3. Prints the structured JSON it got back
#   4. Writes output/filled_demo_bill_gemini.xlsx
#
# Useful when you want to verify the key works without spinning up
# Streamlit, or when you want the AI-extracted Excel for the
# submission email and don't want to drive the UI.

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from src.extractor.pdf_parser import extract_text_from_pdf
from src.extractor.llm_extractor import extract_with_gemini
from src.excel.filler import fill_template, report
from src.solar.calculator import recommend


SAMPLE = ROOT / "samples" / "sample_msedcl_bill.pdf"
TEMPLATE = ROOT / "templates" / "solar_load_template.xlsx"
OUT = ROOT / "output" / "filled_demo_bill_gemini.xlsx"


def hr(title=""):
    print()
    print("-" * 64)
    if title:
        print(title)
        print("-" * 64)


def main():
    if not os.getenv("GOOGLE_API_KEY") and not os.getenv("GEMINI_API_KEY"):
        print("ERROR: No GOOGLE_API_KEY in environment.")
        print("Put one in .env (see .env.example).")
        sys.exit(1)

    if not SAMPLE.exists():
        print(f"ERROR: missing sample bill at {SAMPLE}")
        sys.exit(1)

    if not TEMPLATE.exists():
        print(f"Template missing -- generating it now.")
        from src.excel.template_builder import build
        build(TEMPLATE)

    hr("1. Reading sample bill")
    raw = SAMPLE.read_bytes()
    text, images = extract_text_from_pdf(raw)
    print(f"   file: {SAMPLE.name} ({len(raw):,} bytes)")
    print(f"   text layer: {len(text)} chars")
    print(f"   page images: {len(images)}")

    hr("2. Calling Gemini 1.5 Flash (vision)")
    result = extract_with_gemini(images, text_hint=text)
    fields = result["fields"]
    confs = result["confidence"]
    print("   extracted fields:")
    for k, v in fields.items():
        c = confs.get(k, 0)
        bar = "#" * int(c * 10) + "-" * (10 - int(c * 10))
        print(f"     {k:22s}  {str(v):<35s}  [{bar}] {int(c*100)}%")

    hr("3. Solar recommendation")
    rec = recommend(fields.get("units_consumed") or 0,
                    fields.get("sanctioned_load"))
    if rec:
        for k, v in rec.items():
            print(f"     {k:24s} = {v}")
    else:
        print("   (skipped -- units_consumed missing)")

    hr("4. Filling template")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fill_template(TEMPLATE, fields, OUT)
    rep = report()
    print(f"   wrote: {OUT}")
    print(f"   cells written: {len(rep['written'])}")
    if rep["skipped"]:
        print(f"   cells skipped (formula collisions): {rep['skipped']}")

    hr("5. Raw JSON (for the record)")
    print(json.dumps(result, indent=2, default=str))

    hr()
    print(f"DONE. Open the filled file:\n   {OUT}")


if __name__ == "__main__":
    main()
