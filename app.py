import streamlit as st
import json
import requests
import io
import time

from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

st.set_page_config(page_title="Writing Word Bank Generator", page_icon="✍️", layout="wide")

api_key = st.secrets.get("GEMINI_API_KEY", "")


# --- 1. API CASCADE ENGINE ---
def call_gemini_cascade(prompt):
    models = ["gemini-2.5-flash", "gemini-3.5-flash-lite", "gemini-1.5-flash"]
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"response_mime_type": "application/json", "temperature": 0.1}
    }
    clean_key = api_key.strip().replace('"', '').replace("'", "")
    last_err = ""

    for model in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={clean_key}"
        headers = {"Content-Type": "application/json"}
        
        for attempt in range(2):
            try:
                res = requests.post(url, headers=headers, json=payload, timeout=12)
                if res.status_code == 200:
                    raw_text = res.json()["candidates"][0]["content"]["parts"][0]["text"]
                    return json.loads(raw_text)
                elif res.status_code == 503 and attempt == 0:
                    time.sleep(1)
                    continue
                else:
                    last_err = f"HTTP {res.status_code} ({res.text})"
                    break
            except Exception as e:
                last_err = str(e)
                break

    raise Exception(f"API Request Failed: {last_err}")


# --- 2. WORD BANK PROMPT ENGINE ---
def extract_word_bank(task_type, prompt_text, target_year, target_band, word_count):
    if task_type == "Literary Analysis / GCSE Essay":
        category_guidance = (
            "Organise the output strictly into 4 literature categories: "
            "1. 'Conceptual Nouns' (abstract thematic ideas directly tailored to this prompt/text), "
            "2. 'Analytical Verbs' (e.g. subverts, epitomises, forebodes), "
            "3. 'Tone Descriptors' (e.g. didactic, volatile, sombre), "
            "4. 'Discourse Markers' (e.g. fundamentally, conversely, ultimately)."
        )
    elif task_type in ["Creative / Descriptive Writing", "Narrative Writing"]:
        category_guidance = (
            "Organise the output strictly into 4 descriptive categories: "
            "1. 'Sensory Details', 2. 'Atmospheric Adjectives', "
            "3. 'Dynamic Verbs', 4. 'Figurative Openers'."
        )
    else:
        category_guidance = (
            "Organise the output strictly into 4 persuasive categories: "
            "1. 'Rhetorical Connectives', 2. 'Emotive Nouns', "
            "3. 'Persuasive Adverbs', 4. 'Counter-argument Markers'."
        )

    prompt = (
        f"Act as an expert UK Secondary English teacher. Generate a writing word bank for {target_year} pupils "
        f"working at {target_band}. Use UK English spelling strictly throughout (e.g., analyse, characterise, emphasise).\n\n"
        f"Task Type: {task_type}\n"
        f"Task Prompt/Context: '{prompt_text}'\n\n"
        f"{category_guidance}\n\n"
        f"Extract/generate exactly {word_count} target vocabulary words or academic phrases appropriate for this writing task. "
        f"For each item, include: word, word_class, category, definition, and a short model_phrase illustrating its use in an English writing context.\n"
        "Return a JSON array where each object strictly contains keys: word, word_class, category, definition, model_phrase."
    )
    return call_gemini_cascade(prompt)


