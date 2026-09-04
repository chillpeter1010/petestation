from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.api.dependencies.auth import require_admin
from app.api.routes import admin, auth, batter_comparison, batters, catchers, comparison, derived, discipline, games, home, location, models, personal, pitchers, pitching, rotation, similarity, stuff, teams
from app.api.routes.auth import SESSION_COOKIE, get_auth_store
from app.core.config import settings

app = FastAPI(title=settings.app_name, version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PUBLIC_PATHS = {"/api/health", "/api/auth/login", "/api/auth/register"}


@app.middleware("http")
async def require_private_site_session(request: Request, call_next):
    path = request.url.path.rstrip("/") or "/"
    if request.method == "OPTIONS" or path in PUBLIC_PATHS:
        return await call_next(request)
    if path.startswith("/api/") or path in {"/docs", "/redoc", "/openapi.json"}:
        user = get_auth_store().user_for_session(request.cookies.get(SESSION_COOKIE))
        if user is None:
            return JSONResponse(status_code=401, content={"detail": "Authentication required."})
        request.state.auth_user = user
    return await call_next(request)


app.include_router(auth.router, prefix="/api/auth", tags=["auth"])

app.include_router(pitchers.router, prefix="/api/pitchers", tags=["pitchers"])
app.include_router(batters.router, prefix="/api/batters", tags=["batters"])
app.include_router(catchers.router, prefix="/api/catchers", tags=["catchers"])
app.include_router(personal.router, prefix="/api/personal", tags=["personal"])
app.include_router(stuff.router, prefix="/api/stuff", tags=["stuff"])
app.include_router(discipline.router, prefix="/api/discipline", tags=["discipline"])
app.include_router(location.router, prefix="/api/location", tags=["location"])
app.include_router(pitching.router, prefix="/api/pitching", tags=["pitching"])
app.include_router(similarity.router, prefix="/api/similarity", tags=["similarity"])
app.include_router(comparison.router, prefix="/api/comparison", tags=["comparison"])
app.include_router(batter_comparison.router, prefix="/api/batter-comparison", tags=["batter-comparison"])
app.include_router(rotation.router, prefix="/api/rotation", tags=["rotation"])
app.include_router(models.router, prefix="/api/models", tags=["models"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])
app.include_router(derived.router, prefix="/api/derived", tags=["derived"])
app.include_router(games.router, prefix="/api/games", tags=["games"])
app.include_router(teams.router, prefix="/api/teams", tags=["teams"])
app.include_router(home.router, prefix="/api/home", tags=["home"])


@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
