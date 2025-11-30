import os
import json
import time
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

router = APIRouter()

CACHE: Dict[str, Dict[str, Any]] = {}
CACHE_TTL = 60 * 60

class BankingLocationRequest(BaseModel):
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    country_code: Optional[str] = None
    language: Optional[str] = None

class Bank(BaseModel):
    name: str
    tagline: str
    features: List[str]
    rating_value: float
    rating_text: str
    icon: str
    url: Optional[str] = None
    branches_nearby: Optional[str] = None

class BankingStep(BaseModel):
    number: int
    title: str
    description: str

class BankingInfo(BaseModel):
    country_code: str
    country_name: str
    city: str
    location_text_used: str
    banks: List[Bank]
    steps: List[BankingStep]

async def reverse_geocode(lat: float, lon: float) -> Dict[str, str]:
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json&addressdetails=1"
        async with httpx.AsyncClient(timeout=5.0) as http_client:
            resp = await http_client.get(url, headers={"User-Agent": "UrbanMind"})
            data = resp.json()
            addr = data.get("address", {})
            return {
                "country_code": addr.get("country_code", "").lower(),
                "country_name": addr.get("country", "") or "Unknown",
                "city": addr.get("city")
                or addr.get("town")
                or addr.get("village")
                or addr.get("municipality")
                or addr.get("state")
                or "",
            }
    except Exception:
        return {"country_code": "", "country_name": "Unknown", "city": ""}

async def geolocate_ip(ip: str) -> Dict[str, str]:
    try:
        async with httpx.AsyncClient(timeout=5.0) as http_client:
            resp = await http_client.get(f"https://ipapi.co/{ip}/json/")
            data = resp.json()
            return {
                "country_code": str(data.get("country_code", "")).lower(),
                "country_name": data.get("country_name", "") or "Unknown",
                "city": data.get("city", "") or data.get("region", "") or "",
            }
    except Exception:
        return {"country_code": "", "country_name": "Unknown", "city": ""}

def get_cache(key: str) -> Optional[Dict[str, Any]]:
    entry = CACHE.get(key)
    if not entry:
        return None
    if entry["expires"] < time.time():
        return None
    return entry["data"]

def set_cache(key: str, data: Dict[str, Any]) -> None:
    CACHE[key] = {"data": data, "expires": time.time() + CACHE_TTL}

