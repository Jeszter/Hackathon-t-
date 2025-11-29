from fastapi import FastAPI
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

app = FastAPI()

# Путь к фронту
front_dir = Path(__file__).parent / "Front"

# Домашняя страница
@app.get("/")
async def home():
    return FileResponse(front_dir / "index.html")

# Подключение статических файлов (css, js, img)
app.mount("/css", StaticFiles(directory=front_dir / "css"), name="css")
app.mount("/js", StaticFiles(directory=front_dir / "js"), name="js")
app.mount("/img", StaticFiles(directory=front_dir / "img"), name="img")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(work_router, prefix="/work")
app.include_router(docs_router, prefix="/docs")
app.include_router(language_router, prefix="/language")
app.include_router(housing_router, prefix="/housing")

# Запуск
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
