import os
import json
import base64
import logging
import io
from typing import List, Optional, Tuple

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import Response
from pydantic import BaseModel
from dotenv import load_dotenv
from openai import OpenAI
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import PyPDF2

# Try to import PyMuPDF for PDF to image conversion
try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False
    # Logger will be initialized later, so we'll log this after logger setup

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

# Log PyMuPDF availability after logger is initialized
if not HAS_PYMUPDF:
    logger.warning("PyMuPDF (fitz) not available. PDF to image conversion will not work. Install with: pip install PyMuPDF")

api_key_present = bool(os.getenv("OPENAI_API_KEY"))
if not api_key_present:
    logger.error("OPENAI_API_KEY is not set in environment")
else:
    logger.info("OPENAI_API_KEY detected in environment")


class FillFormResponse(BaseModel):
    filled_text: str
    missing_fields: List[str] = []
    notes: Optional[str] = None


def create_pdf_from_text(text: str, original_filename: str = "form.pdf") -> io.BytesIO:
    """Create a PDF file from filled form text."""
    buffer = io.BytesIO()
    
    fonts_dir = os.path.join(os.path.dirname(__file__), "fonts")
    regular_path = os.path.join(fonts_dir, "NotoSans-Regular.ttf")
    bold_path = os.path.join(fonts_dir, "NotoSans-Bold.ttf")
    
    # Register fonts if not already registered
    registered = pdfmetrics.getRegisteredFontNames()
    if "NotoSans" not in registered and os.path.exists(regular_path):
        pdfmetrics.registerFont(TTFont("NotoSans", regular_path))
    if "NotoSans-Bold" not in registered and os.path.exists(bold_path):
        pdfmetrics.registerFont(TTFont("NotoSans-Bold", bold_path))
    
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=40,
        rightMargin=40,
        topMargin=40,
        bottomMargin=40,
    )
    
    styles = getSampleStyleSheet()
    
    # Use registered font if available, otherwise use default
    font_name = "NotoSans" if "NotoSans" in pdfmetrics.getRegisteredFontNames() else "Helvetica"
    bold_font_name = "NotoSans-Bold" if "NotoSans-Bold" in pdfmetrics.getRegisteredFontNames() else "Helvetica-Bold"
    
    normal_style = ParagraphStyle(
        "NormalText",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=11,
        leading=14,
        spaceAfter=6,
        alignment=TA_LEFT,
    )
    
    story = []
    
    # Split text into lines and create paragraphs
    lines = text.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            story.append(Spacer(1, 6))
        else:
            # Preserve formatting - check for bold markers or special formatting
            if line.startswith('# '):
                # Heading
                heading_style = ParagraphStyle(
                    "Heading",
                    parent=normal_style,
                    fontName=bold_font_name,
                    fontSize=14,
                    spaceAfter=8,
                    spaceBefore=12,
                )
                story.append(Paragraph(line[2:].strip(), heading_style))
            elif line.startswith('## '):
                # Subheading
                subheading_style = ParagraphStyle(
                    "Subheading",
                    parent=normal_style,
                    fontName=bold_font_name,
                    fontSize=12,
                    spaceAfter=6,
                    spaceBefore=8,
                )
                story.append(Paragraph(line[3:].strip(), subheading_style))
            else:
                story.append(Paragraph(line, normal_style))
    
    doc.build(story)
    buffer.seek(0)
    return buffer


def _truncate_for_log(text: str, length: int = 400) -> str:
    if text is None:
        return ""
    text = str(text).replace("\n", " ")
    if len(text) <= length:
        return text
    return text[: length - 3] + "..."


def _pdf_to_image(pdf_bytes: bytes) -> Tuple[bytes, str]:
    """Convert first page of PDF to PNG image."""
    if not HAS_PYMUPDF:
        raise HTTPException(
            status_code=500,
            detail="PDF to image conversion requires PyMuPDF library. Please install it: pip install PyMuPDF"
        )
    
    try:
        # Open PDF from bytes
        pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        if len(pdf_document) == 0:
            raise ValueError("PDF has no pages")
        
        # Get first page
        page = pdf_document[0]
        
        # Render page to image (PNG) with high DPI for better quality
        mat = fitz.Matrix(2.0, 2.0)  # 2x zoom for better quality
        pix = page.get_pixmap(matrix=mat)
        
        # Convert to PNG bytes
        img_bytes = pix.tobytes("png")
        
        pdf_document.close()
        
        logger.info(f"Converted PDF page to image. Image size: {len(img_bytes)} bytes")
        return img_bytes, "image/png"
        
    except Exception as e:
        logger.exception("Failed to convert PDF to image")
        raise HTTPException(
            status_code=400,
            detail=f"Failed to convert PDF to image: {str(e)}"
        )


