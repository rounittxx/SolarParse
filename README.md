# Energybae Solar Bill Extractor

Upload an electricity bill (PDF or image), get a filled solar-load Excel back.

Built for the Energybae AI Intern task. Designed for MSEDCL bills but the
extraction is layout-agnostic, so most Indian DISCOM bills should work.

---

## What it does

1. You drop a bill into the web UI
2. Gemini 1.5 Flash reads it and returns structured JSON
3. You review the values (with confidence chips), fix anything wrong
4. The app writes those values into the input cells of an Excel template
5. You download the filled file with all the solar-load formulas intact

A small solar recommendation preview (system size, payback, savings) shows
up before download so you can sanity-check the inputs.

---

## Run it locally

```bash
git clone <your-repo-url>
cd energybae-solar-bill-extractor

python -m venv .venv && source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt

cp .env.example .env
# put your Gemini key in .env -- free key at https://aistudio.google.com/apikey

streamlit run app.py
```

Open http://localhost:8501.

If you don't want to set up a key right now, tick **Offline mode** in the UI.
That uses a regex extractor that gets the obvious fields (units, amount,
load) on most MSEDCL bills.

### System dependencies

For PDF rendering you need poppler. On macOS:

```bash
brew install poppler tesseract
```

On Ubuntu:

```bash
sudo apt-get install -y poppler-utils tesseract-ocr
```

(Tesseract is only needed for the offline OCR fallback.)

---

## Project layout

```
.
├── app.py                       # Streamlit UI
├── src/
│   ├── config.py                # field defs + cell mapping (single place to edit)
│   ├── extractor/
│   │   ├── pdf_parser.py        # pdfplumber + pdf2image
│   │   ├── ocr.py               # tesseract fallback
│   │   └── llm_extractor.py     # Gemini Flash, JSON-mode, regex fallback
│   ├── excel/
│   │   ├── template_builder.py  # builds the default xlsx
│   │   └── filler.py            # writes inputs only, never touches formulas
│   └── solar/
│       └── calculator.py        # quick recommendation preview
├── templates/
│   └── solar_load_template.xlsx # generated on first run
├── scripts/build_template.py    # rebuild the template from CLI
├── tests/                       # offline tests + filler sanity check
└── EXPLANATION.md               # 4-line writeup for the submission email
```

### Swapping in the real Energybae template

The whole project is structured so that switching templates is one file:

1. Drop the real `.xlsx` at `templates/solar_load_template.xlsx`
2. Open it, note the cell address of each input field
3. Edit `src/config.py` -> `FIELD_TO_CELL`
4. Run the app -- done. No other code changes.

The filler refuses to overwrite any cell whose existing value starts with `=`,
so even if a mapping is wrong you can't accidentally destroy a formula.

---

## How extraction works

- For digital PDFs we pull the text layer with `pdfplumber` AND render
  page images. Both go to Gemini -- the text layer is a hint, the image
  is the source of truth. This is much more robust than text-only.
- For image bills (PNG/JPG) or scanned PDFs we send the image straight
  to Gemini.
- Gemini is called with `response_mime_type="application/json"` and
  `temperature=0.0`, plus a prompt that lists exactly the fields we want
  and forbids guessing. Missing fields return `null`, not made-up values.
- We post-process: numeric coercion, currency stripping, confidence
  capped to 0 for nulls.
- An offline regex extractor is included as a fallback for when no API
  key is set. It's not as good but it works.

---

## Tests

```bash
pytest -q
```

The tests cover the regex fallback (deterministic), the Excel filler
(formulas survive a write), and the field-mapping config.
They do NOT call Gemini -- the LLM call is mocked.

---

## License

MIT, do whatever.
