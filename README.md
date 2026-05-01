# SolarParse — Energybae Solar Bill Extractor

Upload an electricity bill (PDF or image), get a filled solar-load Excel back.

Built for the Energybae AI Intern task. Designed for MSEDCL bills but the
extraction is layout-agnostic, so most Indian DISCOM bills should work.

**Stack:** Python · Streamlit · Google Gemini 2.5 / 2.0 Flash (vision)
· openpyxl · pdfplumber + pdf2image · pytesseract (offline fallback)

---

## For Energybae evaluators

| | |
|---|---|
| Live app | https://solarparse.streamlit.app |
| Repo | https://github.com/rounittxx/SolarParse |
---

## What it does

1. You drop a bill into the web UI
2. Gemini Flash reads it and returns structured JSON (with per-field confidence)
3. You review the values, fix anything wrong inline
4. The app writes those values into the input cells of an Excel template
5. You download the filled file with all the solar-load formulas intact

A small solar recommendation preview (system size, payback, 25-year savings,
CO₂ offset, plus a cumulative-savings chart) shows up before download so you
can sanity-check the inputs.

---

## Deploy a public link (Streamlit Community Cloud, free)

Anyone with the link can use the app. Your Gemini key stays server-side
in Streamlit Secrets, never shipped to the browser.

1. Push your code to GitHub (already done if you're reading this in the repo).
2. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.
3. Click **New app**, then:
   - **Repository:** `rounittxx/SolarParse`
   - **Branch:** `main`
   - **Main file path:** `app.py`
4. Click **Advanced settings → Secrets**, paste:
   ```toml
   GOOGLE_API_KEY = "AIzaSy...your_key..."
   ```
5. Click **Deploy**. About 90 seconds later you get a public URL like
   `https://solarparse.streamlit.app`.

Quota note: Gemini Flash free tier is 15 requests/min and 1,500 requests/day
per key. Plenty for a demo. If the link goes viral, add a per-session
limit or move to a paid tier.

---

## Run it locally

```bash
git clone https://github.com/rounittxx/SolarParse.git
cd SolarParse

python -m venv .venv && source .venv/bin/activate   # on Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# put your Gemini key in .env -- free key at https://aistudio.google.com/apikey

streamlit run app.py
```

Open http://localhost:8501.

If you don't want to set up a key right now, tick **Offline mode** in the
sidebar. That uses a regex extractor that gets the obvious fields (units,
amount, load) on most MSEDCL bills.

### One-command end-to-end check (no UI)

```bash
python scripts/run_gemini_demo.py
```

Loads `.env`, runs Gemini against `samples/sample_msedcl_bill.pdf`, prints
the structured JSON with confidence bars, and writes
`output/filled_demo_bill_gemini.xlsx`. Useful for a quick sanity check or
when you want the AI-extracted Excel without driving the UI.

### System dependencies

For PDF rendering you need poppler. On macOS:

```bash
brew install poppler tesseract
```

On Ubuntu:

```bash
sudo apt-get install -y poppler-utils tesseract-ocr
```

(Tesseract is only needed for the offline OCR fallback — Gemini handles
images directly.)

---

## Project layout

```
.
├── app.py                              # Streamlit UI (single file, ~600 lines)
├── src/
│   ├── config.py                       # field defs + cell mapping (one place to edit)
│   ├── extractor/
│   │   ├── pdf_parser.py               # pdfplumber + pdf2image
│   │   ├── ocr.py                      # tesseract fallback
│   │   └── llm_extractor.py            # Gemini Flash + model fallback chain + regex
│   ├── excel/
│   │   ├── template_builder.py         # builds the default xlsx
│   │   └── filler.py                   # writes inputs only, never touches formulas
│   └── solar/
│       └── calculator.py               # quick recommendation preview
├── templates/
│   └── solar_load_template.xlsx        # generated on first run
├── samples/
│   ├── generate_sample_bill.py         # reportlab MSEDCL bill generator
│   ├── sample_msedcl_bill.pdf          # residential demo bill
│   └── sample_msedcl_noisy.pdf         # commercial demo bill (different layout)
├── scripts/
│   ├── build_template.py               # rebuild the template from CLI
│   └── run_gemini_demo.py              # headless end-to-end run
├── .streamlit/
│   ├── config.toml                     # pins theme to light
│   └── secrets.toml.example            # secrets format for Streamlit Cloud
├── output/
│   └── filled_demo_bill.xlsx           # canonical demo output (committed)
├── tests/                              # 4 offline tests (no network calls)
├── README.md
└── EXPLANATION.md                      # short writeup for the submission email
```

### Swapping in the real Energybae template

The whole project is structured so that switching templates is one file:

1. Drop the real `.xlsx` at `templates/solar_load_template.xlsx`
2. Open it, note the cell address of each input field
3. Edit `src/config.py` → `FIELD_TO_CELL`
4. Run the app. Done. No other code changes.

The filler refuses to overwrite any cell whose existing value starts with `=`,
so even if a mapping is wrong you can't accidentally destroy a formula.
The dedicated test `test_filler_refuses_to_overwrite_a_formula` covers this.

---

## How extraction works

- For digital PDFs we pull the text layer with `pdfplumber` AND render
  page images. Both go to Gemini. The text layer is a hint, the image
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

### Model selection

Google deprecates Flash variants every few months, so
`src/extractor/llm_extractor.py` keeps an ordered fallback list and uses
the first model the API will actually serve:

```
gemini-2.5-flash       # current latest, preferred
gemini-2.0-flash
gemini-flash-latest
gemini-2.0-flash-001
gemini-1.5-flash-latest
gemini-1.5-flash-002
```

If you ever hit `404 models/... is not found`, Google has retired another
name. Add the new one to `MODEL_CANDIDATES` at the top of
`llm_extractor.py` and redeploy.

Auth and quota errors bubble up immediately (no point retrying), only
"not found" / "unsupported" errors trigger the next candidate.

---

## Tests

```bash
pytest -q
```

Four offline tests, no network calls (LLM is mocked):

1. **Regex fallback** picks up obvious fields from a MSEDCL-style sample
2. **Field mapping** is complete (every config field has a target cell)
3. **Filler** writes inputs and preserves the Solar sheet's formulas
4. **Filler** refuses to overwrite a cell that already contains a formula

---

## License

MIT, do whatever.
