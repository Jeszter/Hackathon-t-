import os
import json
import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

router = APIRouter()


class LocationRequest(BaseModel):
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    country_code: Optional[str] = None
    language: Optional[str] = None


def reverse_geocode(lat: float, lon: float) -> Dict[str, str]:
    try:
        url = (
            f"https://nominatim.openstreetmap.org/reverse?"
            f"lat={lat}&lon={lon}&format=json&addressdetails=1"
        )
        resp = requests.get(url, headers={"User-Agent": "UrbanMind/1.0"}, timeout=10)
        data = resp.json()
        addr = data.get("address", {})
        return {
            "country_code": addr.get("country_code", "").lower(),
            "country_name": addr.get("country", "") or "Unknown",
            "city": addr.get("city")
            or addr.get("town")
            or addr.get("village")
            or addr.get("state")
            or "",
        }
    except Exception:
        return {"country_code": "", "country_name": "Unknown", "city": ""}


def ask_ai_for_job_sites(location_text: str, ui_language: str) -> List[Dict[str, Any]]:
    system_prompt = """
You are an expert career advisor and job-market analyst.

Given the user's location, recommend the most relevant, popular and trustworthy ONLINE JOB SEARCH WEBSITES for that region.

Rules:
- Suggest 3–7 websites.
- Prefer local or region-specific sites; include global platforms (like LinkedIn, Indeed) only if they are actually widely used in that region.
- Include only job boards, career portals, or official employment services. No generic forums, Telegram channels, or unrelated sites.
- Be up to date and realistic, but do NOT invent obviously fake brands.
- Output MUST be valid JSON only, with no extra text.

Use this JSON schema:
[
  {
    "name": "string",
    "url": "string",
    "description": "short string (1–2 sentences)",
    "country_or_region": "string",
    "primary_language": "string"
  }
]
"""
    user_prompt = (
        f"User interface language: {ui_language}.\n"
        f"User location: {location_text}.\n\n"
        "Return ONLY a JSON array following the schema.\n"
        "Descriptions can be in English if you are unsure."
    )

    resp = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": system_prompt.strip()},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.4,
    )
    content = resp.choices[0].message.content
    try:
        data = json.loads(content)
        if isinstance(data, list):
            cleaned = []
            for item in data:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name", "")).strip()
                url = str(item.get("url", "")).strip()
                if not name or not url:
                    continue
                cleaned.append(
                    {
                        "name": name,
                        "url": url,
                        "description": str(item.get("description", "")).strip(),
                        "country_or_region": str(
                            item.get("country_or_region", "")
                        ).strip(),
                        "primary_language": str(
                            item.get("primary_language", "")
                        ).strip(),
                    }
                )
            return cleaned
        return []
    except json.JSONDecodeError:
        return []


@router.post("/api/get_job_sites")
def get_job_sites(req: LocationRequest):
    ui_lang = req.language or "en"
    location_text = ""
    country_code = ""
    country_name = ""
    city = ""

    if req.latitude is not None and req.longitude is not None:
        geo = reverse_geocode(req.latitude, req.longitude)
        country_code = geo.get("country_code", "")
        country_name = geo.get("country_name", "Unknown")
        city = geo.get("city", "")
    elif req.country_code:
        country_code = req.country_code.lower()
        country_name = req.country_code.upper()
        city = ""

    if not country_code and not country_name:
        raise HTTPException(status_code=400, detail="Location not provided")

    if city:
        location_text = f"{city}, {country_name} ({country_code.upper()})"
    else:
        location_text = f"{country_name} ({country_code.upper()})"

    sites = ask_ai_for_job_sites(location_text, ui_lang)

    return {
        "country_code": country_code or "unknown",
        "country_name": country_name or "Unknown",
        "city": city,
        "sites": sites,
    }
