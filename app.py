import streamlit as st
import json
import requests
import io
import time

from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

st.set_page_config(page_title="Writing Word Bank Generator", page_icon="✍️", layout="wide")

api_key = st.secrets.get("GEMINI_API_KEY", "")

# Session State Initialization for word persistence
if "wb_data" not in st.session_state:
    st.session_state.wb_data = None
if "categories" not in st.session_state:
    st.session_state.categories = []
if "task_type" not in st.session_state:
    st.session_state.task_type = ""
if "target_band" not in st.session_state:
    st.session_state.target_band = ""


# --- 1. API CASCADE ENGINE ---
def call_gemini_cascade(prompt):
    models = ["gemini-2.5-flash", "gemini-3.5-flash-lite", "gemini-3.8-flash"]
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
def extract_word_bank(task_type, prompt_text, mandatory_words, target_year, target_band, word_count):
    if task_type == "Literary Analysis / GCSE Essay":
        categories = ["Conceptual Nouns", "Analytical Verbs", "Tone Descriptors", "Discourse Markers"]
        category_guidance = (
            "Organise the output strictly into these 4 literature categories: "
            "1. 'Conceptual Nouns' (abstract thematic ideas tailored to this prompt), "
            "2. 'Analytical Verbs' (e.g. subverts, epitomises, forebodes), "
            "3. 'Tone Descriptors' (e.g. didactic, volatile, sombre), "
            "4. 'Discourse Markers' (e.g. fundamentally, conversely, ultimately)."
        )
    elif task_type in ["Creative / Descriptive Writing", "Narrative Writing"]:
        categories = ["Sensory Details", "Atmospheric Adjectives", "Dynamic Verbs", "Figurative Openers"]
        category_guidance = (
            "Organise the output strictly into these 4 descriptive categories: "
            "1. 'Sensory Details', 2. 'Atmospheric Adjectives', "
            "3. 'Dynamic Verbs', 4. 'Figurative Openers'."
        )
    else:
        categories = ["Rhetorical Connectives", "Emotive Nouns", "Persuasive Adverbs", "Counter-argument Markers"]
        category_guidance = (
            "Organise the output strictly into these 4 persuasive categories: "
            "1. 'Rhetorical Connectives', 2. 'Emotive Nouns', "
            "3. 'Persuasive Adverbs', 4. 'Counter-argument Markers'."
        )

    # Flightpath adjustment matrix mapping Year Group + Band to realistic pitch
    flightpath_map = {
        ("Year 7", "Developing (Grades 1-3)"): "Entry / Access Level (KS2 to KS3 bridge, highly grounded and clear vocabulary)",
        ("Year 7", "Reaching (Grades 4-6)"): "Year 7 Secure / Working towards GCSE Grade 2-3 (Accessible Tier 2 academic words, no overly complex Latinate terms)",
        ("Year 7", "Mastering (Grades 7-9)"): "Year 7 High Attainer / Working towards GCSE Grade 4-5 (Ambitious yet clean, practical vocabulary)",
        
        ("Year 8", "Developing (Grades 1-3)"): "Year 8 Foundation / GCSE Grade 1-2 equivalent",
        ("Year 8", "Reaching (Grades 4-6)"): "Year 8 Secure / GCSE Grade 3-4 equivalent (Grounded academic Tier 2 words)",
        ("Year 8", "Mastering (Grades 7-9)"): "Year 8 High Attainer / GCSE Grade 5-6 equivalent",
        
        ("Year 9", "Developing (Grades 1-3)"): "Year 9 Foundation / GCSE Grade 2-3 equivalent",
        ("Year 9", "Reaching (Grades 4-6)"): "Year 9 Secure / GCSE Grade 4-5 equivalent",
        ("Year 9", "Mastering (Grades 7-9)"): "Year 9 High Attainer / GCSE Grade 6-7 equivalent",

        ("Year 10", "Developing (Grades 1-3)"): "GCSE Grades 1-3 Foundation",
        ("Year 10", "Reaching (Grades 4-6)"): "GCSE Grades 4-6 Intermediate",
        ("Year 10", "Mastering (Grades 7-9)"): "GCSE Grades 7-9 Higher Mastery",

        ("Year 11", "Developing (Grades 1-3)"): "GCSE Grades 1-3 Foundation",
        ("Year 11", "Reaching (Grades 4-6)"): "GCSE Grades 4-6 Intermediate",
        ("Year 11", "Mastering (Grades 7-9)"): "GCSE Grades 7-9 Higher Mastery"
    }

    calibrated_level = flightpath_map.get((target_year, target_band), f"{target_year} {target_band}")

    mandatory_instruction = ""
    if mandatory_words.strip():
        mandatory_instruction = (
            f"\n\nMANDATORY REQUIREMENT: You MUST include the following teacher-specified words/phrases "
            f"in the output array, placing them in their most appropriate category: '{mandatory_words}'."
        )

    prompt = (
        f"Act as an expert UK Secondary English teacher. Generate a writing word bank for {target_year} pupils "
        f"calibrated strictly to this secondary flightpath standard: '{calibrated_level}'. Use UK English spelling strictly throughout (e.g., analyse, characterise, emphasise).\n\n"
        f"STRICT PEDAGOGICAL PEDAGOGY & PITCH GUIDELINES:\n"
        f"- CRITICAL: Do NOT generate obscure, archaic, excessively rare, or pretentiously elevated words (e.g. avoid 'perspicacious', 'inimical', 'pusillanimous', 'ubiquitous').\n"
        f"- For Key Stage 3 ({target_year}), focus on high-utility Tier 2 vocabulary that pupils can realistically use to improve their writing tone without sounding unnatural or forced.\n"
        f"- Ensure definitions are short, pupil-friendly, and easy for an 11-16 year old to grasp immediately.\n\n"
        f"Task Type: {task_type}\n"
        f"Task Prompt/Context: '{prompt_text}'{mandatory_instruction}\n\n"
        f"{category_guidance}\n\n"
        f"Generate up to {word_count} total items distributed evenly across the 4 categories.\n"
        f"For each item, include: word, word_class, category (must match one of the 4 specified category names exactly), definition, and a short model_phrase illustrating its use in an English writing context.\n"
        "Return a JSON array where each object strictly contains keys: word, word_class, category, definition, model_phrase."
    )
    return call_gemini_cascade(prompt), categories


