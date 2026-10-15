from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from .auth import ENTERS_TIME, SEES_DOLLARS, current_user
from .db import Base, engine, get_db
from .models import Company, User
from .routers import jobs, time
from .schemas import MeOut

Base.metadata.create_all(engine)

app = FastAPI(title="Courtfield", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(jobs.router)
app.include_router(time.router)


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/me", response_model=MeOut)
def me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    company = db.get(Company, user.company_id)
    return MeOut(
        id=user.id, name=user.name, role=user.role,
        company_id=company.id, company_name=company.name,
        sees_dollars=user.role in SEES_DOLLARS, enters_time=user.role in ENTERS_TIME,
    )


# Serve the built front end (frontend/dist) from the same origin when present.
_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _dist.is_dir():
    app.mount("/assets", StaticFiles(directory=_dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        target = _dist / path
        if path and target.is_file() and _dist in target.resolve().parents:
            return FileResponse(target)
        return FileResponse(_dist / "index.html")
