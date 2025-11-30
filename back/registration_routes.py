import os
import json
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

router = APIRouter()

CACHE: Dict[str, Dict[str, Any]] = {}
CACHE_TTL = 60 * 60


class RegistrationRequest(BaseModel):
    country_code: str
    language: Optional[str] = None


class ImmigrationSite(BaseModel):
    label: str
    url: str


class RegistrationInfo(BaseModel):
    country_code: str
    country_name: str
    flag: str
    process_title: str
    description: str
    deadline: str
    cost: str
    documents: List[str]
    immigration_sites: List[ImmigrationSite]


def get_cache(key: str) -> Optional[Dict[str, Any]]:
    entry = CACHE.get(key)
    if not entry:
        return None
    if entry["expires"] < time.time():
        return None
    return entry["data"]


def set_cache(key: str, data: Dict[str, Any]) -> None:
    CACHE[key] = {"data": data, "expires": time.time() + CACHE_TTL}


def ask_ai_for_registration_info(country_code: str, language: str) -> RegistrationInfo:
    system_prompt = (
        "You are an expert in immigration and migrant procedures in European countries. "
        "You always answer with a single JSON object describing how migrants should handle visa or residence permit applications "
        "and registration with the immigration authority (foreigners office, migration police, immigration service) for the given country. "
        "You focus on: which documents are needed to submit the application, where and how to book an appointment/termin, "
        "and how much time after arrival the migrant typically has to do this."
    )
    user_prompt = (
        "Return a JSON object with the following fields:\n"
        "{\n"
        '  "country_code": string,\n'
        '  "country_name": string,\n'
        '  "flag": string,\n'
        '  "process_title": string,\n'
        '  "description": string,\n'
        '  "deadline": string,\n'
        '  "cost": string,\n'
        '  "documents": [string, ...],\n'
        '  "immigration_sites": [\n'
        '    {"label": string, "url": string},\n'
        "    ...\n"
        "  ]\n"
        "}\n\n"
        f"Target language for all user-facing text: {language}.\n"
        f"Country ISO code: {country_code.upper()}.\n"
        "Content requirements:\n"
        "- description: short overview of how migrants apply for a visa or residence permit after arrival and where they must register (immigration office, migration police, foreigners office, etc.).\n"
        "- deadline: explain how long after arrival the migrant typically has to register or submit the residence permit/visa application (for example: 'within 3 days after arrival', 'within 3 months after entering with a long-stay visa').\n"
        "- cost: typical state fees for the residence permit/visa application, described in simple language such as 'Around 90–120 EUR depending on permit type'.\n"
        "- documents: list of key documents required to apply for a visa or residence permit and to register at the immigration authority (passport, biometric photos, proof of accommodation, health insurance, proof of income, application form, etc.).\n"
        "- immigration_sites: only official government, ministry, or city immigration pages where migrants can find information about the process or book appointments/termins online.\n"
        "General rules:\n"
        "- Use the correct country name for the given ISO code.\n"
        "- Use the correct flag emoji in the flag field.\n"
        "- If exact legal numbers or fees are uncertain, use safe wording like 'typically within X days' or 'around Y EUR' instead of very precise legal citations.\n"
        "- Do not include any explanatory text outside the JSON object."
    )

    resp = client.chat.completions.create(
        model="gpt-4.1-mini",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
    )

    content = resp.choices[0].message.content

    try:
        data = json.loads(content)
    except Exception:
        raise HTTPException(status_code=500, detail="AI returned invalid JSON")

    country_code_out = str(data.get("country_code") or country_code).lower()
    country_name = str(data.get("country_name") or "").strip()
    flag = str(data.get("flag") or "").strip()
    process_title = str(data.get("process_title") or "").strip()
    description = str(data.get("description") or "").strip()
    deadline = str(data.get("deadline") or "").strip()
    cost = str(data.get("cost") or "").strip()
    documents_raw = data.get("documents") or []
    immigration_sites_raw = data.get("immigration_sites") or []

    documents: List[str] = []
    for d in documents_raw:
        if not d:
            continue
        documents.append(str(d).strip())

    sites: List[ImmigrationSite] = []
    for s in immigration_sites_raw:
        if not isinstance(s, dict):
            continue
        label = str(s.get("label") or "").strip()
        url = str(s.get("url") or "").strip()
        if not label or not url:
            continue
        sites.append(ImmigrationSite(label=label, url=url))

    info = RegistrationInfo(
        country_code=country_code_out,
        country_name=country_name,
        flag=flag,
        process_title=process_title or country_name or country_code_out.upper(),
        description=description,
        deadline=deadline,
        cost=cost,
        documents=documents,
        immigration_sites=sites,
    )

    return info


@router.post("/api/get_registration_info", response_model=RegistrationInfo)
async def get_registration_info(req: RegistrationRequest) -> RegistrationInfo:
    if not req.country_code:
        raise HTTPException(status_code=400, detail="country_code is required")

    language = req.language or "en"
    code = req.country_code.lower()
    cache_key = f"{code}:{language}"
    cached = get_cache(cache_key)
    if cached:
        return RegistrationInfo(**cached)

    info = ask_ai_for_registration_info(code, language)
    set_cache(cache_key, info.dict())
    return info
