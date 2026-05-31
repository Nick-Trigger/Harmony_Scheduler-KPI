from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import register_handlers

app = FastAPI(
    title="Scheduling API",
    version="0.1.0",
    description="A scheduling API for factories.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


from app.api.schedule import router as schedule_router
app.include_router(schedule_router)
register_handlers(app)


@app.get("/health")
def health():
    return {"status": "ok"}
