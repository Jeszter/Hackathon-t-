import os
from typing import Optional
from dotenv import load_dotenv
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from openai import OpenAI

load_dotenv()

router = APIRouter()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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


def extract_text_from_file(filename: str, data: bytes) -> str:
    name_lower = filename.lower()

    if name_lower.endswith(".txt"):
        return data.decode("utf-8", errors="ignore")

    if name_lower.endswith(".pdf"):
        from PyPDF2 import PdfReader
        import io
        reader = PdfReader(io.BytesIO(data))
        text = "\n".join(page.extract_text() or "" for page in reader.pages).strip()
        if not text:
            raise HTTPException(status_code=400, detail="Cannot extract text from PDF.")
        return text

    if name_lower.endswith(".docx"):
        import docx
        import io
        doc = docx.Document(io.BytesIO(data))
        text = "\n".join(p.text for p in doc.paragraphs)
        if not text.strip():
            raise HTTPException(status_code=400, detail="Cannot extract text from DOCX.")
        return text

    raise HTTPException(status_code=400, detail="Unsupported file type. Use PDF, DOCX, TXT.")


@router.post("/analyze")
async def analyze_cv(file: UploadFile = File(...)):
    filename = file.filename or "uploaded_file"
    ext = os.path.splitext(filename)[1].lower()

    if ext not in {".pdf", ".docx", ".txt"}:
        raise HTTPException(status_code=400, detail="Unsupported file type. Allowed: PDF, DOCX, TXT.")

    data = await file.read()
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File is too large. Max size is 5 MB.")

    cv_text = extract_text_from_file(filename, data)

    if not cv_text or len(cv_text.strip()) < 100:
        raise HTTPException(status_code=400, detail="CV text too short or empty.")

    user_prompt = (
        "Here is the CV text:\n\n"
        f"{cv_text}\n\n"
        "Analyze this CV according to the system instructions."
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": neurohr_system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )

        analysis_text = response.choices[0].message.content

        return JSONResponse(
            {
                "status": "success",
                "filename": filename,
                "analysis": analysis_text,
            }
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"NeuroHR analysis error: {str(e)}",
        )
