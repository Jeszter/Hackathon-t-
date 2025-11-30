import os
import json
import base64
import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

router = APIRouter(prefix="/api", tags=["banking"])
logger = logging.getLogger("fill_form")
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] [fill_form] %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

api_key_present = bool(os.getenv("OPENAI_API_KEY"))
if not api_key_present:
    logger.error("OPENAI_API_KEY is not set in environment")
else:
    logger.info("OPENAI_API_KEY detected in environment")


class FillFormResponse(BaseModel):
    filled_text: str
    missing_fields: List[str] = []
    notes: Optional[str] = None


def _truncate_for_log(text: str, length: int = 400) -> str:
    if text is None:
        return ""
    text = str(text).replace("\n", " ")
    if len(text) <= length:
        return text
    return text[: length - 3] + "..."


def ask_ai_to_fill_form(
    template_text: Optional[str],
    user_document_text: Optional[str],
    template_image_b64: Optional[str],
    user_image_b64: Optional[str],
    template_mime: Optional[str],
    user_mime: Optional[str],
    language: str,
) -> FillFormResponse:
    use_images = bool(template_image_b64 or user_image_b64)

    logger.info(
        "ask_ai_to_fill_form called. use_images=%s template_text_len=%s user_text_len=%s",
        use_images,
        len(template_text) if template_text else 0,
        len(user_document_text) if user_document_text else 0,
    )
    logger.info("Template text preview: %s", _truncate_for_log(template_text))
    logger.info("User document text preview: %s", _truncate_for_log(user_document_text))
    if template_image_b64:
        logger.info(
            "Template image present. mime=%s base64_len=%s",
            template_mime,
            len(template_image_b64),
        )
    if user_image_b64:
        logger.info(
            "User document image present. mime=%s base64_len=%s",
            user_mime,
            len(user_image_b64),
        )

    system_prompt = (
        "You are an assistant that fills out official forms for a user based on their personal document. "
        "You may receive the blank form and user document as text, as images, or a mix of both. "
        "If images are provided, you must visually read them and extract all relevant data. "
        "Your task:\n"
        "- Read the user document (text and/or image) and extract all relevant personal data.\n"
        "- Fill the blank form template with this data, preserving the original structure of the template as much as possible.\n"
        "- Do not invent data that is not present in the user document.\n"
        "- If some fields in the template cannot be filled from the user document, keep them blank, with placeholders like '____' or existing empty lines.\n"
        "- Do not remove any fields from the template.\n"
        "- Keep the language of the template itself (do not translate field names)."
    )

    json_spec_text = (
        "Return a single JSON object with this structure:\n"
        "{\n"
        '  "filled_text": string,\n'
        '  "missing_fields": [string, ...],\n'
        '  "notes": string\n'
        "}\n\n"
        "Where:\n"
        "- filled_text is the template form fully filled with user data where possible.\n"
        "- missing_fields is a list of human-readable field names or labels that could not be filled from the user document.\n"
        "- notes is a short explanation for the user about any uncertainties or assumptions.\n\n"
        f"User interface language for notes and missing_fields: {language}.\n"
        "Use this language for notes and missing_fields descriptions, but keep template labels in their original language.\n\n"
    )

    if not use_images:
        logger.info("ask_ai_to_fill_form using text-only mode")
        user_prompt = (
            json_spec_text
            + "BLANK FORM TEMPLATE:\n"
            "--------------------\n"
            f"{template_text or ''}\n\n"
            "USER DOCUMENT:\n"
            "--------------\n"
            f"{user_document_text or ''}\n\n"
            "Now output only the JSON object."
        )
        try:
            resp = client.chat.completions.create(
                model="gpt-4.1-mini",
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,
            )
        except Exception as e:
            logger.exception("AI request failed in text-only mode")
            raise HTTPException(status_code=500, detail=f"AI request failed: {e}")

    else:
        logger.info("ask_ai_to_fill_form using multimodal (image+text) mode")
        user_content = []

        user_content.append({"type": "text", "text": json_spec_text})

        if template_image_b64:
            mime = template_mime or "image/png"
            logger.info("Adding template image to prompt. mime=%s", mime)
            user_content.append(
                {
                    "type": "text",
                    "text": "BLANK FORM TEMPLATE (image below). Visually read this form:",
                }
            )
            user_content.append(
                {
                    "type": "input_image",
                    "image_url": {
                        "url": f"data:{mime};base64,{template_image_b64}",
                    },
                }
            )
        elif template_text:
            logger.info("Template provided as text only in multimodal mode")
            user_content.append(
                {
                    "type": "text",
                    "text": "BLANK FORM TEMPLATE (text):\n--------------------\n" + template_text,
                }
            )
        else:
            logger.warning("No template_text or template_image_b64 provided")

        if user_image_b64:
            mime = user_mime or "image/png"
            logger.info("Adding user document image to prompt. mime=%s", mime)
            user_content.append(
                {
                    "type": "text",
                    "text": "\nUSER DOCUMENT (image below). Extract all personal data from it:",
                }
            )
            user_content.append(
                {
                    "type": "input_image",
                    "image_url": {
                        "url": f"data:{mime};base64,{user_image_b64}",
                    },
                }
            )
        elif user_document_text:
            logger.info("User document provided as text only in multimodal mode")
            user_content.append(
                {
                    "type": "text",
                    "text": "\nUSER DOCUMENT (text):\n--------------\n" + user_document_text,
                }
            )
        else:
            logger.warning("No user_document_text or user_image_b64 provided")

        user_content.append(
            {
                "type": "text",
                "text": "\nNow output only the JSON object.",
            }
        )

        try:
            resp = client.chat.completions.create(
                model="gpt-4.1-mini",
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.1,
            )
        except Exception as e:
            logger.exception("AI request failed in multimodal mode")
            raise HTTPException(status_code=500, detail=f"AI request failed: {e}")

    logger.info("AI request succeeded, processing response")
    content = resp.choices[0].message.content
    logger.info("Raw AI response (truncated): %s", _truncate_for_log(content, 600))

    try:
        data = json.loads(content)
    except Exception as e:
        logger.exception("Failed to parse AI JSON")
        raise HTTPException(status_code=500, detail=f"AI returned invalid JSON: {e}")

    filled_text = str(data.get("filled_text") or "").strip()
    if not filled_text:
        logger.error("AI did not return filled_text field or it is empty")
        raise HTTPException(status_code=500, detail="AI did not return filled form")

    missing_raw = data.get("missing_fields") or []
    if not isinstance(missing_raw, list):
        logger.warning("missing_fields is not a list, value_type=%s", type(missing_raw))
        missing_raw = []

    missing_fields: List[str] = []
    for item in missing_raw:
        if not item:
            continue
        missing_fields.append(str(item).strip())

    notes = data.get("notes")
    if notes is not None:
        notes = str(notes).strip()

    logger.info(
        "Filled form generated. filled_len=%s missing_count=%s notes_len=%s",
        len(filled_text),
        len(missing_fields),
        len(notes) if notes else 0,
    )

    return FillFormResponse(
        filled_text=filled_text,
        missing_fields=missing_fields,
        notes=notes,
    )


