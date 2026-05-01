# Streamlit UI -- single-file on purpose. Easy to demo, easy to read.
#
# Flow:
#   upload (or pick a sample) -> extract -> review/edit -> generate -> download
#
# I wanted this to feel like a real product, not a streamlit demo,
# so there's a fair bit of custom CSS and a 4-step stepper at the top.
# Nothing fancy in terms of dependencies though -- just Streamlit + Pillow.

import io
import time
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from PIL import Image

from src.config import FIELDS, FIELD_TO_CELL, SOLAR_DEFAULTS
from src.excel.filler import fill_template, report
from src.excel.template_builder import build as build_template
from src.extractor.llm_extractor import extract_with_gemini, extract_from_text_only
from src.extractor.ocr import ocr_images
from src.extractor.pdf_parser import extract_text_from_pdf, looks_like_scanned
from src.solar.calculator import recommend


load_dotenv()

ROOT = Path(__file__).parent
TEMPLATE = ROOT / "templates" / "solar_load_template.xlsx"
SAMPLES = ROOT / "samples"
OUTPUT_DIR = ROOT / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


# ============================================================
# Page config + theming
# ============================================================

st.set_page_config(
    page_title="Energybae | Solar Bill Extractor",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      /* ---- canvas ---- */
      /* Force a light canvas + dark default text. Every custom container
         below ALSO sets its own color, so nothing relies on inheritance. */
      .stApp { background: linear-gradient(180deg, #FAFCFB 0%, #F4F7F5 100%) !important;
               color: #0F1B14 !important; }
      .block-container { padding-top: 1.2rem; padding-bottom: 4rem; max-width: 1280px; }

      /* ---- typography ---- */
      h1, h2, h3, h4, h5, h6 { color: #0F1B14 !important; letter-spacing: -0.01em; }
      .stApp p, .stApp span, .stApp label, .stApp li { color: #1F2937; }
      .muted { color:#6B7280 !important; font-size:0.86rem; }
      .tiny  { color:#9CA3AF !important; font-size:0.74rem; }

      /* ---- hero ---- */
      .hero {
        background: linear-gradient(135deg, #0F4C36 0%, #1FA463 100%);
        color: #FFFFFF !important; padding: 28px 32px; border-radius: 18px;
        box-shadow: 0 6px 22px rgba(15,76,54,0.15);
      }
      .hero h1  { color: #FFFFFF !important; margin: 0; font-size: 1.8rem; font-weight: 700; }
      .hero .sub{ color: rgba(255,255,255,0.92) !important; margin-top: 4px; font-size: 0.95rem; }

      /* ---- stepper ---- */
      .stepper { display:flex; gap:0; margin: 18px 0 10px 0;
                 background:#FFFFFF !important; padding: 8px; border-radius: 12px;
                 border:1px solid #E5E7EB; }
      .step { flex:1; padding: 10px 14px; text-align:center; font-size:0.8rem;
              color:#9CA3AF !important; font-weight:600; border-radius:8px; transition:all .2s; }
      .step.done   { color:#0F4C36 !important; }
      .step.active { background:#1FA463 !important; color:#FFFFFF !important; }
      .step .num { display:inline-block; width:22px; height:22px;
                   border-radius:50%; background:#E5E7EB; color:#6B7280;
                   font-size:0.75rem; line-height:22px; margin-right:6px; }
      .step.done   .num { background:#DCFCE7; color:#0F4C36; }
      .step.active .num { background:rgba(255,255,255,.25); color:#FFFFFF; }

      /* ---- cards (always white bg, always dark text) ---- */
      .card { background:#FFFFFF !important; padding:18px 20px; border-radius:14px;
              border:1px solid #E5E7EB; height:100%; color:#0F1B14 !important; }
      .card * { color: inherit; }
      .stat-num { font-size:1.55rem; font-weight:700; color:#0F1B14 !important; }
      .stat-lbl { font-size:0.72rem; color:#6B7280 !important; text-transform:uppercase;
                  letter-spacing:.05em; margin-bottom:4px; }

      /* ---- confidence pills + bars ---- */
      .pill { display:inline-block; padding:2px 9px; border-radius:999px;
              font-size:0.7rem; font-weight:700; }
      .pill.ok    { background:#DCFCE7 !important; color:#166534 !important; }
      .pill.warn  { background:#FEF3C7 !important; color:#92400E !important; }
      .pill.bad   { background:#FEE2E2 !important; color:#991B1B !important; }
      .pill.edit  { background:#E0E7FF !important; color:#3730A3 !important; }

      .bar { height:4px; background:#F3F4F6; border-radius:999px; overflow:hidden; margin-top:4px; }
      .bar > span { display:block; height:100%; border-radius:999px; }
      .bar.ok   > span { background:#22C55E; }
      .bar.warn > span { background:#F59E0B; }
      .bar.bad  > span { background:#EF4444; }

      /* ---- footer ---- */
      footer { visibility: hidden; }
      .made-by { text-align:center; color:#6B7280 !important; font-size:0.78rem; margin-top:30px; }
      .made-by a { color:#1FA463 !important; text-decoration:none; }

      /* ---- streamlit native overrides ---- */
      div[data-testid="stFileUploader"] section {
        background:#FFFFFF !important; color:#0F1B14 !important;
        border: 2px dashed #1FA463; border-radius: 14px; }
      div[data-testid="stFileUploader"] section:hover { border-color:#0F4C36; }
      div[data-testid="stFileUploader"] section * { color:#0F1B14 !important; }

      .stButton > button[kind="primary"] {
        background:#1FA463 !important; color:#FFFFFF !important;
        border: 0; font-weight: 600;
        box-shadow: 0 2px 8px rgba(31,164,99,0.25); }
      .stButton > button[kind="primary"]:hover { background:#0F4C36 !important; }
      .stButton > button[kind="secondary"] {
        background:#FFFFFF !important; color:#0F1B14 !important;
        border:1px solid #E5E7EB !important; }

      /* ---- sidebar contrast ---- */
      section[data-testid="stSidebar"] { background:#FFFFFF !important; }
      section[data-testid="stSidebar"] * { color:#1F2937 !important; }
      section[data-testid="stSidebar"] h1,
      section[data-testid="stSidebar"] h2,
      section[data-testid="stSidebar"] h3,
      section[data-testid="stSidebar"] h4 { color:#0F1B14 !important; }
      section[data-testid="stSidebar"] .stCaption,
      section[data-testid="stSidebar"] small { color:#6B7280 !important; }
      section[data-testid="stSidebar"] .stButton > button {
        background:#F9FAFB !important; color:#0F1B14 !important;
        border:1px solid #E5E7EB !important; font-weight:500; }
      section[data-testid="stSidebar"] .stButton > button:hover {
        background:#F3F4F6 !important; border-color:#1FA463 !important; }

      /* ---- streamlit alerts (info/warning/success) keep their colors ---- */
      div[data-testid="stAlert"] { color:#0F1B14 !important; }
      div[data-testid="stAlert"] * { color: inherit !important; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# State + helpers
# ============================================================

ss = st.session_state
ss.setdefault("extracted", None)        # {"fields":..., "confidence":...}
ss.setdefault("raw_bytes", None)
ss.setdefault("preview_images", None)
ss.setdefault("file_name", None)
ss.setdefault("output_path", None)
ss.setdefault("extract_seconds", None)
ss.setdefault("user_edits", set())      # field keys the user manually changed


def current_step():
    if ss.output_path:           return 4
    if ss.extracted:             return 3
    if ss.raw_bytes:             return 2
    return 1


def render_stepper():
    step = current_step()
    labels = ["Upload", "Extract", "Review", "Generate"]
    chunks = []
    for i, label in enumerate(labels, start=1):
        cls = "step"
        if i == step:    cls += " active"
        elif i < step:   cls += " done"
        chunks.append(f"<div class='{cls}'><span class='num'>{i}</span>{label}</div>")
    st.markdown("<div class='stepper'>" + "".join(chunks) + "</div>",
                unsafe_allow_html=True)


def reset_for_new_bill():
    ss.extracted = None
    ss.raw_bytes = None
    ss.preview_images = None
    ss.file_name = None
    ss.output_path = None
    ss.extract_seconds = None
    ss.user_edits = set()


def confidence_visual(c, missing):
    if missing:
        return ("bad", "missing", 0)
    pct = int(round(c * 100))
    if c >= 0.8:   return ("ok",   f"{pct}% confident", pct)
    if c >= 0.5:   return ("warn", f"{pct}% confident", pct)
    return ("bad", f"{pct}% confident", pct)


# ============================================================
# First-run setup
# ============================================================

if not TEMPLATE.exists():
    with st.spinner("First run -- generating the default Excel template..."):
        build_template(TEMPLATE)


# ============================================================
# Sidebar
# ============================================================

with st.sidebar:
    st.markdown(
        "<div style='display:flex;align-items:center;gap:8px;'>"
        "<span style='color:#1FA463;font-size:1.4rem;line-height:1'>◆</span>"
        "<span style='font-weight:700;letter-spacing:0.14em;font-size:0.86rem;"
        "color:#0F1B14'>ENERGYBAE</span>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.caption("Solar Bill Extractor · v0.1")

    st.divider()
    st.markdown("**Mode**")
    use_offline = st.toggle(
        "Offline mode",
        value=False,
        help="Skip Gemini and use a regex-only extractor. Free, instant, less accurate. "
             "Use this if you don't have a GOOGLE_API_KEY set up.",
    )
    if not use_offline:
        st.caption("Using Gemini 1.5 Flash (vision)")
    else:
        st.caption("Using regex-only fallback")

    st.divider()
    st.markdown("**Try a sample**")
    st.caption("Skip the upload step.")

    samples = sorted(SAMPLES.glob("sample_*.pdf"))
    for sp in samples:
        nice = sp.stem.replace("sample_", "").replace("_", " ").title()
        if st.button(f"📄  {nice}", use_container_width=True, key=f"sample_{sp.name}"):
            reset_for_new_bill()
            ss.raw_bytes = sp.read_bytes()
            ss.file_name = sp.name
            st.rerun()

    st.divider()
    if ss.raw_bytes:
        if st.button("↻  Process another bill", use_container_width=True):
            reset_for_new_bill()
            st.rerun()

    st.divider()
    with st.expander("About", expanded=False):
        st.caption(
            "Built for the Energybae AI Intern task. The pipeline is "
            "PDF/image -> Gemini vision -> JSON validation -> Excel "
            "template fill (formulas preserved) -> download."
        )
        st.caption("[GitHub repo](https://github.com/rounittxx/Volt_extract)")


# ============================================================
# Hero
# ============================================================

st.markdown(
    """
    <div class='hero'>
      <div style='font-size:0.72rem;letter-spacing:0.18em;font-weight:600;
                  opacity:0.85;margin-bottom:6px;'>ENERGYBAE&nbsp;&nbsp;//&nbsp;&nbsp;AI&nbsp;TOOLING</div>
      <h1>Solar Bill Extractor</h1>
      <div class='sub'>Drop in any electricity bill, get a filled solar-load Excel back in seconds.</div>
    </div>
    """,
    unsafe_allow_html=True,
)

render_stepper()


# ============================================================
# Step 1 -- Upload
# ============================================================

if current_step() == 1:
    st.markdown("### 1. Upload a bill")
    st.caption("PDF or image. Drag and drop, or click to browse. We support most Indian DISCOM bills (MSEDCL, BEST, Tata Power, Adani, etc.).")

    upload = st.file_uploader(
        " ", type=["pdf", "png", "jpg", "jpeg"],
        accept_multiple_files=False, label_visibility="collapsed",
    )

    if upload:
        ss.raw_bytes = upload.read()
        ss.file_name = upload.name
        st.rerun()

    # how-it-works strip -- gives the user (and reviewer!) the mental model upfront
    st.markdown("<div style='margin-top:32px;'></div>", unsafe_allow_html=True)
    st.markdown("##### How it works")
    cols = st.columns(4)
    bullets = [
        ("📤", "Upload",  "PDF or image of any electricity bill."),
        ("🧠", "Extract", "Gemini reads the bill and returns structured JSON."),
        ("✏️", "Review",  "Confidence chips on every field. Edit if needed."),
        ("📊", "Download", "Filled Excel with intact solar-load formulas."),
    ]
    for col, (ic, t, d) in zip(cols, bullets):
        col.markdown(
            f"<div class='card'><div style='font-size:1.6rem'>{ic}</div>"
            f"<div style='font-weight:700;margin-top:6px'>{t}</div>"
            f"<div class='muted' style='margin-top:4px'>{d}</div></div>",
            unsafe_allow_html=True,
        )


# ============================================================
# Step 2 -- Extract (we have bytes, no extraction yet)
# ============================================================

elif current_step() == 2:
    st.markdown("### 2. Extract the data")

    # render preview images (PDFs get rasterised, images load directly)
    if ss.file_name.lower().endswith(".pdf"):
        text_hint, images = extract_text_from_pdf(ss.raw_bytes)
        ss.preview_images = images
        ss._text_hint = text_hint   # stash for the LLM call
        if text_hint and looks_like_scanned(text_hint):
            st.info("This PDF looks scanned. We'll send the rendered image to Gemini.")
    else:
        ss.preview_images = [Image.open(io.BytesIO(ss.raw_bytes))]
        ss._text_hint = ""

    left, right = st.columns([0.55, 0.45], gap="large")

    with left:
        st.markdown("##### Bill preview")
        if ss.preview_images:
            st.image(ss.preview_images[0], use_container_width=True)
        else:
            st.warning("Couldn't render a preview, but extraction will still try the text path.")

    with right:
        st.markdown("##### Ready to extract")
        st.markdown(
            f"<div class='card'><div class='stat-lbl'>File</div>"
            f"<div style='font-weight:600;color:#0F1B14;margin-top:2px'>{ss.file_name}</div>"
            f"<div class='tiny' style='margin-top:8px'>{len(ss.raw_bytes)/1024:.1f} KB · "
            f"{'PDF (' + str(len(ss.preview_images)) + ' page' + ('s' if len(ss.preview_images)!=1 else '') + ')' if ss.file_name.lower().endswith('.pdf') else 'Image'}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
        st.write("")

        st.caption("Click below to send the bill through the AI pipeline. Most bills extract in 2-5 seconds.")

        if st.button("🧠  Extract data", type="primary", use_container_width=True):
            t0 = time.time()
            try:
                with st.status("Processing bill...", expanded=True) as status:
                    st.write("• Reading file")
                    if use_offline:
                        st.write("• Running offline regex extractor")
                        text = ss._text_hint or ocr_images(ss.preview_images)
                        ss.extracted = extract_from_text_only(text)
                    else:
                        st.write("• Calling Gemini 1.5 Flash (vision)")
                        ss.extracted = extract_with_gemini(
                            ss.preview_images, text_hint=ss._text_hint
                        )
                    st.write("• Validating fields & computing confidence")
                    status.update(label="Extraction complete", state="complete")
                ss.extract_seconds = round(time.time() - t0, 2)
                st.rerun()
            except Exception as e:
                st.error(f"Extraction failed: {e}")
                st.caption("Try the **Offline mode** toggle in the sidebar, or check that "
                           "GOOGLE_API_KEY is set in `.env`.")


# ============================================================
# Step 3 -- Review (extraction done, no Excel yet)
# ============================================================

elif current_step() == 3:
    fields = ss.extracted["fields"]
    confs  = ss.extracted["confidence"]

    # ---- stats banner ----
    n_extracted = sum(1 for v in fields.values() if v not in (None, ""))
    avg_conf = (sum(confs.values()) / len(confs)) if confs else 0
    high_conf = sum(1 for c in confs.values() if c >= 0.8)

    bcols = st.columns(4)
    cards = [
        ("Time taken",       f"{ss.extract_seconds or 0:.1f}s"),
        ("Fields extracted", f"{n_extracted}/{len(fields)}"),
        ("Avg confidence",   f"{int(avg_conf*100)}%"),
        ("High-confidence",  f"{high_conf} fields"),
    ]
    for col, (lbl, val) in zip(bcols, cards):
        col.markdown(
            f"<div class='card'><div class='stat-lbl'>{lbl}</div>"
            f"<div class='stat-num'>{val}</div></div>",
            unsafe_allow_html=True,
        )

    st.markdown("<div style='margin-top:18px;'></div>", unsafe_allow_html=True)
    st.markdown("### 3. Review & edit")
    st.caption("Confidence comes from the model. Anything wrong or missing? Fix it inline.")

    left, right = st.columns([0.42, 0.58], gap="large")

    # ---- left: bill preview ----
    with left:
        st.markdown("##### Source bill")
        if ss.preview_images:
            st.image(ss.preview_images[0], use_container_width=True)

    # ---- right: editable form ----
    with right:
        edited = {}
        for f in FIELDS:
            v = fields.get(f.key)
            c = confs.get(f.key, 0.0)
            missing = v in (None, "")
            tone, conf_text, pct = confidence_visual(c, missing)

            edited_pill = ""
            if f.key in ss.user_edits:
                edited_pill = "<span class='pill edit' style='margin-left:6px'>edited</span>"

            unit_html = (
                f" <span style='color:#9CA3AF;font-size:0.74rem;font-weight:500'>"
                f"({f.unit})</span>" if f.unit else ""
            )

            label_html = (
                f"<div style='display:flex;align-items:center;justify-content:space-between;"
                f"margin-top:4px'>"
                f"<div style='color:#0F1B14;font-weight:600;font-size:0.92rem'>"
                f"{f.label}{unit_html}{edited_pill}</div>"
                f"<div><span class='pill {tone}'>{conf_text}</span></div>"
                f"</div>"
                f"<div class='bar {tone}'><span style='width:{pct}%'></span></div>"
            )
            st.markdown(label_html, unsafe_allow_html=True)

            if f.key in ("units_consumed", "total_bill_amount",
                         "connected_load", "sanctioned_load"):
                new_val = st.number_input(
                    label="value",
                    value=float(v) if isinstance(v, (int, float)) else 0.0,
                    min_value=0.0,
                    step=1.0 if f.key.endswith("amount") or f.key.endswith("consumed") else 0.1,
                    format="%.2f",
                    key=f"in_{f.key}",
                    label_visibility="collapsed",
                )
            else:
                new_val = st.text_input(
                    label="value",
                    value="" if v is None else str(v),
                    key=f"in_{f.key}",
                    label_visibility="collapsed",
                    placeholder="(missing -- please fill in)" if missing else "",
                )

            # track edits so we can show a chip
            original = "" if v is None else (str(v) if not isinstance(v, (int, float)) else float(v))
            if isinstance(new_val, str):
                if new_val != original:
                    ss.user_edits.add(f.key)
            else:
                if abs((new_val or 0) - (original or 0)) > 1e-6:
                    ss.user_edits.add(f.key)

            edited[f.key] = new_val
            st.markdown("<div style='margin-bottom:6px'></div>", unsafe_allow_html=True)

    # ---- solar preview + chart ----
    rec = recommend(
        units_consumed_kwh=edited.get("units_consumed") or 0,
        sanctioned_load_kw=edited.get("sanctioned_load"),
    )

    if rec:
        st.markdown("<div style='margin-top:18px;'></div>", unsafe_allow_html=True)
        st.markdown("### Solar recommendation (preview)")

        scols = st.columns(4)
        items = [
            ("Recommended size",  f"{rec['recommended_kw']} kW"),
            ("Estimated cost",    f"₹{rec['system_cost_inr']:,}"),
            ("Annual savings",    f"₹{rec['annual_savings_inr']:,}"),
            ("Payback",           f"{rec['payback_years']} yrs" if rec['payback_years'] else "--"),
        ]
        for col, (lbl, val) in zip(scols, items):
            col.markdown(
                f"<div class='card'><div class='stat-lbl'>{lbl}</div>"
                f"<div class='stat-num'>{val}</div></div>",
                unsafe_allow_html=True,
            )

        # 25-year cumulative savings chart
        years = list(range(0, SOLAR_DEFAULTS["system_life_years"] + 1))
        deg = SOLAR_DEFAULTS["panel_degradation_pct"] / 100.0
        cum = []
        running = -rec["system_cost_inr"]
        for yr in years:
            if yr == 0:
                cum.append(running)
                continue
            # simple model: savings degrade ~0.7%/yr as panels age
            running += rec["annual_savings_inr"] * ((1 - deg) ** (yr - 1))
            cum.append(round(running))
        chart_df = pd.DataFrame({"Year": years, "Cumulative net savings (INR)": cum})
        chart_df = chart_df.set_index("Year")
        st.line_chart(chart_df, height=240)
        st.caption(
            f"Annual gen ≈ {rec['annual_generation_kwh']:,} kWh · "
            f"CO₂ offset ≈ {rec['co2_offset_tpy']} tonnes/yr · "
            f"breakeven around year {rec['payback_years']} · "
            f"25-yr net savings ≈ ₹{rec['lifetime_savings_inr']:,}"
        )

    # ---- generate ----
    st.markdown("<div style='margin-top:22px;'></div>", unsafe_allow_html=True)
    st.markdown("### 4. Generate Excel")

    missing_required = [f.label for f in FIELDS
                        if f.required and not edited.get(f.key)]
    if missing_required:
        st.warning(
            "Missing required fields: " + ", ".join(missing_required) +
            ". You can still generate the file -- those cells will be left blank."
        )

    confirm = st.checkbox(
        "I have reviewed the values above and they look correct.",
        key="confirm",
    )

    if st.button("📥  Generate filled Excel", type="primary",
                 use_container_width=True, disabled=not confirm):
        out_name = f"solar_load_{Path(ss.file_name).stem}.xlsx"
        out_path = OUTPUT_DIR / out_name
        with st.spinner("Filling template (formulas preserved)..."):
            fill_template(TEMPLATE, edited, out_path)
        ss.output_path = out_path
        st.rerun()


# ============================================================
# Step 4 -- Done, offer download
# ============================================================

elif current_step() == 4:
    st.success("Excel generated successfully")

    # --- download card ---
    with open(ss.output_path, "rb") as fh:
        data = fh.read()

    left, right = st.columns([0.6, 0.4], gap="large")
    with left:
        st.markdown("##### Your filled solar-load file")
        st.markdown(
            f"<div class='card'>"
            f"<div class='stat-lbl'>Output</div>"
            f"<div style='font-weight:600;color:#0F1B14;margin-top:2px'>"
            f"{Path(ss.output_path).name}</div>"
            f"<div class='tiny' style='margin-top:8px'>{len(data)/1024:.1f} KB · "
            f"3 sheets (Inputs, Solar, Notes) · all formulas intact</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
        st.write("")
        st.download_button(
            "⬇  Download Excel",
            data=data,
            file_name=Path(ss.output_path).name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            use_container_width=True,
        )

    with right:
        st.markdown("##### What's inside")
        st.markdown(
            "- **Inputs sheet** — all bill fields you reviewed\n"
            "- **Solar sheet** — live formulas: recommended kW, cost, payback, "
            "25-year savings, CO₂ offset\n"
            "- **Notes sheet** — assumptions Energybae can tweak per customer"
        )

    # audit trail of what was written
    rep = report()
    if rep:
        with st.expander("Cell-by-cell write log"):
            wrote_df = pd.DataFrame(
                [{"Field": k, "Cell": c, "Value": v} for (k, c, v) in rep["written"]]
            )
            st.dataframe(wrote_df, use_container_width=True, hide_index=True)
            if rep["skipped"]:
                st.warning("Skipped cells (formula collisions): " + str(rep["skipped"]))

    st.write("")
    if st.button("📄  Process another bill", use_container_width=True):
        reset_for_new_bill()
        st.rerun()


# ============================================================
# Footer
# ============================================================

st.markdown(
    "<div class='made-by'>"
    "Built for Energybae · "
    "PDFs are processed in-memory and never stored · "
    "<a href='https://github.com/rounittxx/Volt_extract' style='color:#1FA463;text-decoration:none'>Source on GitHub</a>"
    "</div>",
    unsafe_allow_html=True,
)
