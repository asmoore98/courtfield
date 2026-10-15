import mimetypes
import os
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from . import config
from .auth import current_user
from .db import Base, engine, get_db
from .models import User
from .routers import auth as auth_routes
from .routers import jobs, materials, reports, team, time
from .routers.auth import me_out
from .schemas import MeOut

if config.IS_DEV:
    # Production schema is managed by Alembic migrations (see backend/migrations).
    Base.metadata.create_all(engine)

app = FastAPI(title="Courtfield", version="0.2.0", docs_url="/api/docs" if config.IS_DEV else None, redoc_url=None,
              openapi_url="/api/openapi.json" if config.IS_DEV else None)
if config.IS_DEV:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],  # Vite dev server
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    h = response.headers
    h.setdefault("X-Content-Type-Options", "nosniff")
    h.setdefault("X-Frame-Options", "DENY")
    h.setdefault("Referrer-Policy", "no-referrer")  # invite links carry a token in the path
    h.setdefault("Permissions-Policy", "geolocation=(self), camera=(), microphone=()")
    if not config.IS_DEV:
        h.setdefault("Strict-Transport-Security", "max-age=31536000")
    path = request.url.path
    if path.startswith("/api/") or path in ("/", "/index.html", "/sw.js", "/registerSW.js", "/manifest.webmanifest") or path.startswith("/invite/"):
        h["Cache-Control"] = "no-store" if path.startswith("/api/") else "no-cache"
    return response


app.include_router(auth_routes.router)
app.include_router(team.router)
app.include_router(jobs.router)
app.include_router(time.router)
app.include_router(reports.router)
app.include_router(materials.router)


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/me", response_model=MeOut)
def me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return me_out(db, user)


mimetypes.add_type("application/manifest+json", ".webmanifest")

# Serve the built front end (frontend/dist) from the same origin when present.
_dist = Path(os.environ.get("FRONTEND_DIST", Path(__file__).resolve().parents[2] / "frontend" / "dist")).resolve()
if _dist.is_dir():
    app.mount("/assets", StaticFiles(directory=_dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404, "Not found")
        target = _dist / path
        if path and target.is_file() and _dist in target.resolve().parents:
            return FileResponse(target)
        return FileResponse(_dist / "index.html")