async def ask_ai_for_banking_info(location_text: str, language: str) -> BankingInfo:
    system_prompt = (
        "You are an expert banking assistant for migrants in European countries. "
        "Given the user's location (city and country), you always respond with a single JSON object describing: "
        "1) banks near that location (including large, medium and smaller local banks that realistically operate there) and "
        "2) a clear step-by-step guide on how to open a bank account in that country."
    )
    user_prompt = (
        "Return a JSON object with the following structure:\n"
        "{\n"
        '  "country_code": string,\n'
        '  "country_name": string,\n'
        '  "city": string,\n'
        '  "banks": [\n'
        "    {\n"
        '      "name": string,\n'
        '      "tagline": string,\n'
        '      "features": [string, ...],\n'
        '      "rating_value": number,\n'
        '      "rating_text": string,\n'
        '      "icon": string,\n'
        '      "url": string,\n'
        '      "branches_nearby": string\n'
        "    },\n"
        "    ...\n"
        "  ],\n"
        '  "steps": [\n'
        "    {\n"
        '      "number": number,\n'
        '      "title": string,\n'
        '      "description": string\n'
        "    },\n"
        "    ...\n"
        "  ]\n"
        "}\n\n"
        f"Target language for all user-facing text: {language}.\n"
        f"User location: {location_text}.\n"
        "Content rules:\n"
        "- banks: 8 to 15 real retail banks that operate in this country and are realistically available in or near the given city, including major national banks, regional banks and popular online banks. Prefer banks with branches or strong presence close to the user's city.\n"
        "- features: short bullet-point style advantages of the bank for newcomers, expats, students and foreigners.\n"
        "- rating_value: number between 3.5 and 5.0 representing overall reputation.\n"
        "- rating_text: human-readable rating summary, for example '4.6/5 (about 1,200 reviews)'.\n"
        "- icon: a simple keyword hint for the icon such as 'university', 'landmark', 'piggy-bank', or 'building'.\n"
        "- branches_nearby: short text describing nearby branches relative to the city center or user location.\n"
        "- steps: concise ordered guide explaining how a foreigner opens a basic current account in this country.\n"
        "- Do not include any explanatory text outside the JSON object."
    )

    resp = await client.chat.completions.create(
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
        max_tokens=2000,
    )

    content = resp.choices[0].message.content

    try:
        data = json.loads(content)
    except Exception:
        raise HTTPException(status_code=500, detail="AI returned invalid JSON")

    country_code_out = str(data.get("country_code") or "").lower()
    country_name = str(data.get("country_name") or "").strip()
    city = str(data.get("city") or "").strip()
    banks_raw = data.get("banks") or []
    steps_raw = data.get("steps") or []

    banks: List[Bank] = []
    for b in banks_raw:
        if not isinstance(b, dict):
            continue
        name = str(b.get("name") or "").strip()
        if not name:
            continue
        tagline = str(b.get("tagline") or "").strip()
        features_raw = b.get("features") or []
        features: List[str] = []
        for f in features_raw:
            if not f:
                continue
            features.append(str(f).strip())
        try:
            rating_value = float(b.get("rating_value") or 0.0)
        except Exception:
            rating_value = 0.0
        rating_text = str(b.get("rating_text") or "").strip()
        icon = str(b.get("icon") or "").strip() or "university"
        url = str(b.get("url") or "").strip() or ""
        branches_nearby = str(b.get("branches_nearby") or "").strip() or ""
        banks.append(
            Bank(
                name=name,
                tagline=tagline,
                features=features,
                rating_value=rating_value,
                rating_text=rating_text,
                icon=icon,
                url=url or None,
                branches_nearby=branches_nearby or None,
            )
        )

    steps: List[BankingStep] = []
    for s in steps_raw:
        if not isinstance(s, dict):
            continue
        try:
            number = int(s.get("number") or 0)
        except Exception:
            number = 0
        title = str(s.get("title") or "").strip()
        description = str(s.get("description") or "").strip()
        if not title or not description:
            continue
        steps.append(BankingStep(number=number, title=title, description=description))

    if not country_code_out and location_text:
        country_code_out = location_text.split("(")[-1].replace(")", "").strip().lower()
    if not country_name:
        country_name = location_text

    info = BankingInfo(
        country_code=country_code_out or "unknown",
        country_name=country_name or "Unknown",
        city=city,
        location_text_used=location_text,
        banks=banks,
        steps=sorted(steps, key=lambda x: x.number or 0),
    )

    return info

@router.post("/api/get_banking_info", response_model=BankingInfo)
async def get_banking_info(req: BankingLocationRequest, request: Request) -> BankingInfo:
    ui_lang = req.language or "en"

    country_code = ""
    country_name = ""
    city = ""

    if req.latitude is not None and req.longitude is not None:
        geo = await reverse_geocode(req.latitude, req.longitude)
        country_code = geo["country_code"]
        country_name = geo["country_name"]
        city = geo["city"]
    elif req.country_code:
        country_code = req.country_code.lower()
        country_name = req.country_code.upper()
        city = ""
    else:
        ip = request.client.host
        geo = await geolocate_ip(ip)
        country_code = geo["country_code"]
        country_name = geo["country_name"]
        city = geo["city"]

    if not country_code and not country_name:
        raise HTTPException(status_code=400, detail="Cannot determine location")

    if city:
        location_text = f"{city}, {country_name} ({country_code.upper()})"
    else:
        location_text = f"{country_name} ({country_code.upper()})"

    cache_key = f"{country_code}:{city}:{ui_lang}"
    cached = get_cache(cache_key)
    if cached:
        return BankingInfo(**cached)

    info = await ask_ai_for_banking_info(location_text, ui_lang)
    set_cache(cache_key, info.dict())
    return info
