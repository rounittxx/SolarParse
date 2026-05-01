# Streamlit UI -- single file on purpose. Easy to read, easy to demo.
#
# Flow:
#   upload bill -> extract with Gemini -> review/edit fields ->
#   confirm -> fill template -> download

import io
import time
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from PIL import Image

from src.config import FIELDS, FIELD_BY_KEY, FIELD_TO_CELL
from src.excel.filler import fill_template, report
from src.excel.template_builder import build as build_template
from src.extractor.llm_extractor import extract_with_gemini, extract_from_text_only
from src.extractor.ocr import ocr_images
from src.extractor.pdf_parser import extract_text_from_pdf, looks_like_scanned
from src.solar.calculator import recommend


load_dotenv()

ROOT = Path(__file__).parent
TEMPLATE = ROOT / "templates" / "solar_load_template.xlsx"
OUTPUT_DIR = ROOT / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


# ---------- page config + a tiny bit of CSS ----------

st.set_page_config(
    page_title="Energybae Solar Bill Extractor",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
      .stApp { background: #fafafa; }
      .small  { color:#6B7280; font-size:0.85rem; }
      .pill   { display:inline-block; padding:2px 10px; border-radius:999px;
                font-size:0.75rem; font-weight:600; }
      .ok     { background:#DCFCE7; color:#166534; }
      .warn   { background:#FEF3C7; color:#92400E; }
      .bad    { background:#FEE2E2; color:#991B1B; }
      .stat-card{ background:white; padding:18px 20px; border-radius:14px;
                  border:1px solid #E5E7EB; }
      .stat-num{ font-size:1.6rem; font-weight:700; color:#111827; }
      .stat-lbl{ font-size:0.78rem; color:#6B7280; text-transform:uppercase;
                 letter-spacing:.04em; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------- header ----------

c1, c2 = st.columns([0.8, 0.2])
with c1:
    st.markdown("# ⚡ Energybae Solar Bill Extractor")
    st.markdown(
        "<span class='small'>Upload an electricity bill. Get a filled solar-load Excel back. "
        "Built for MSEDCL-style bills, works on most Indian DISCOMs.</span>",
        unsafe_allow_html=True,
    )
with c2:
    st.write("")
    st.write("")
    st.markdown("<div class='small'>v0.1 &nbsp;·&nbsp; Gemini 1.5 Flash</div>",
                unsafe_allow_html=True)

st.divider()


# ---------- ensure template exists ----------

if not TEMPLATE.exists():
    with st.spinner("First run -- generating the default Excel template..."):
        build_template(TEMPLATE)


# ---------- session state ----------

ss = st.session_state
ss.setdefault("extracted", None)        # dict from llm_extractor
ss.setdefault("preview_images", None)
ss.setdefault("file_name", None)
ss.setdefault("output_path", None)


# ---------- step 1: upload ----------

st.subheader("1. Upload the bill")
upload = st.file_uploader(
    "Drag & drop a PDF or image (PNG/JPG)",
    type=["pdf", "png", "jpg", "jpeg"],
    accept_multiple_files=False,
)

col_a, col_b = st.columns([0.5, 0.5])
with col_a:
    use_offline = st.checkbox(
        "Offline mode (skip Gemini, use regex extractor)",
        value=False,
        help="Useful if you don't have an API key handy. Less accurate, but free and instant.",
    )

if upload and (ss.file_name != upload.name):
    # new file -> reset everything that depended on the previous one
    ss.extracted = None
    ss.output_path = None
    ss.file_name = upload.name


# ---------- step 2: extract ----------

if upload:
    st.subheader("2. Extract")

    images = []
    text_hint = ""
    raw = upload.read()

    if upload.type == "application/pdf":
        with st.spinner("Reading PDF..."):
            text_hint, images = extract_text_from_pdf(raw)
        if looks_like_scanned(text_hint):
            st.info("PDF looks scanned -- relying on the image + OCR path.")
    else:
        images = [Image.open(io.BytesIO(raw))]

    ss.preview_images = images

    # show a thumbnail so the user knows the right file landed
    if images:
        with st.expander("Bill preview", expanded=False):
            st.image(images[0], use_container_width=True)

    extract_btn = st.button("Extract data from bill",
                            type="primary",
                            disabled=ss.extracted is not None)

    if extract_btn:
        t0 = time.time()
        try:
            with st.spinner("Processing bill..."):
                if use_offline:
                    text_for_offline = text_hint or ocr_images(images)
                    ss.extracted = extract_from_text_only(text_for_offline)
                else:
                    ss.extracted = extract_with_gemini(images, text_hint=text_hint)
            st.success(f"Extraction complete in {time.time()-t0:.1f}s")
        except Exception as e:
            st.error(f"Extraction failed: {e}")
            st.caption("Tip: tick 'Offline mode' to try the regex fallback, "
                       "or check that GOOGLE_API_KEY is set in .env")


# ---------- step 3: review / edit ----------

if ss.extracted:
    st.subheader("3. Review & edit")
    st.caption("Anything wrong? Fix it here. Confidence chips show how sure the AI was.")

    fields = ss.extracted["fields"]
    confs = ss.extracted["confidence"]

    edited = {}

    cols = st.columns(2)
    for i, f in enumerate(FIELDS):
        with cols[i % 2]:
            v = fields.get(f.key)
            c = confs.get(f.key, 0.0)

            # confidence pill
            if v in (None, ""):
                pill = "<span class='pill bad'>missing</span>"
            elif c >= 0.8:
                pill = f"<span class='pill ok'>high · {int(c*100)}%</span>"
            elif c >= 0.5:
                pill = f"<span class='pill warn'>medium · {int(c*100)}%</span>"
            else:
                pill = f"<span class='pill bad'>low · {int(c*100)}%</span>"

            label_html = f"**{f.label}**"
            if f.unit:
                label_html += f" <span class='small'>({f.unit})</span>"
            st.markdown(f"{label_html} &nbsp; {pill}", unsafe_allow_html=True)

            # numeric vs text input
            if f.key in ("units_consumed", "total_bill_amount",
                         "connected_load", "sanctioned_load"):
                edited[f.key] = st.number_input(
                    label="value",
                    value=float(v) if isinstance(v, (int, float)) else 0.0,
                    min_value=0.0,
                    step=1.0 if f.key.endswith("amount") or f.key.endswith("consumed") else 0.1,
                    format="%.2f",
                    key=f"in_{f.key}",
                    label_visibility="collapsed",
                )
            else:
                edited[f.key] = st.text_input(
                    label="value",
                    value="" if v is None else str(v),
                    key=f"in_{f.key}",
                    label_visibility="collapsed",
                )

    # ---------- step 3b: solar preview ----------
    rec = recommend(
        units_consumed_kwh=edited.get("units_consumed") or 0,
        sanctioned_load_kw=edited.get("sanctioned_load"),
    )
    if rec:
        st.subheader("Solar recommendation (preview)")
        cards = st.columns(4)
        items = [
            ("Recommended size",     f"{rec['recommended_kw']} kW"),
            ("Estimated cost",       f"₹{rec['system_cost_inr']:,}"),
            ("Annual savings",       f"₹{rec['annual_savings_inr']:,}"),
            ("Payback",              f"{rec['payback_years']} yrs" if rec['payback_years'] else "--"),
        ]
        for col, (lbl, val) in zip(cards, items):
            col.markdown(
                f"<div class='stat-card'><div class='stat-lbl'>{lbl}</div>"
                f"<div class='stat-num'>{val}</div></div>",
                unsafe_allow_html=True,
            )
        st.caption(
            f"Annual generation ≈ {rec['annual_generation_kwh']:,} kWh · "
            f"CO₂ offset ≈ {rec['co2_offset_tpy']} tonnes/yr · "
            f"25-yr net savings ≈ ₹{rec['lifetime_savings_inr']:,}"
        )

    # ---------- step 4: confirm + generate ----------
    st.subheader("4. Generate Excel")

    missing_required = [f.label for f in FIELDS
                        if f.required and not edited.get(f.key)]
    if missing_required:
        st.warning("Missing required fields: " + ", ".join(missing_required) +
                   ". You can still generate the file; those cells will stay blank.")

    confirm = st.checkbox("I have reviewed the values above and they look correct.")

    gen = st.button("Generate Excel", type="primary", disabled=not confirm)
    if gen:
        out_name = f"solar_load_{ss.file_name.rsplit('.', 1)[0]}.xlsx"
        out_path = OUTPUT_DIR / out_name
        with st.spinner("Filling template..."):
            fill_template(TEMPLATE, edited, out_path)
        ss.output_path = out_path
        st.success("Excel generated successfully")

        # show what got written -- nice for debugging + transparency
        rep = report()
        if rep:
            with st.expander("What got written", expanded=False):
                st.write({
                    "Output file": rep["output"],
                    "Cells written": [
                        {"field": k, "cell": c, "value": v}
                        for (k, c, v) in rep["written"]
                    ],
                    "Cells skipped (formula collisions)": rep["skipped"],
                })

if ss.output_path and Path(ss.output_path).exists():
    with open(ss.output_path, "rb") as fh:
        st.download_button(
            "Download filled Excel",
            data=fh.read(),
            file_name=Path(ss.output_path).name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
        )

st.divider()
st.markdown(
    "<div class='small'>Built for the Energybae AI Intern task. "
    "Source on GitHub. PDFs are processed in-memory and never stored.</div>",
    unsafe_allow_html=True,
)
