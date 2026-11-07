from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import admin, auth, care, files, people, pregnancies, records
from app.core.config import settings
from app.core.startup_checks import check_runtime_settings

# Outside development, refuse to start with committed defaults (JWT secret,
# migrator credentials in the API process, insecure cookies).
check_runtime_settings(settings)

app = FastAPI(title="MatriSathi API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", settings.csrf_header_name, "Idempotency-Key"],
)

api_v1 = APIRouter(prefix="/api/v1")
api_v1.include_router(auth.router)
api_v1.include_router(people.router)
api_v1.include_router(pregnancies.router)
api_v1.include_router(admin.router)
api_v1.include_router(files.router)
api_v1.include_router(care.router)
api_v1.include_router(records.router)
app.include_router(api_v1)


@app.get("/health")
def health() -> dict:
    # The environment label lets anyone confirm they are on staging, not a
    # real deployment. It is a label only, never a secret.
    return {"status": "ok", "env": settings.env}
