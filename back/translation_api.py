import os
import io
from dotenv import load_dotenv
from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
from openai import OpenAI

load_dotenv()

router = APIRouter()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


class TranslationRequest(BaseModel):
    text: str
    source_language: Optional[str] = "auto"
    target_language: str


translation_system_prompt = """
You are an intelligent multilingual translation assistant.

Your responsibilities:
- Translate text naturally and fluently.
- Preserve meaning, tone and context.
- If source_language = 'auto', first detect the language of the text.
- Support any Unicode text (Cyrillic, Arabic, Asian scripts, accents, emojis).
- Always answer ONLY with the final translation.
- Do not add explanations, comments or quotes around the translation.
"""


@router.post("/translation")
async def translation_endpoint(payload: TranslationRequest):
    text = (payload.text or "").strip()
    target = (payload.target_language or "").strip()
    source = (payload.source_language or "auto").strip()

    if not text:
        return JSONResponse({"status": "error", "message": "Empty text."}, status_code=400)
    if not target:
        return JSONResponse({"status": "error", "message": "Target language is required."}, status_code=400)

    try:
        user_prompt = (
            f"Source language: {source}\n"
            f"Target language: {target}\n\n"
            f"Text:\n{text}\n\n"
            "Return only the translation."
        )

        resp = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": translation_system_prompt.strip()},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
        )

        translated = resp.choices[0].message.content.strip()

        return JSONResponse(
            {
                "status": "success",
                "translated_text": translated,
            }
        )
    except Exception as e:
        return JSONResponse(
            {
                "status": "error",
                "message": f"Translation error: {str(e)}",
            },
            status_code=500,
        )


@router.post("/translation/voice")
async def translation_voice_endpoint(
    audio: UploadFile = File(...),
    source_language: str = Form("auto"),
    target_language: str = Form(...)
):
    target = (target_language or "").strip()
    source = (source_language or "auto").strip()

    if not target:
        return JSONResponse({"status": "error", "message": "Target language is required."}, status_code=400)

    try:
        raw = await audio.read()
        if not raw:
            return JSONResponse({"status": "error", "message": "Empty audio file."}, status_code=400)

        audio_file = ("audio.webm", io.BytesIO(raw), audio.content_type or "audio/webm")

        transcription = client.audio.transcriptions.create(
            model="gpt-4o-mini-transcribe",
            file=audio_file,
            response_format="text"
        )

        transcribed_text = getattr(transcription, "text", str(transcription)).strip()

        if not transcribed_text:
            return JSONResponse(
                {"status": "error", "message": "Could not transcribe audio."},
                status_code=500,
            )

        user_prompt = (
            f"Source language: {source}\n"
            f"Target language: {target}\n\n"
            f"Text:\n{transcribed_text}\n\n"
            "Return only the translation."
        )

        resp = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": translation_system_prompt.strip()},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
        )

        translated = resp.choices[0].message.content.strip()

        return JSONResponse(
            {
                "status": "success",
                "transcribed_text": transcribed_text,
                "translated_text": translated,
            }
        )

    except Exception as e:
        return JSONResponse(
            {
                "status": "error",
                "message": f"Voice translation error: {str(e)}",
            },
            status_code=500,
        )
