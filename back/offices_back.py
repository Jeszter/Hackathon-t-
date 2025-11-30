import os
import json
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from openai import OpenAI
from pydantic import BaseModel

load_dotenv()

router = APIRouter()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


class OfficesRequest(BaseModel):
    address: str
    ui_language: str = "en"


offices_system_prompt = """
You are an AI assistant for the UrbanMind platform that helps migrants find official migration police offices and migrant support centers near a given address.

Your task:
1) Read the user address (street, city, region, or just city and country).
2) Infer the country and region as well as possible.
3) Using your knowledge about real institutions, list the closest relevant offices and centers:
   - migration or foreign police
   - state migration services
   - residence/visa/registration offices
   - integration or advisory centers for migrants and refugees
   - NGOs that provide legal, social or integration support

Output format:
Return ONLY a single valid JSON object with the following structure:

{
  "offices": [
    {
      "name": "...",
      "type": "migration_police" or "migrant_help_center",
      "category": "state" or "ngo",
      "address": "...",
      "city": "...",
      "country": "...",
      "phone": "... or null",
      "email": "... or null",
      "website": "... or null",
      "lat": number or null,
      "lon": number or null,
      "distance_km_estimate": number or null
    },
    ...
  ]
}

Rules:
- Do not add any text outside JSON.
- Always return the "offices" array, even if it is empty.
- If you are not sure about coordinates, set "lat" and "lon" to null.
- If you are not sure about distance, set "distance_km_estimate" to null.
- Use the same language as the user (based on ui_language) for "name", "address", "city" and "country" when possible.
"""


@router.post("/offices/nearby")
async def get_nearby_offices(payload: OfficesRequest):
    try:
        messages = [
            {"role": "system", "content": offices_system_prompt},
            {
                "role": "user",
                "content": f"User address: {payload.address}\nUI language: {payload.ui_language}"
            }
        ]

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.2,
            max_tokens=700
        )

        raw_reply = response.choices[0].message.content

        try:
            data = json.loads(raw_reply)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=500,
                detail="AI response is not valid JSON"
            )

        if "offices" not in data or not isinstance(data["offices"], list):
            raise HTTPException(
                status_code=500,
                detail="AI response does not contain 'offices' list"
            )

        return {
            "status": "success",
            "data": {
                "address": payload.address,
                "offices": data["offices"]
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Offices search error: {str(e)}")
