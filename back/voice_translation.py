import os
from fastapi import APIRouter, UploadFile, File
from fastapi.responses import JSONResponse
from openai import OpenAI

router = APIRouter()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


@router.post("/translation/voice")
async def voice_translation(
    audio: UploadFile = File(...),
    target_language: str = "en"
):
    try:
        # 1) SPEECH → TEXT (Whisper)
        transcript = client.audio.transcriptions.create(
            model="gpt-4o-mini-tts",
            file=audio.file,
            response_format="text"
        )

        recognized_text = transcript.strip()

        # 2) TEXT → TRANSLATION
        translation_chat = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": "Translate the user text fluently. Return only translation."},
                {"role": "user", "content": recognized_text}
            ]
        )

        translated_text = translation_chat.choices[0].message.content.strip()

        # 3) TRANSLATION → SPEECH (TTS)
        tts_response = client.audio.speech.create(
            model="gpt-4o-mini-tts",
            voice="alloy",
            input=translated_text
        )

        audio_bytes = tts_response.read()

        return JSONResponse({
            "status": "success",
            "recognized_text": recognized_text,
            "translated_text": translated_text,
            "tts_audio_base64": tts_response._content["audio_base64"]
        })

    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)
