from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import uvicorn

from dotenv import load_dotenv
load_dotenv()

from back.work_backend import router as work_router
from back.docs_backend import router as docs_router
from back.language_backend import router as language_router
from back.housing_backend import router as housing_router
from back.neurohr_backend import router as neurohr_router
from back.job_api import router as job_router
from back.translation_api import router as translation_router
from back.language_backend import router as language_router
from back.culture_router import router as culture_router
from back.chat_backend import router as chat_router
from back.offices_back import router as offices_router
from back.housing_backend import router as housing_router
from back.registration_routes import router as registration_router

app = FastAPI()

front_dir = Path(__file__).parent / "Front"
pages_dir = front_dir / "pages"
components_dir = front_dir / "components"

print("=== DEBUG INFO ===")
print(f"Front dir: {front_dir}")
print(f"Pages dir: {pages_dir}")
print(f"Components dir: {components_dir}")
print(f"Header file exists: {(components_dir / 'header.html').exists()}")
print("==================")


@app.get("/header.html")
async def get_header():
    header_file = components_dir / "header.html"
    print(f"Looking for header at: {header_file}")
    print(f"Header exists: {header_file.exists()}")

    if header_file.exists():
        return FileResponse(header_file)
    else:
        raise HTTPException(status_code=404, detail="Header file not found")


@app.get("/")
async def home():
    return FileResponse(pages_dir / "home.html")


@app.get("/neurohr")
async def neurohr():
    return FileResponse(pages_dir / "neurohr.html")


@app.get("/jobs")
async def jobs():
    return FileResponse(pages_dir / "jobs.html")


@app.get("/translation")
async def translation():
    return FileResponse(pages_dir / "translation.html")


@app.get("/cultural")
async def cultural():
    return FileResponse(pages_dir / "culture.html")


@app.get("/language")
async def language():
    return FileResponse(pages_dir / "language.html")


@app.get("/official")
async def official():
    return FileResponse(pages_dir / "official.html")


@app.get("/housing")
async def housing():
    return FileResponse(pages_dir / "housing.html")



@app.get("/registration")
async def registration():
    return FileResponse(pages_dir / "registration.html")


@app.get("/banking")
async def banking():
    return FileResponse(pages_dir / "banking.html")


@app.get("/legal")
async def legal():
    return FileResponse(pages_dir / "legal.html")





app.mount("/css", StaticFiles(directory=front_dir / "css"), name="css")
app.mount("/js", StaticFiles(directory=front_dir / "js"), name="js")
app.mount("/img", StaticFiles(directory=front_dir / "img"), name="img")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(work_router, prefix="/work")
app.include_router(docs_router, prefix="/docs")
app.include_router(language_router, prefix="/language")
app.include_router(housing_router, prefix="/api")
app.include_router(neurohr_router, prefix="/neurohr-api")
app.include_router(job_router)
app.include_router(translation_router)
app.include_router(language_router, prefix="/api/language")
app.include_router(culture_router, prefix="/api/culture")
app.include_router(chat_router, prefix="/api")
app.include_router(offices_router, prefix="/api")
app.include_router(registration_router)



if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