def replace_single_word(rejected_word, category, task_type, target_band, current_words):
    existing_list = ", ".join([w.get('word', '') for w in current_words if w.get('word')])
    prompt = (
        f"Act as an expert UK Secondary English teacher. Generate 1 replacement target vocabulary item for a {task_type} task "
        f"for secondary pupils working at flightpath standard '{target_band}'.\n\n"
        f"Category Required: '{category}'\n"
        f"Word to replace: '{rejected_word}'\n"
        f"Do NOT generate any of these words that are already in the word bank: {existing_list}.\n\n"
        f"STRICT RULE: Keep the word accessible, high-utility, and natural for UK secondary pupils. Avoid obscure or archaic terms.\n"
        f"Use UK English spelling strictly throughout. Return a JSON array containing EXACTLY ONE object with keys: word, word_class, category, definition, model_phrase."
    )
    res = call_gemini_cascade(prompt)
    if isinstance(res, list) and len(res) > 0:
        return res[0]
    return None


# --- 3. LANDSCAPE A4 PDF GENERATOR ---
def generate_word_bank_pdf(wb_data, categories, task_type, target_band):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=25, leftMargin=25, topMargin=25, bottomMargin=25)
    elements = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontSize=15, leading=18, spaceAfter=2)
    sub_style = ParagraphStyle('DocSub', parent=styles['Normal'], fontSize=9, leading=11, textColor=colors.HexColor("#555555"), spaceAfter=8)
    cat_header = ParagraphStyle('CatHeader', parent=styles['Heading2'], fontSize=11, leading=14, textColor=colors.HexColor("#005b96"), spaceBefore=6, spaceAfter=4)
    cell_body = ParagraphStyle('CellBody', parent=styles['Normal'], fontSize=8, leading=10)

    elements.append(Paragraph("English Writing Word Bank", title_style))
    elements.append(Paragraph(f"<b>Focus:</b> {task_type} &nbsp;|&nbsp; <b>Level:</b> {target_band}", sub_style))

    for cat in categories:
        cat_items = [item for item in wb_data if item.get('category', '').lower() == cat.lower()]
        if not cat_items:
            continue

        elements.append(Paragraph(f"<b>{cat}</b>", cat_header))

        rows = []
        current_row = []
        for item in cat_items:
            cell_text = (
                f"<b><font size=10 color='#111111'>{item.get('word', '')}</font></b> <i>({item.get('word_class', '')})</i><br/>"
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
            ('PADDING', (0, 0), (-1, -1), 6)
        ]))
        elements.append(t)
        elements.append(Spacer(1, 4))

    doc.build(elements)
    buffer.seek(0)
    return buffer


# --- 4. USER INTERFACE ---
st.title("✍️ Writing Word Bank Generator")

st.sidebar.header("1. Target Options")
wb_task = st.sidebar.selectbox("Task Type", [
    "Creative / Descriptive Writing", 
    "Narrative Writing", 
    "Transactional / Persuasive Writing", 
    "Literary Analysis / GCSE Essay"
], key="wb_task_select")

wb_year = st.sidebar.selectbox("Target Year Group", ["Year 7", "Year 8", "Year 9", "Year 10", "Year 11"], index=3, key="wb_year_select")

wb_band = st.sidebar.selectbox("Target Attainment Band", [
    "Developing (Grades 1-3)", 
    "Reaching (Grades 4-6)", 
    "Mastering (Grades 7-9)"
], index=1, key="wb_band_select")

wb_count = st.sidebar.slider("Number of Words/Phrases", min_value=6, max_value=16, value=12, key="wb_count_slider")

# Main Page Inputs
c1, c2 = st.columns(2)

with c1:
    wb_prompt = st.text_area(
        "Writing Prompt / Context / Essay Title", 
        placeholder="e.g. Write a description of a stormy sea OR Analyse how Priestley presents social responsibility in An Inspector Calls",
        height=140,
        key="wb_prompt_input"
    )

with c2:
    wb_mandatory = st.text_area(
        "Words to Include (Optional)", 
        placeholder="
