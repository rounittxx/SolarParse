# Submission note

I built a Streamlit web app that takes an electricity bill (PDF or image) and
returns a filled Excel solar-load sheet. The bill is sent to Google Gemini 1.5
Flash in JSON mode along with both the rendered page image and any text I
could pull from the PDF layer; that combination handles digital and scanned
bills with the same code path. Extracted values land in a review form with
per-field confidence chips so the user can fix anything before the Excel is
generated, and the filler is hard-coded to write only into mapped input cells
(it refuses to clobber anything that starts with `=`), so the template's
formulas stay intact.

Tools used: Python, Streamlit, Google Gemini 1.5 Flash, pdfplumber, pdf2image,
openpyxl, pytesseract (offline fallback).

What I would improve next: (1) replace the regex offline fallback with a
small fine-tuned layout parser keyed on MSEDCL field positions, (2) add a
multi-bill batch mode so the sales team can drop a folder of PDFs at once,
(3) wire it to a database so each generated proposal becomes a CRM record
instead of a one-off file.
