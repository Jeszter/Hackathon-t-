from dotenv import load_dotenv
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import PyPDF2
from pydantic import BaseModel
from back.system_prompts import docs_system_prompt
import openai
import os

load_dotenv()

router = APIRouter()

# Set OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")

class RequestValue(BaseModel):
    message: str

def read_pdf(file_path):
    """Read and extract text from a PDF file."""
    text = ""
    try:
        with open(file_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text += page.extract_text() + "\n"
    except Exception as e:
        return f"Error reading PDF: {str(e)}"
    return text

async def chat_with_gpt(user_message: str, system_prompt: str):
    """
    Send a message to GPT-4 and get a response.
    
    :param user_message: The user's message
    :param system_prompt: System instructions for the AI
    :return: AI response text
    """
    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            temperature=0.7,
            max_tokens=2000
        )
        return response.choices[0].message.content
    except Exception as e:
        raise Exception(f"OpenAI API error: {str(e)}")

@router.post("/chat")
async def docs_chat(request_data: RequestValue):
    """
    Request body should be JSON like:
    {
        "message": "user text"
    }
    """
    message = request_data.message.strip()
    if not message:
        return JSONResponse({"status": "error", "message": "Message is empty."}, status_code=400)

    try:
        # Check if message contains a request to read a PDF
        # You can enhance this logic to detect file paths or document references
        enhanced_prompt = f"""
{docs_system_prompt}

User request: {message}

If the user is asking about a specific document, you can use the document content provided.
Provide helpful and accurate information based on the request.
"""

        reply = await chat_with_gpt(message, enhanced_prompt)
        return JSONResponse({"status": "success", "reply": reply})
    except Exception as e:
        return JSONResponse(
            {"status": "error", "message": f"Documents chat error: {str(e)}"},
            status_code=500
        )

@router.post("/chat-with-pdf")
async def docs_chat_with_pdf(request_data: dict):
    """
    Request body should be JSON like:
    {
        "message": "user text",
        "pdf_path": "path/to/document.pdf"
    }
    """
    message = request_data.get("message", "").strip()
    pdf_path = request_data.get("pdf_path", "")

    if not message:
        return JSONResponse({"status": "error", "message": "Message is empty."}, status_code=400)

    try:
        # Read PDF content if path is provided
        pdf_content = ""
        if pdf_path:
            pdf_content = read_pdf(pdf_path)
            if pdf_content.startswith("Error reading PDF"):
                return JSONResponse(
                    {"status": "error", "message": pdf_content},
                    status_code=400
                )

        # Combine document content with user message
        enhanced_message = f"""
Document Content:
{pdf_content}

User Question: {message}
"""

        reply = await chat_with_gpt(enhanced_message, docs_system_prompt)
        return JSONResponse({"status": "success", "reply": reply})
    except Exception as e:
        return JSONResponse(
            {"status": "error", "message": f"Documents chat error: {str(e)}"},
            status_code=500
        )