# --- 3. LANDSCAPE A4 PDF GENERATOR ---
def generate_word_bank_pdf(wb_data, task_type, target_band):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elements = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontSize=16, leading=20, spaceAfter=4)
    sub_style = ParagraphStyle('DocSub', parent=styles['Normal'], fontSize=10, leading=12, textColor=colors.HexColor("#555555"), spaceAfter=10)
    cell_body = ParagraphStyle('CellBody', parent=styles['Normal'], fontSize=8.5, leading=11)

    elements.append(Paragraph("English Writing Word Bank", title_style))
    elements.append(Paragraph(f"<b>Focus:</b> {task_type} &nbsp;|&nbsp; <b>Level:</b> {target_band}", sub_style))

    rows = []
    current_row = []
    for item in wb_data:
        cell_text = (
            f"<b><font size=7 color='#005b96'>{item.get('category', '').upper()}</font></b><br/>"
            f"<b><font size=11 color='#111111'>{item.get('word', '')}</font></b> <i>({item.get('word_class', '')})</i><br/><br/>"
            f"<b>Meaning:</b> {item.get('definition', '')}<br/>"
            f"<b>Usage:</b> <i>\"{item.get('model_phrase', '')}\"</i>"
        )
        current_row.append(Paragraph(cell_text, cell_body))
        if len(current_row) == 3:
            rows.append(current_row)
            current_row = []
            
    if current_row:
        while len(current_row) < 3:
            current_row.append(Paragraph("", cell_body))
        rows.append(current_row)

    t = Table(rows, colWidths=[260, 260, 260])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#fdfdfd")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#dddddd")),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('PADDING', (0, 0), (-1, -1), 8)
    ]))
    
    elements.append(t)
    doc.build(elements)
    buffer.seek(0)
    return buffer


# --- 4. USER INTERFACE ---
st.title("✍️ Writing Word Bank Generator")
st.caption("UK English Secondary Education • Adaptation Station Suite")

col1, col2 = st.columns([1, 2])

with col1:
    wb_task = st.selectbox("Task Type", [
        "Creative / Descriptive Writing", 
        "Narrative Writing", 
        "Transactional / Persuasive Writing", 
        "Literary Analysis / GCSE Essay"
    ], key="wb_task_select")
    wb_year = st.selectbox("Target Year Group", ["Year 7", "Year 8", "Year 9", "Year 10", "Year 11"], index=3, key="wb_year_select")
    wb_band = st.selectbox("Target Attainment Band", [
        "Foundation / Access (Grades 1-3)", 
        "Intermediate / Secure (Grades 4-6)", 
        "Higher / Mastery (Grades 7-9)"
    ], index=1, key="wb_band_select")
    wb_count = st.slider("Number of Words/Phrases", min_value=6, max_value=12, value=9, key="wb_count_slider")
    
with col2:
    wb_prompt = st.text_area(
        "Writing Prompt / Context / Essay Title", 
        placeholder="e.g. Write a description of a stormy sea OR Analyse how Priestley presents social responsibility in An Inspector Calls",
        height=180,
        key="wb_prompt_input"
    )
    generate_wb = st.button("Generate Word Bank Grid", type="primary", key="wb_generate_btn")

if generate_wb:
    if not wb_prompt.strip():
        st.warning("Please enter a writing prompt or context.")
    elif not api_key:
        st.error("Missing GEMINI_API_KEY in Streamlit Secrets.")
    else:
        with st.spinner("Generating UK English Word Bank..."):
            try:
                wb_data = extract_word_bank(wb_task, wb_prompt, wb_year, wb_band, wb_count)
                wb_pdf = generate_word_bank_pdf(wb_data, wb_task, wb_band)

                st.markdown("---")
                col_title, col_btn = st.columns([3, 1])
                col_title.subheader("Generated Writing Support Grid")
                col_btn.download_button(
                    label="📥 Download Printable PDF (A4)",
                    data=wb_pdf,
                    file_name="Writing_Word_Bank.pdf",
                    mime="application/pdf",
                    type="primary",
                    key="dl_wb_pdf"
                )

                cols = st.columns(3)
                for idx, item in enumerate(wb_data):
                    with cols[idx % 3]:
                        with st.container(border=True):
                            st.caption(f"{item.get('category', 'Vocabulary')} • *({item.get('word_class', '')})*")
                            st.subheader(item.get('word', ''))
                            st.write(f"**Meaning:** {item.get('definition', '')}")
                            st.write(f"**Usage:** *\"{item.get('model_phrase', '')}\"*")

            except Exception as e:
                st.error(f"Error generating Word Bank: {e}")
