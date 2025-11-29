import os
import io
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ---------- SYSTEM PROMPTS ----------

neurohr_system_prompt = """
You are an experienced HR specialist and CV reviewer.

Your job:
- Analyze the candidate's CV text.
- Give a score from 0 to 10.
- Provide clear, practical, and kind feedback.
- Output structure:
1) Overall score
2) Strengths
3) Weaknesses
4) Suggestions and example improvements.
"""

resume_missing_system_prompt = """
You are an HR expert helping a candidate improve their CV.

Given the CV text, identify which standard CV sections are missing or weak.
Standard sections: Personal information, Professional summary, Work experience,
Education, Skills, Languages, Certifications, Projects, Volunteering, Other.

Return a friendly text addressed to the user that:
- briefly summarises which sections are missing or incomplete
- asks the user to provide the missing information in plain text
- explicitly lists what you want them to write as bullet points.
Do not invent any data.
"""

# ВАЖНО: теперь просим модель выдавать строго Markdown
resume_generate_system_prompt = """
You are a professional CV writer.

Your task:
- Use only the information from the original CV text and the additional info provided by the user.
- Do not invent or hallucinate any data.
- If a typical section has no data, omit that section completely.

Output format:
- Output the FINAL CV **strictly in Markdown**, without any explanations and without backticks.
- First line should be "# Full Name" (or best guess of the candidate name from the data).
- Use section headings with "##", e.g.:
  ## PERSONAL INFORMATION
  ## EDUCATION AND TRAINING
  ## LANGUAGE SKILLS
  ## SKILLS
  ## WORK EXPERIENCE
  ## PROJECTS
  ## CERTIFICATIONS
  ## OTHER

- Use bullet lists with "- " for items.
- For language skills, use a Markdown table. Example:

  ## LANGUAGE SKILLS

  | Language  | Listening | Reading | Spoken production | Spoken interaction | Writing |
  |----------|-----------|---------|-------------------|--------------------|---------|
  | English  | B2        | B2      | B2                | B2                 | B1      |
  | Slovak   | B2        | B2      | B2                | B2                 | B2      |

- For work experience, use bullets with clear dates, position, company and responsibilities.

Your goal:
- Produce a clean, well-structured, modern CV layout in Markdown that can be converted to a PDF.
- Output ONLY the Markdown CV content, nothing else.
"""


# ---------- OPENAI CALLS ----------

def analyze_cv_text(cv_text: str) -> str:
    user_prompt = (
        "Here is the CV text:\n\n"
        f"{cv_text}\n\n"
        "Analyze this CV according to the system instructions."
    )
    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": neurohr_system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return response.choices[0].message.content


def get_missing_info_prompt(cv_text: str, language: str) -> str:
    lang = language or "English"
    user_prompt = (
        f"The user prefers to communicate in: {lang}.\n\n"
        "Here is the CV text:\n\n"
        f"{cv_text}\n\n"
        "Identify missing or weak sections and ask the user to provide the missing information. "
        "Write the whole answer in the preferred language."
    )
    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": resume_missing_system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return response.choices[0].message.content


# ---------- PDF GENERATION (КРАСИВАЯ ВЁРСТКА) ----------

def build_pdf_from_text(markdown_text: str) -> io.BytesIO:
    """
    Принимает структурированный Markdown и верстает красивый PDF:
    - #   -> большой заголовок (имя)
    - ##  -> заголовок секции
    - -   -> буллет-список
    - таблицы вида | a | b | c | -> превращаются в таблицу reportlab
    """

    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_LEFT, TA_CENTER
    from reportlab.lib import colors

    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=40,
        rightMargin=40,
        topMargin=40,
        bottomMargin=40,
    )

    styles = getSampleStyleSheet()

    # Базовые стили
    title_style = ParagraphStyle(
        "CVTitle",
        parent=styles["Title"],
        fontSize=20,
        leading=24,
        alignment=TA_LEFT,
        spaceAfter=12,
    )

    h2_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontSize=13,
        leading=16,
        spaceBefore=12,
        spaceAfter=6,
        textTransform="uppercase",
    )

    normal_style = ParagraphStyle(
        "NormalText",
        parent=styles["Normal"],
        fontSize=10,
        leading=13,
        spaceAfter=2,
    )

    bullet_style = ParagraphStyle(
        "BulletText",
        parent=styles["Normal"],
        fontSize=10,
        leading=13,
        leftIndent=12,
        bulletIndent=0,
        spaceAfter=1,
    )

    story = []
    lines = markdown_text.splitlines()

    current_table = []
    inside_table = False

    def flush_table():
        nonlocal current_table, story
        if not current_table:
            return
        table = Table(current_table, hAlign="LEFT")
        style_cmds = [
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]
        # шапка серым фоном
        if len(current_table) > 1:
            style_cmds.append(("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey))
            style_cmds.append(("TEXTCOLOR", (0, 0), (-1, 0), colors.black))
        table.setStyle(TableStyle(style_cmds))
        story.append(table)
        story.append(Spacer(1, 6))
        current_table = []

    for raw_line in lines:
        line = raw_line.rstrip("\n")

        # Таблицы Markdown: строки вида "| A | B | C |"
        if line.strip().startswith("|") and line.strip().endswith("|"):
            inside_table = True
            row = [cell.strip() for cell in line.strip().strip("|").split("|")]
            current_table.append(row)
            continue
        else:
            if inside_table:
                flush_table()
                inside_table = False

        stripped = line.strip()

        # Пустая строка -> вертикальный отступ
        if stripped == "":
            story.append(Spacer(1, 6))
            continue

        if stripped.startswith("# "):
            # Главный заголовок (имя)
            text = stripped[2:].strip()
            story.append(Paragraph(text, title_style))
            story.append(Spacer(1, 6))
        elif stripped.startswith("## "):
            # Заголовок секции
            text = stripped[3:].strip()
            story.append(Paragraph(text, h2_style))
        elif stripped.startswith("- "):
            # Буллет
            text = stripped[2:].strip()
            story.append(Paragraph(text, bullet_style, bulletText="•"))
        else:
            # Обычный абзац
            story.append(Paragraph(stripped, normal_style))

    # Если текст закончился в середине таблицы – не забываем её вывести
    if inside_table:
        flush_table()

    doc.build(story)
    buffer.seek(0)
    return buffer


def generate_resume_pdf(cv_text: str, extra_info: str, cv_format: str, language: str) -> io.BytesIO:
    fmt = (cv_format or "").strip().lower() or "europass"
    lang = language or "English"
    extra = extra_info.strip() if extra_info else ""
    user_prompt = (
        f"Target CV format (style): {fmt}.\n"
        f"Target language: {lang}.\n\n"
        "Original CV text:\n"
        f"{cv_text}\n\n"
        "Additional information from the user that should be added:\n"
        f"{extra if extra else '(no additional info provided)'}\n\n"
        "Generate the final CV in STRICT MARKDOWN according to the system instructions."
    )
    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": resume_generate_system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    resume_markdown = response.choices[0].message.content
    return build_pdf_from_text(resume_markdown)