def _normalize_image_mime(mime: Optional[str]) -> str:
    """Normalize image MIME type for OpenAI Vision API compatibility."""
    if not mime:
        return "image/png"
    
    mime_lower = mime.lower().strip()
    
    # OpenAI Vision API does NOT support PDF - reject it
    if mime_lower == "application/pdf" or mime_lower.endswith("/pdf"):
        raise ValueError("PDF files cannot be sent as images to OpenAI Vision API. Please extract text from PDF first.")
    
    # Map common image MIME types to OpenAI supported formats
    mime_map = {
        "image/jpg": "image/jpeg",
        "image/jpeg": "image/jpeg",
        "image/png": "image/png",
        "image/gif": "image/gif",
        "image/webp": "image/webp",
    }
    
    # Check if it's a known format
    if mime_lower in mime_map:
        return mime_map[mime_lower]
    
    # Check if it starts with image/ and try to extract format
    if mime_lower.startswith("image/"):
        format_part = mime_lower.split("/")[-1].split(";")[0]  # Remove parameters like ;charset=utf-8
        if format_part in ["jpg", "jpeg"]:
            return "image/jpeg"
        elif format_part in ["png", "gif", "webp"]:
            return f"image/{format_part}"
    
    # Default to PNG if unknown
    logger.warning(f"Unknown image MIME type: {mime}, defaulting to image/png")
    return "image/png"


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
        "You are an expert assistant that fills out official forms for users based on their personal documents (passports, IDs, etc.). "
        "You may receive the blank form and user document as text, as images, or a mix of both. "
        "If images are provided, you must carefully and accurately read them using OCR and extract ALL relevant personal data including: "
        "full name, date of birth, place of birth, nationality, passport/ID number, address, phone number, email, and any other information present. "
        "Your task:\n"
        "- Carefully read the user document (text and/or image) and extract ALL available personal data with high accuracy.\n"
        "- Match the extracted data to the corresponding fields in the blank form template.\n"
        "- Fill the blank form template with this data, preserving the original structure, formatting, and field names of the template exactly.\n"
        "- Fill ALL fields that can be matched from the user document - be thorough and complete.\n"
        "- Do not invent or guess data that is not clearly visible in the user document.\n"
        "- If some fields in the template cannot be filled from the user document, leave them blank or use placeholders like '____' or existing empty lines.\n"
        "- Do not remove, modify, or translate any field names or labels from the template.\n"
        "- Keep the language of the template itself unchanged (do not translate field names or labels)."
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
                model="gpt-4o-mini",
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
            try:
                mime = _normalize_image_mime(template_mime)
                logger.info("Adding template image to prompt. original_mime=%s normalized_mime=%s", template_mime, mime)
            except ValueError as e:
                logger.error("Invalid MIME type for template image: %s", e)
                raise HTTPException(status_code=400, detail=str(e))
            user_content.append(
                {
                    "type": "text",
                    "text": "BLANK FORM TEMPLATE (image below). Carefully read and identify all fields in this form:",
                }
            )
            user_content.append(
                {
                    "type": "image_url",
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
            try:
                mime = _normalize_image_mime(user_mime)
                logger.info("Adding user document image to prompt. original_mime=%s normalized_mime=%s", user_mime, mime)
            except ValueError as e:
                logger.error("Invalid MIME type for user document image: %s", e)
                raise HTTPException(status_code=400, detail=str(e))
            user_content.append(
                {
                    "type": "text",
                    "text": "\nUSER DOCUMENT (passport/ID image below). Carefully extract ALL personal data from this document including: full name, date of birth, place of birth, nationality, document number, address, and any other visible information:",
                }
            )
            user_content.append(
                {
                    "type": "image_url",
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
                model="gpt-4o-mini",
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


@router.post("/fill_form")
async def fill_form(
    template_file: UploadFile = File(...),
    user_document_file: UploadFile = File(...),
    language: str = Form("en"),
):
    logger.info(
        "/api/fill_form called. template_filename=%s user_filename=%s language=%s",
        template_file.filename,
        user_document_file.filename,
        language,
    )

    template_content_type = template_file.content_type or "application/octet-stream"
    user_content_type = user_document_file.content_type or "application/octet-stream"
    template_filename = template_file.filename or "form.pdf"
    logger.info(
        "Incoming files content types: template_content_type=%s user_content_type=%s",
        template_content_type,
        user_content_type,
    )

    template_bytes = await template_file.read()
    user_bytes = await user_document_file.read()
    
    # Check if template is PDF
    template_is_pdf = template_content_type == "application/pdf" or template_filename.lower().endswith(".pdf")

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

    template_is_image = template_content_type.startswith("image/") and not template_is_pdf
    user_is_image = user_content_type.startswith("image/")

    logger.info(
        "Detection: template_is_pdf=%s template_is_image=%s user_is_image=%s",
        template_is_pdf,
        template_is_image,
        user_is_image,
    )

    template_text: Optional[str] = None
    user_document_text: Optional[str] = None
    template_image_b64: Optional[str] = None
    user_image_b64: Optional[str] = None

    # Handle PDF template
    if template_is_pdf:
        try:
            # Try to extract text from PDF
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(template_bytes))
            template_text = ""
            for page in pdf_reader.pages:
                page_text = page.extract_text()
                if page_text:
                    template_text += page_text + "\n"
            template_text = template_text.strip()
            
            if not template_text:
                # If no text extracted, convert PDF to image
                logger.info("No text extracted from PDF, converting first page to image")
                try:
                    img_bytes, img_mime = _pdf_to_image(template_bytes)
                    template_image_b64 = base64.b64encode(img_bytes).decode("utf-8")
                    template_text = None
                    # Update content type to image for proper handling
                    template_content_type = img_mime
                    template_is_image = True
                    logger.info("PDF converted to image successfully. image_size=%s", len(img_bytes))
                except HTTPException:
                    raise
                except Exception as e:
                    logger.exception("Failed to convert PDF to image")
                    raise HTTPException(
                        status_code=400,
                        detail=f"PDF does not contain extractable text and could not be converted to image: {str(e)}. Please install PyMuPDF: pip install PyMuPDF"
                    )
            else:
                logger.info("Extracted text from PDF. text_len=%s", len(template_text))
        except HTTPException:
            raise
        except Exception as e:
            logger.exception("Failed to process PDF")
            # Try to convert to image as fallback
            logger.info("Attempting to convert PDF to image as fallback")
            try:
                img_bytes, img_mime = _pdf_to_image(template_bytes)
                template_image_b64 = base64.b64encode(img_bytes).decode("utf-8")
                template_text = None
                template_content_type = img_mime
                template_is_image = True
                logger.info("PDF converted to image as fallback. image_size=%s", len(img_bytes))
            except Exception as img_error:
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to process PDF file: {str(e)}. Also failed to convert to image: {str(img_error)}"
                )
    elif template_is_image:
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

    if not template_is_pdf and not template_is_image and (not template_text or not template_text.strip()):
        logger.warning("Template text is empty after decoding and it is not an image or PDF")
        raise HTTPException(status_code=400, detail="Could not read text from template file")

    if not user_is_image and (not user_document_text or not user_document_text.strip()):
        logger.warning("User document text is empty after decoding and it is not an image")
        raise HTTPException(status_code=400, detail="Could not read text from user document file")

    lang = language or "en"
    logger.info("Resolved language parameter: %s", lang)

    try:
        # Normalize MIME types for images
        normalized_template_mime = None
        normalized_user_mime = None
        
        if template_is_image:
            try:
                normalized_template_mime = _normalize_image_mime(template_content_type)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"Template file: {str(e)}")
        
        if user_is_image:
            try:
                normalized_user_mime = _normalize_image_mime(user_content_type)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"User document file: {str(e)}")
        
        result = ask_ai_to_fill_form(
            template_text=template_text,
            user_document_text=user_document_text,
            template_image_b64=template_image_b64,
            user_image_b64=user_image_b64,
            template_mime=normalized_template_mime,
            user_mime=normalized_user_mime,
            language=lang,
        )
    except HTTPException as e:
        logger.error("fill_form aborted with HTTPException: status=%s detail=%s", e.status_code, e.detail)
        raise
    except Exception as e:
        logger.exception("Unexpected error in fill_form")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")

    logger.info("fill_form completed successfully, creating PDF response")
    
    # Create PDF from filled text
    try:
        pdf_buffer = create_pdf_from_text(result.filled_text, template_filename)
        pdf_bytes = pdf_buffer.read()
        
        # Generate output filename
        output_filename = template_filename
        if not output_filename.lower().endswith('.pdf'):
            output_filename = output_filename.rsplit('.', 1)[0] + '_filled.pdf'
        else:
            output_filename = output_filename.rsplit('.', 1)[0] + '_filled.pdf'
        
        logger.info("PDF created successfully. size=%s filename=%s", len(pdf_bytes), output_filename)
        
        # Return PDF file
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{output_filename}"',
                "X-Missing-Fields": json.dumps(result.missing_fields),
                "X-Notes": result.notes or "",
            }
        )
    except Exception as e:
        logger.exception("Failed to create PDF")
        raise HTTPException(status_code=500, detail=f"Failed to create PDF: {e}")