@router.post("/fill_form", response_model=FillFormResponse)
async def fill_form(
    template_file: UploadFile = File(...),
    user_document_file: UploadFile = File(...),
    language: str = Form("en"),
) -> FillFormResponse:
    logger.info(
        "/api/fill_form called. template_filename=%s user_filename=%s language=%s",
        template_file.filename,
        user_document_file.filename,
        language,
    )

    template_content_type = template_file.content_type or "application/octet-stream"
    user_content_type = user_document_file.content_type or "application/octet-stream"
    logger.info(
        "Incoming files content types: template_content_type=%s user_content_type=%s",
        template_content_type,
        user_content_type,
    )

    template_bytes = await template_file.read()
    user_bytes = await user_document_file.read()

    logger.info(
        "Read files from request. template_size=%s user_size=%s",
        len(template_bytes) if template_bytes else 0,
        len(user_bytes) if user_bytes else 0,
    )

    if not template_bytes:
        logger.warning("template_file is empty")
        raise HTTPException(status_code=400, detail="template_file is required and must not be empty")
    if not user_bytes:
        logger.warning("user_document_file is empty")
        raise HTTPException(status_code=400, detail="user_document_file is required and must not be empty")

    template_is_image = template_content_type.startswith("image/")
    user_is_image = user_content_type.startswith("image/")

    logger.info(
        "Detection: template_is_image=%s user_is_image=%s",
        template_is_image,
        user_is_image,
    )

    template_text: Optional[str] = None
    user_document_text: Optional[str] = None
    template_image_b64: Optional[str] = None
    user_image_b64: Optional[str] = None

    if template_is_image:
        template_image_b64 = base64.b64encode(template_bytes).decode("utf-8")
        logger.info(
            "Template treated as image. mime=%s base64_len=%s",
            template_content_type,
            len(template_image_b64),
        )
    else:
        try:
            template_text = template_bytes.decode("utf-8", errors="ignore").strip()
        except Exception as e:
            logger.exception("Failed to decode template_file as UTF-8")
            raise HTTPException(status_code=400, detail=f"Could not decode template file: {e}")
        logger.info("Template decoded as text. text_len=%s preview=%s", len(template_text), _truncate_for_log(template_text))

    if user_is_image:
        user_image_b64 = base64.b64encode(user_bytes).decode("utf-8")
        logger.info(
            "User document treated as image. mime=%s base64_len=%s",
            user_content_type,
            len(user_image_b64),
        )
    else:
        try:
            user_document_text = user_bytes.decode("utf-8", errors="ignore").strip()
        except Exception as e:
            logger.exception("Failed to decode user_document_file as UTF-8")
            raise HTTPException(status_code=400, detail=f"Could not decode user document file: {e}")
        logger.info(
            "User document decoded as text. text_len=%s preview=%s",
            len(user_document_text),
            _truncate_for_log(user_document_text),
        )

    if not template_is_image and (not template_text or not template_text.strip()):
        logger.warning("Template text is empty after decoding and it is not an image")
        raise HTTPException(status_code=400, detail="Could not read text from template file")

    if not user_is_image and (not user_document_text or not user_document_text.strip()):
        logger.warning("User document text is empty after decoding and it is not an image")
        raise HTTPException(status_code=400, detail="Could not read text from user document file")

    lang = language or "en"
    logger.info("Resolved language parameter: %s", lang)

    try:
        result = ask_ai_to_fill_form(
            template_text=template_text,
            user_document_text=user_document_text,
            template_image_b64=template_image_b64,
            user_image_b64=user_image_b64,
            template_mime=template_content_type if template_is_image else None,
            user_mime=user_content_type if user_is_image else None,
            language=lang,
        )
    except HTTPException as e:
        logger.error("fill_form aborted with HTTPException: status=%s detail=%s", e.status_code, e.detail)
        raise
    except Exception as e:
        logger.exception("Unexpected error in fill_form")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")

    logger.info("fill_form completed successfully, returning response to client")
    return result
