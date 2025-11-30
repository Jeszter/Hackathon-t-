import os
import re
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from openai import OpenAI
from pydantic import BaseModel

load_dotenv()

router = APIRouter()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


class ChatRequest(BaseModel):
    message: str
    chat_history: list = []
    ui_language: str = "en"


urbanmind_system_prompt = """
You are an AI assistant for the UrbanMind platform that helps migrants adapt to a new country.

Main functions:
1) Help users navigate the UrbanMind website.
2) Direct users to relevant sections.
3) Answer questions about what the platform can do for them.

Website sections and paths:
- Improve or check CV: <a href="/neurohr">NeuroHR – CV assistant</a> (/neurohr)
- Find jobs: <a href="/jobs">Job search</a> (/jobs)
- Language learning: <a href="/language">Language learning</a> (/language)
- Official forms and office search: <a href="/official">Official help</a> (/official)
- Translation services: <a href="/translation">Translation</a> (/translation)
- Cultural attractions: <a href="/cultural">Cultural guide</a> (/cultural)

Formatting rules:
- Always answer in the same language as the latest user message. Detect the language from the text, but never mention that you are detecting it.
- When you recommend a section, include an HTML link using the patterns above, for example: <a href="/language">Language learning</a>.
- Keep answers short, friendly and practical.
- Use 1–3 short paragraphs.
- At the end of every answer, add one short sentence offering further help, in the same language as the user.

Do not output markdown links like [text](/path). Use HTML links <a href="/path">text</a> instead.
"""


def convert_markdown_links_to_html(text: str) -> str:
    pattern = re.compile(r"\[([^\]]+)\]\((\/[^\)]+)\)")
    return pattern.sub(r'<a href="\2">\1</a>', text)


@router.post("/chat")
async def urbanmind_chat(payload: ChatRequest):
    try:
        messages = [
            {"role": "system", "content": urbanmind_system_prompt}
        ]

        for msg in payload.chat_history:
            messages.append({"role": msg["role"], "content": msg["content"]})

        messages.append({"role": "user", "content": payload.message})

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.6,
            max_tokens=400
        )

        reply = response.choices[0].message.content
        reply = convert_markdown_links_to_html(reply)

        quick_actions = generate_quick_actions(payload.message)

        return {
            "status": "success",
            "data": {
                "assistant_message": reply,
                "quick_actions": quick_actions
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat error: {str(e)}")


def generate_quick_actions(user_message: str):
    message_lower = user_message.lower()

    base_actions = [
        {"action": "documents", "label": "Help with documents", "section": "/official"},
        {"action": "housing", "label": "Find housing", "section": "/housing"},
        {"action": "language", "label": "Language learning", "section": "/language"},
        {"action": "community", "label": "Community events", "section": "/cultural"}
    ]

    if any(word in message_lower for word in ["cv", "resume", "curriculum"]):
        return [
            {"action": "cv_help", "label": "Improve my CV", "section": "/neurohr"},
            {"action": "find_jobs", "label": "Find jobs", "section": "/jobs"},
            {"action": "documents", "label": "Help with documents", "section": "/official"},
            {"action": "language", "label": "Language learning", "section": "/language"}
        ]
    elif any(word in message_lower for word in ["job", "work", "employment"]):
        return [
            {"action": "find_jobs", "label": "Find jobs", "section": "/jobs"},
            {"action": "cv_help", "label": "Improve my CV", "section": "/neurohr"},
            {"action": "language", "label": "Language learning", "section": "/language"},
            {"action": "documents", "label": "Help with documents", "section": "/official"}
        ]
    elif any(word in message_lower for word in ["language", "learn", "speak", "english"]):
        return [
            {"action": "language", "label": "Language learning", "section": "/language"},
            {"action": "translation", "label": "Translation help", "section": "/translation"},
            {"action": "community", "label": "Community events", "section": "/cultural"},
            {"action": "documents", "label": "Help with documents", "section": "/official"}
        ]

    return base_actions
